"""P02 — una comparación solo es causal si el único factor que cambia es la defensa.

`simple-prompt` frente a `proxy-full` cambia system prompt, contexto inyectado y
catálogo de tools además de los controles: la diferencia que mide no es el proxy. Estos
tests fijan el contrato que impide publicar ese delta.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.models.posture import (
    CAUSAL_BASELINE_TARGET,
    TargetPosture,
    comparable,
    comparison_blockers,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from run_attack_suite import (  # noqa: E402
    applicable_targets,
    build_executions,
    order_in_blocks,
    requested_posture,
)

_INVARIANTES = {
    "prompt_hash": "aaaa", "context_injection": True, "document_channel": False,
    "tool_catalog_hash": "bbbb", "policy_hash": "cccc", "model_config_hash": "dddd",
}


def _postura(target, **controles):
    base = {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
            "output_auditor": False, "leak_guard": False, "shadow": False}
    invariantes = {**_INVARIANTES, **{k: v for k, v in controles.items() if k in _INVARIANTES}}
    efectiva = {**base, **{k: v for k, v in controles.items() if k not in _INVARIANTES},
                **invariantes, "target": target}
    return TargetPosture(target=target, requested=dict(efectiva), effective=efectiva)


# ── Fingerprint comparable ───────────────────────────────────────────────────

def test_dos_posturas_que_solo_difieren_en_defensas_son_comparables():
    baseline = _postura("proxy-baseline")
    defended = _postura("proxy-full", input_sanitizer=True, pii_shield=True,
                        tool_gatekeeper=True, output_auditor=True, leak_guard=True)
    assert comparable(baseline, defended)
    assert comparison_blockers(baseline, defended) == []


def test_un_solo_factor_no_defensivo_distinto_rompe_la_comparabilidad():
    baseline = _postura("proxy-baseline")
    defended = _postura("proxy-full", tool_gatekeeper=True, prompt_hash="OTRO")
    assert not comparable(baseline, defended)
    assert any("factores no defensivos" in razon for razon in comparison_blockers(baseline, defended))


def test_el_contexto_inyectado_tambien_rompe_la_comparabilidad():
    baseline = _postura("proxy-baseline", context_injection=False)
    defended = _postura("proxy-full", tool_gatekeeper=True)
    assert not comparable(baseline, defended)


# ── Endpoints pedagógicos ────────────────────────────────────────────────────

def test_un_endpoint_pedagogico_no_puede_ser_la_linea_base_del_proxy():
    pedagogico = _postura("complex-with-context")
    defended = _postura("proxy-full", tool_gatekeeper=True)
    razones = comparison_blockers(pedagogico, defended)
    assert any("pedagógico" in razon for razon in razones)


def test_la_linea_base_causal_es_el_perfil_baseline_del_proxy():
    assert CAUSAL_BASELINE_TARGET == "proxy-baseline"
    assert _postura("proxy-baseline").is_causal_baseline
    assert not _postura("proxy-baseline").is_pedagogical


# ── Baseline puro ────────────────────────────────────────────────────────────

def test_una_linea_base_con_un_control_activo_no_es_pura():
    """El caso real: `output_auditor` heredado tapaba la fuga en un baseline."""
    contaminada = _postura("proxy-baseline", output_auditor=True)
    assert not contaminada.is_causal_baseline
    razones = comparison_blockers(contaminada, _postura("proxy-full", tool_gatekeeper=True))
    assert any("no es pura" in razon for razon in razones)
    assert any("output_auditor" in razon for razon in razones)


def test_una_divergencia_entre_solicitada_y_efectiva_invalida_la_comparacion():
    defended = _postura("proxy-full", tool_gatekeeper=True)
    # El runner pidió el Input Sanitizer; el backend no lo aplicó (shadow, flag, bug).
    defended.requested["input_sanitizer"] = True
    assert defended.divergences() == ["input_sanitizer"]
    razones = comparison_blockers(_postura("proxy-baseline"), defended)
    assert any("solicitada≠efectiva" in razon for razon in razones)


# ── Postura solicitada por target ────────────────────────────────────────────

def test_la_postura_solicitada_del_baseline_apaga_todos_los_controles():
    assert set(requested_posture("proxy", "baseline").values()) == {False}


def test_los_endpoints_pedagogicos_solicitan_cero_controles():
    assert set(requested_posture("complex-with-context", None).values()) == {False}
    assert set(requested_posture("simple-prompt", None).values()) == {False}


# ── Diseño de bloques ────────────────────────────────────────────────────────

def _matriz(repeat=2):
    fixtures = [
        {"id": "atk_1", "rendered_steps": [{"content": "x"}]},
        {"id": "atk_2", "rendered_steps": [{"content": "y"}]},
    ]
    endpoints = {"proxy-baseline": "/p", "proxy-full": "/p"}
    profiles = {"proxy-baseline": "baseline", "proxy-full": "full"}
    return build_executions(fixtures, endpoints, profiles, repeat=repeat, run_folder_name="RUN")


def test_cada_bloque_contiene_el_mismo_fixture_y_repeticion_en_ambas_posturas():
    ordenadas = order_in_blocks(_matriz(), seed=7)
    bloques: dict[tuple, set] = {}
    for execution in ordenadas:
        bloques.setdefault((execution["fixture_id"], execution["repetition"]), set()).add(
            execution["target"]
        )
    assert len(bloques) == 4
    for targets in bloques.values():
        assert targets == {"proxy-baseline", "proxy-full"}


def test_el_orden_es_reproducible_con_la_misma_semilla():
    def firma(seed):
        return [e["fixture_execution_id"] for e in order_in_blocks(_matriz(), seed=seed)]

    matriz = _matriz()
    a = [e["target"] for e in order_in_blocks(matriz, seed=3)]
    b = [e["target"] for e in order_in_blocks(matriz, seed=3)]
    assert a == b


def test_cada_ejecucion_nace_con_identidad_propia():
    executions = _matriz()
    ids = {e["fixture_execution_id"] for e in executions}
    assert len(ids) == len(executions) == 8


def test_las_posturas_se_intercalan_dentro_del_bloque_no_por_target():
    """Con todos los fixtures de un target seguidos, la deriva temporal del proveedor
    se confundiría con la eficacia de esa postura."""
    ordenadas = order_in_blocks(_matriz(repeat=4), seed=11)
    targets = [e["target"] for e in ordenadas]
    # Si estuvieran agrupados por target habría exactamente un cambio de target.
    cambios = sum(1 for a, b in zip(targets, targets[1:]) if a != b)
    assert cambios > 1


def test_un_fixture_no_se_ejecuta_donde_no_mide_nada():
    fixture = {"id": "atk_leak", "rendered_steps": [{"content": "x"}],
               "applicable_endpoints": ["complex-prompt"]}
    endpoints = {"simple-prompt": "/s", "complex-prompt": "/c", "proxy-full": "/p"}
    assert applicable_targets(fixture, endpoints) == ["complex-prompt"]


def test_un_fixture_documental_solo_va_al_canal_documental():
    fixture = {"id": "atk_doc", "document": "payload.pdf"}
    endpoints = {"complex-with-document": "/d", "proxy-full": "/p"}
    assert applicable_targets(fixture, endpoints) == ["complex-with-document"]
