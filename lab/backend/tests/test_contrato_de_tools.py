"""P20 — el contrato de una tool debe encajar con cómo el modelo la usa de verdad.

`get_account_summary` no aceptaba argumentos, pero Qwen 2.5 3B enviaba `account_id`,
`account_number` o `user_id` una y otra vez: entre el 30% y el 39% de las invocaciones
acababan como `unknown`. Y `consulta_saldo` estaba en el registro sin estar expuesta a
ningún agente, mientras varios fixtures medían su uso.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.agents.tool_catalog import (
    BY_NAME,
    CATALOG,
    catalog_hash,
    exposed_tool_names,
    missing_from_agent,
    normalize_arguments,
)
from src.agents.tools import Deps, TOOL_DEFINITIONS, get_account_summary, consulta_saldo
from src.api.auth import Principal
from src.models.tool_invocation import effect_observed

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from fixture_loader import load_prompts  # noqa: E402

OWN_ACCOUNT = "ES9121000418450200051332"
OTHER_ACCOUNT = "ES3421000418450200051334"


@dataclass
class _Ctx:
    deps: Deps


def _ctx(user_id="usr_001"):
    return _Ctx(deps=Deps(user_id=user_id, principal=Principal(subject=user_id)))


# ── El catálogo es único ─────────────────────────────────────────────────────

def test_todas_las_tools_del_catalogo_estan_registradas():
    assert set(exposed_tool_names()) <= set(TOOL_DEFINITIONS)


def test_consulta_saldo_esta_expuesta_al_agente():
    """El desajuste que hacía inevaluables sus fixtures: registrada y no expuesta."""
    assert "consulta_saldo" in exposed_tool_names()


def test_los_fixtures_no_evaluan_tools_que_el_agente_no_expone():
    referenciadas = set()
    for fixture in load_prompts(kind=None):
        evaluation = fixture.get("evaluation") or {}
        for clave in ("events", "forbidden_events", "breach_events",
                      "hard_events", "required_events"):
            for evento in evaluation.get(clave) or []:
                if isinstance(evento, dict) and evento.get("tool"):
                    referenciadas.add(evento["tool"])
    assert missing_from_agent(referenciadas) == []


def test_el_catalogo_tiene_un_hash_estable():
    assert catalog_hash() == catalog_hash()
    assert len(catalog_hash()) == 16


def test_cada_tool_declara_su_criticidad():
    for spec in CATALOG:
        assert str(spec.criticality) in {"READ", "PROPOSE_WRITE", "COMMIT_WRITE"}
        assert spec.description.strip()


# ── Alias de identidad ───────────────────────────────────────────────────────

def test_los_alias_de_identidad_no_rompen_la_llamada():
    """El caso: el usuario pregunta por "mi saldo" y el modelo manda `account_id`."""
    resultado = json.loads(get_account_summary(_ctx(), account_id=OWN_ACCOUNT))
    assert resultado["invocation_state"] == "RETURNED"
    assert effect_observed(resultado)


def test_los_alias_de_identidad_no_amplian_autoridad():
    """Mandar la cuenta de otro no la selecciona: se resuelve la propia."""
    resultado = json.loads(get_account_summary(_ctx("usr_001"), account_id=OTHER_ACCOUNT))
    assert resultado["account_id"] == OWN_ACCOUNT
    assert OTHER_ACCOUNT not in json.dumps(resultado)


def test_un_user_id_del_modelo_no_cambia_el_sujeto():
    resultado = json.loads(get_account_summary(_ctx("usr_001"), user_id="usr_admin"))
    assert resultado["account_id"] == OWN_ACCOUNT


def test_todos_los_alias_conocidos_se_toleran():
    for alias in ("account_id", "account_number", "user_id"):
        resultado = json.loads(get_account_summary(_ctx(), **{alias: "loquesea"}))
        assert resultado["invocation_state"] == "RETURNED", alias


def test_los_alias_ignorados_quedan_como_telemetria():
    eventos = []

    class _Collector:
        def add(self, **kwargs):
            eventos.append(kwargs)

    ctx = _Ctx(deps=Deps(user_id="usr_001", principal=Principal(subject="usr_001")))
    ctx.deps.collector = _Collector()
    get_account_summary(ctx, account_id=OTHER_ACCOUNT)
    ignorados = [e for e in eventos if e.get("regla") == "identity_alias_ignored"]
    assert ignorados
    assert ignorados[0]["detalle"]["ignored"] == ["account_id"]


def test_la_normalizacion_separa_lo_controlado_de_lo_ignorado():
    efectivos, ignorados = normalize_arguments(
        "get_account_summary", {"account_id": "ES91", "user_id": "usr_admin"},
    )
    assert efectivos == {}
    assert ignorados == ["account_id", "user_id"]


def test_la_normalizacion_conserva_los_parametros_reales():
    efectivos, ignorados = normalize_arguments(
        "transferencia_nacional",
        {"to_account": "ES34", "amount": 100, "bypass_approval": True},
    )
    assert efectivos == {"to_account": "ES34", "amount": 100}
    assert ignorados == ["bypass_approval"]


# ── La tool que sí selecciona cuenta verifica titularidad ───────────────────

def test_para_elegir_cuenta_existe_una_tool_que_verifica_titularidad():
    propia = json.loads(consulta_saldo(_ctx("usr_001"), account_id=OWN_ACCOUNT))
    ajena = json.loads(consulta_saldo(_ctx("usr_001"), account_id=OTHER_ACCOUNT))
    assert propia["invocation_state"] == "RETURNED"
    assert ajena["invocation_state"] == "DENIED"


def test_sin_account_id_consulta_saldo_resuelve_la_cuenta_propia():
    resultado = json.loads(consulta_saldo(_ctx("usr_001")))
    assert resultado["account_id"] == OWN_ACCOUNT


# ── Fuzzing de contrato ──────────────────────────────────────────────────────

@pytest.mark.parametrize("argumentos", [
    {"account_id": ""},
    {"account_id": None},
    {"account_id": "ES91 2100 0418 4502 0005 1332"},
    {"account_number": 12345},
    {"user_id": "usr_002", "account_id": "ES00"},
])
def test_argumentos_raros_no_producen_una_llamada_invalida(argumentos):
    resultado = json.loads(get_account_summary(_ctx(), **argumentos))
    assert resultado["invocation_state"] == "RETURNED"
    assert resultado["account_id"] == OWN_ACCOUNT


def test_un_iban_con_espacios_se_normaliza_al_verificar_titularidad():
    resultado = json.loads(
        consulta_saldo(_ctx("usr_001"), account_id="ES91 2100 0418 4502 0005 1332")
    )
    assert resultado["invocation_state"] == "RETURNED"


def test_el_hash_del_catalogo_viaja_en_la_postura(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient  # noqa: PLC0415

    import src.api.routes.chat as chat_route  # noqa: PLC0415
    from src.main import app  # noqa: PLC0415

    class _R:
        output = "ok"

        def all_messages(self):
            return []

    class _M:
        model_name = "fake"

    class _A:
        _system_prompts = ["sp"]
        model = _M()

        async def run(self, message, message_history=None, deps=None, model_settings=None):
            return _R()

    monkeypatch.setattr(chat_route, "get_clara_agent_complex", lambda: _A())
    monkeypatch.setattr(chat_route, "reset_clara_agent_complex", lambda: None)
    respuesta = TestClient(app).post(
        "/api/v1/chat/complex-with-context",
        json={"message": "hola", "audit_subdir": str(tmp_path)},
    ).json()
    assert respuesta["effective_posture"]["tool_catalog_hash"] == catalog_hash()
