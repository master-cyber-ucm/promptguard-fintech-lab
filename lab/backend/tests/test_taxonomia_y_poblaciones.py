"""P11 — familia, categoría OWASP y población son dimensiones distintas.

Las tablas mezclaban mecanismos (`CHAINED_ATTACK`) con buckets OWASP (`LLM06`) en la
misma columna, y `security_breaches_observed` sumaba tráfico legítimo: en
`simple-prompt` aparecían 74 brechas cuando solo 69 eran ataques.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from src.models.taxonomy import (
    AttackFamily,
    SourceSuite,
    TaxonomyError,
    TrafficKind,
    classify,
    reconcile_populations,
)
from scripts.report import _build_md, _compute_stats

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from fixture_loader import load_prompts  # noqa: E402


# ── Dimensiones independientes ───────────────────────────────────────────────

def test_la_familia_no_cae_a_la_categoria_owasp_cuando_falta():
    """Ese fallback es lo que ponía `LLM06` junto a `CONFUSED_DEPUTY` en la misma columna."""
    taxonomia = classify({"id": "atk_x", "kind": "attack-prompts", "category": "LLM06"})
    assert taxonomia.owasp_category == "LLM06"
    assert taxonomia.attack_family == AttackFamily.NOT_APPLICABLE


def test_la_familia_se_resuelve_desde_un_mapping_declarado():
    taxonomia = classify({
        "id": "atk_1", "kind": "attack-prompts", "category": "LLM06",
        "attack": "LLM06-excessive-agency/confused-deputy",
    })
    assert taxonomia.attack_family == AttackFamily.CONFUSED_DEPUTY
    assert taxonomia.owasp_category == "LLM06"


def test_un_fixture_puede_declarar_su_familia_explicitamente():
    taxonomia = classify({
        "id": "atk_1", "kind": "attack-prompts", "attack_family": "JAILBREAK",
        "attack": "LLM06-excessive-agency/confused-deputy",
    })
    assert taxonomia.attack_family == AttackFamily.JAILBREAK


def test_los_alias_historicos_siguen_leyendose():
    """Cambiar un mapping no puede reescribir artefactos ya publicados."""
    taxonomia = classify({"id": "atk_1", "kind": "attack-prompts",
                          "attack_type": "PROMPT_INJECTION"})
    assert taxonomia.attack_family == AttackFamily.DIRECT_INJECTION


def test_en_modo_estricto_un_ataque_sin_familia_es_un_error():
    with pytest.raises(TaxonomyError):
        classify({"id": "atk_x", "kind": "attack-prompts", "category": "LLM06"}, strict=True)


# ── NAVI es procedencia, no familia ──────────────────────────────────────────

def test_navi_es_una_procedencia_dentro_de_la_poblacion_adversarial():
    taxonomia = classify({"id": "navi_1", "kind": "navi-prompts",
                          "attack": "_extensiones/jailbreak"})
    assert taxonomia.source_suite == SourceSuite.NAVI
    assert taxonomia.traffic_kind == TrafficKind.ATTACK
    assert taxonomia.attack_family == AttackFamily.JAILBREAK


def test_un_legitimo_no_tiene_familia_de_ataque():
    taxonomia = classify({"id": "leg_1", "kind": "legitimate-prompts", "category": "LLM06"})
    assert taxonomia.traffic_kind == TrafficKind.LEGITIMATE
    assert taxonomia.attack_family == AttackFamily.NOT_APPLICABLE


# ── El catálogo real se clasifica sin ambigüedad ─────────────────────────────

def test_todos_los_fixtures_adversariales_del_catalogo_tienen_familia():
    for fixture in load_prompts(kind=None):
        if fixture.get("kind") == "legitimate-prompts":
            continue
        taxonomia = classify(fixture, strict=True)
        assert taxonomia.attack_family != AttackFamily.NOT_APPLICABLE, fixture["id"]


def test_las_poblaciones_del_catalogo_son_disjuntas_y_suman():
    taxonomias = [classify(f) for f in load_prompts(kind=None)]
    reconciliacion = reconcile_populations(taxonomias)
    assert reconciliacion["populations_disjoint"] is True
    assert reconciliacion["families_sum_attacks"] is True
    assert reconciliacion["attack"] + reconciliacion["legitimate"] == reconciliacion["total"]


def test_navi_no_es_una_tercera_poblacion():
    taxonomias = [classify(f) for f in load_prompts(kind=None)]
    reconciliacion = reconcile_populations(taxonomias)
    assert reconciliacion["navi"] > 0
    assert reconciliacion["navi"] <= reconciliacion["attack"]


# ── Los contadores de seguridad no incluyen tráfico legítimo ────────────────

def _fila(fixture_id, kind, disposition, familia="DIRECT_INJECTION"):
    return {
        "fixture_id": fixture_id, "fixture_kind": kind,
        "traffic_kind": "LEGITIMATE" if kind == "legitimate-prompts" else "ATTACK",
        "attack_family": "NOT_APPLICABLE" if kind == "legitimate-prompts" else familia,
        "source_suite": "NAVI" if kind == "navi-prompts" else "CORE",
        "expected_result": "ALLOW" if kind == "legitimate-prompts" else "BLOCK",
        "method": "deterministic", "verdict": "SUCCESS", "passed": False, "detail": "",
        "inconclusive": False, "status": "FAIL", "disposition": disposition,
        "decision_source": "deterministic", "category": "LLM06", "attack_type": "",
        "severity": "HIGH", "name": fixture_id, "session_file": "x.md", "model": "m",
        "tool_outcomes": {}, "execution_status": "COMPLETED", "result_v2": None,
        "leak_assessments": [], "legitimate_outcome": None,
    }


def test_una_peticion_legitima_mal_evaluada_no_engorda_las_brechas():
    """El caso exacto: 74 brechas publicadas donde solo había 69 ataques."""
    filas = [
        *[_fila(f"atk_{i}", "attack-prompts", "SECURITY_BREACH") for i in range(69)],
        *[_fila(f"leg_{i}", "legitimate-prompts", "SECURITY_BREACH") for i in range(5)],
    ]
    resumen = _compute_stats(filas)["summary"]
    assert resumen["security_breaches_observed"] == 69
    assert resumen["populations"]["attack"] == 69
    assert resumen["populations"]["legitimate"] == 5


def test_las_brechas_adversariales_nunca_exceden_los_ataques_evaluados():
    filas = [_fila(f"atk_{i}", "attack-prompts", "SECURITY_BREACH") for i in range(10)]
    resumen = _compute_stats(filas)["summary"]
    assert resumen["security_breaches_observed"] <= resumen["attacks_total"]


def test_la_tabla_por_familia_no_mezcla_buckets_owasp():
    filas = [
        _fila("atk_1", "attack-prompts", "SECURITY_BREACH", familia="CHAINED_ATTACK"),
        _fila("atk_2", "attack-prompts", "SECURITY_BREACH", familia="CONFUSED_DEPUTY"),
        _fila("leg_1", "legitimate-prompts", "FUNCTIONAL_FAILURE"),
    ]
    familias = _compute_stats(filas)["by_family"]
    assert set(familias) == {"CHAINED_ATTACK", "CONFUSED_DEPUTY"}
    assert "LLM06" not in familias


def test_el_informe_publica_la_reconciliacion_de_poblaciones():
    filas = [
        _fila("atk_1", "attack-prompts", "SECURITY_BREACH"),
        _fila("navi_1", "navi-prompts", "SECURITY_BREACH", familia="JAILBREAK"),
        _fila("leg_1", "legitimate-prompts", "FUNCTIONAL_FAILURE"),
    ]
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "by_endpoint": {"proxy-full": _compute_stats(filas)},
    })
    assert "procedencia NAVI" in md
    assert "Poblaciones disjuntas" in md
