"""P19 — revisar el YAML debe permitir conocer la política efectiva.

`requires_approval: true` y `requires_approval_above: 1000` convivían y ganaba el
primero: toda transferencia autorizada quedaba pendiente con independencia del importe.
El `daily_limit` estaba declarado y no se aplicaba nunca, así que varias operaciones
individualmente válidas podían superar el total diario.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass

import pytest

from src.agents.tools import Deps, TOOL_DEFINITIONS, transferencia_nacional
from src.api.auth import Principal
from src.core import policy_engine, tool_permissions
from src.core.policy_engine import (
    ApprovalMode,
    DailyLedger,
    Effect,
    PolicyError,
    compile_policy,
    decide,
    dry_run,
)

CUENTA_DESTINO = "ES3421000418450200051334"


@dataclass
class _Ctx:
    deps: Deps


def _ctx(user_id="usr_001"):
    return _Ctx(deps=Deps(user_id=user_id, principal=Principal(subject=user_id)))


@pytest.fixture
def politica():
    tool_permissions.recargar()
    return tool_permissions.politica_compilada()


def _decidir(politica, amount, role="customer", **params):
    base = {"from_account": "ES91", "to_account": CUENTA_DESTINO,
            "amount": amount, "concept": "x"}
    return decide(
        politica, tool="transferencia_nacional", role=role,
        params={**base, **params}, subject="usr_001", amount=amount,
        ledger=DailyLedger(),
    )[0]


# ── El umbral se aplica ──────────────────────────────────────────────────────

def test_por_debajo_del_umbral_la_policy_autoriza(politica):
    decision = _decidir(politica, 100.0)
    assert decision.effect == Effect.ALLOW
    assert decision.threshold == 1000.0


def test_por_encima_del_umbral_la_policy_exige_confirmacion(politica):
    decision = _decidir(politica, 5000.0)
    assert decision.effect == Effect.REQUIRE_CONFIRMATION
    assert "umbral" in decision.reason


def test_por_encima_del_maximo_la_policy_deniega(politica):
    decision = _decidir(politica, 50000.0)
    assert decision.effect == Effect.DENY
    assert decision.threshold == 5000.0


def test_cada_decision_cita_la_regla_que_la_produjo(politica):
    assert _decidir(politica, 100.0).rule_id.endswith("requires_approval_above")
    assert _decidir(politica, 50000.0).rule_id.endswith("max_amount")
    assert _decidir(politica, 100.0, role="intruso").rule_id.endswith("allowed_roles")


def test_los_umbrales_dependen_del_rol(politica):
    """admin: max 50.000, aprobación por encima de 10.000."""
    assert _decidir(politica, 5000.0, role="admin").effect == Effect.ALLOW
    assert _decidir(politica, 20000.0, role="admin").effect == Effect.REQUIRE_CONFIRMATION


# ── Deny by default ──────────────────────────────────────────────────────────

def test_una_tool_no_declarada_se_deniega(politica):
    decision, _ = decide(politica, tool="tool_fantasma", role="customer", params={})
    assert decision.effect == Effect.DENY
    assert decision.rule_id == "deny_by_default.unknown_tool"


def test_un_rol_no_permitido_se_deniega(politica):
    assert _decidir(politica, 100.0, role="agent").effect == Effect.DENY


def test_un_parametro_prohibido_se_deniega(politica):
    decision = _decidir(politica, 100.0, bypass_approval=True)
    assert decision.effect == Effect.DENY
    assert "bypass_approval" in decision.reason


def test_un_parametro_obligatorio_ausente_se_deniega(politica):
    decision, _ = decide(
        politica, tool="transferencia_nacional", role="customer",
        params={"to_account": CUENTA_DESTINO, "amount": 100}, amount=100.0,
        ledger=DailyLedger(),
    )
    assert decision.effect == Effect.DENY
    assert "from_account" in decision.reason


def test_ninguna_tool_registrada_queda_sin_mapping_de_policy(politica):
    assert dry_run(politica, list(TOOL_DEFINITIONS)) == []


# ── Límite diario transaccional ──────────────────────────────────────────────

def test_el_acumulado_diario_se_aplica(politica):
    """El caso: varias operaciones individualmente válidas superando el total diario."""
    ledger = DailyLedger()
    for _ in range(2):
        decision, _ = decide(
            politica, tool="transferencia_nacional", role="customer",
            params={"from_account": "ES91", "to_account": CUENTA_DESTINO,
                    "amount": 4000, "concept": "x"},
            subject="usr_001", amount=4000.0, ledger=ledger,
        )
        assert decision.effect != Effect.DENY

    # 4.000 + 4.000 + 4.000 > 10.000 de cupo diario.
    decision, _ = decide(
        politica, tool="transferencia_nacional", role="customer",
        params={"from_account": "ES91", "to_account": CUENTA_DESTINO,
                "amount": 4000, "concept": "x"},
        subject="usr_001", amount=4000.0, ledger=ledger,
    )
    assert decision.effect == Effect.DENY
    assert decision.rule_id.endswith("daily_limit")
    assert decision.remaining_daily == 2000.0


def test_el_cupo_es_por_sujeto(politica):
    """Cada sujeto tiene su propio acumulado: 4.000 € no consumen el cupo de otro."""
    ledger = DailyLedger()
    for subject in ("usr_001", "usr_002"):
        for _ in range(2):
            decision, _ = decide(
                politica, tool="transferencia_nacional", role="customer",
                params={"from_account": "ES91", "to_account": CUENTA_DESTINO,
                        "amount": 4000, "concept": "x"},
                subject=subject, amount=4000.0, ledger=ledger,
            )
            assert decision.effect != Effect.DENY


def test_dos_transferencias_concurrentes_no_exceden_el_cupo(politica):
    """Comprobar y después ejecutar deja una ventana; reservar dentro del lock no."""
    ledger = DailyLedger()
    resultados = []

    def _pedir():
        decision, _ = decide(
            politica, tool="transferencia_nacional", role="customer",
            params={"from_account": "ES91", "to_account": CUENTA_DESTINO,
                    "amount": 4000, "concept": "x"},
            subject="usr_001", amount=4000.0, ledger=ledger,
        )
        resultados.append(decision.effect)

    hilos = [threading.Thread(target=_pedir) for _ in range(6)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    # Con 10.000 € de cupo y peticiones de 4.000 €, solo dos pueden pasar — nunca tres,
    # que es lo que ocurriría si se comprobara el acumulado antes de reservarlo.
    assert sum(1 for e in resultados if e != Effect.DENY) == 2


def test_liberar_una_reserva_devuelve_el_cupo_exactamente_una_vez():
    ledger = DailyLedger()
    reserva = ledger.reserve("usr_001", "t", 100.0, 1000.0)
    assert ledger.used("usr_001", "t") == 100.0
    assert ledger.release(reserva) is True
    assert ledger.used("usr_001", "t") == 0.0
    # Segunda liberación: no devuelve cupo dos veces.
    assert ledger.release(reserva) is False


def test_una_reserva_consumida_no_puede_liberarse():
    ledger = DailyLedger()
    reserva = ledger.reserve("usr_001", "t", 100.0, 1000.0)
    assert ledger.consume(reserva) is True
    assert ledger.release(reserva) is False
    assert ledger.consume(reserva) is False


# ── Compilación fail-closed ──────────────────────────────────────────────────

def test_un_campo_desconocido_rompe_la_compilacion():
    with pytest.raises(PolicyError, match="desconocidos"):
        compile_policy({"tools": {"t": {"allowed_roles": ["customer"], "typo_field": 1}}})


def test_una_tool_sin_roles_rompe_la_compilacion():
    with pytest.raises(PolicyError, match="allowed_roles"):
        compile_policy({"tools": {"t": {"description": "x"}}})


def test_un_modo_de_aprobacion_desconocido_rompe_la_compilacion():
    with pytest.raises(PolicyError, match="approval.mode"):
        compile_policy({"tools": {"t": {"allowed_roles": ["customer"],
                                        "approval": {"mode": "a_veces"}}}})


def test_above_threshold_sin_umbral_rompe_la_compilacion():
    with pytest.raises(PolicyError, match="sin umbral"):
        compile_policy({"tools": {"t": {
            "allowed_roles": ["customer"],
            "limits": {"customer": {"approval": {"mode": "above_threshold"}}},
        }}})


def test_una_policy_vacia_no_degrada_a_permitir_todo():
    with pytest.raises(PolicyError):
        compile_policy({"tools": {}})


def test_el_par_ambiguo_del_schema_v1_se_resuelve_por_el_umbral():
    """`requires_approval: true` + `requires_approval_above: 1000` ya no significa
    "siempre": el umbral declarado es el que manda."""
    politica = compile_policy({"tools": {"t": {
        "allowed_roles": ["customer"],
        "requires_approval": True,
        "limits": {"customer": {"requires_approval_above": 1000.0}},
    }}})
    limites = politica["t"].limits_for("customer")
    assert limites.approval_mode == ApprovalMode.ABOVE_THRESHOLD
    assert limites.approval_threshold == 1000.0


# ── Cambiar el YAML cambia el comportamiento, sin tocar código ───────────────

def test_cambiar_el_umbral_cambia_la_decision_sin_tocar_codigo(monkeypatch):
    politica = compile_policy({"tools": {"transferencia_nacional": {
        "allowed_roles": ["customer"],
        "required_params": ["to_account", "amount"],
        "limits": {"customer": {"max_amount": 5000.0, "requires_approval_above": 10.0}},
    }}})
    monkeypatch.setattr(tool_permissions, "_COMPILADA", politica)
    resultado = json.loads(transferencia_nacional(_ctx(), CUENTA_DESTINO, 50.0))
    # Con umbral 10 €, una transferencia de 50 € ya requiere autorización.
    assert resultado["status"] == "pending_confirmation"


def test_la_decision_efectiva_llega_al_resultado_de_la_tool():
    resultado = json.loads(transferencia_nacional(_ctx(), CUENTA_DESTINO, 50000.0))
    assert resultado["status"] == "denied"
    assert resultado["policy_rule"].startswith("transferencia_nacional.limits.")


def test_el_cupo_diario_se_aplica_extremo_a_extremo():
    policy_engine.default_ledger.reset_for_tests()
    # 3 × 4.000 € = 12.000 € > 10.000 € de cupo diario para "customer".
    estados = [
        json.loads(transferencia_nacional(_ctx(), CUENTA_DESTINO, 4000.0))["status"]
        for _ in range(3)
    ]
    policy_engine.default_ledger.reset_for_tests()
    assert estados.count("denied") == 1
