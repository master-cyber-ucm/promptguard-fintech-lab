"""P27 — «100 %» sobre la mitad de los casos no es un 100 %.

Los fixtures de System Prompt Leakage se enrutan a los endpoints `complex-*` y no todos
llegan a `proxy-full`. El informe agregaba un porcentaje por LLM07 en el proxy que no
representaba la batería completa, y las celdas con guion no explicaban por qué.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.models.claim_registry import (
    ClaimStatus,
    CoverageCell,
    LLM07Subtype,
    classify_llm07,
    evaluate_claim,
)
from scripts.report import _build_md, _compute_stats, category_claims

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from fixture_loader import load_prompts  # noqa: E402


def _celda(scope="proxy-full/LLM07", aplicables=20, ejecutados=10, exitos=10):
    return CoverageCell(scope=scope, applicable=aplicables,
                        executed=ejecutados, successes=exitos)


# ── El caso exacto ───────────────────────────────────────────────────────────

def test_diez_de_veinte_bloqueados_no_es_un_cien_por_cien():
    claim = evaluate_claim(_celda(), statement="LLM07 protegido al 100%")
    assert claim.status == ClaimStatus.SUPPRESSED
    assert "cobertura 10/20 (50.0%)" in claim.blockers[0]
    assert "10/10 bloqueados" in claim.render()
    assert "100%" not in claim.render()


def test_con_la_bateria_completa_el_claim_si_se_publica():
    claim = evaluate_claim(
        _celda(aplicables=20, ejecutados=20, exitos=20),
        statement="LLM07 protegido al 100%",
    )
    assert claim.status == ClaimStatus.PUBLISHED
    assert claim.render() == "LLM07 protegido al 100%"


def test_la_celda_expone_numerador_y_denominador():
    celda = _celda()
    assert celda.coverage_pct == 50.0
    assert celda.conditional_rate_pct == 100.0
    assert celda.to_dict()["applicable"] == 20


def test_sin_ejecuciones_aplicables_no_hay_claim():
    claim = evaluate_claim(CoverageCell(scope="x"), statement="algo")
    assert claim.status == ClaimStatus.SUPPRESSED
    assert "no hay ejecuciones aplicables" in claim.blockers[0]


# ── Subtipos ─────────────────────────────────────────────────────────────────

def test_un_subtipo_bajo_gate_suprime_el_claim_del_ambito():
    claim = evaluate_claim(
        _celda(aplicables=20, ejecutados=20, exitos=20),
        statement="LLM07 protegido",
        subtype_cells=[
            CoverageCell(scope="INSTRUCTION_EXTRACTION", applicable=10, executed=10),
            CoverageCell(scope="PROTECTED_SECRET_LEAK", applicable=10, executed=3),
        ],
    )
    assert claim.status == ClaimStatus.SUPPRESSED
    assert "PROTECTED_SECRET_LEAK" in claim.blockers[0]


def test_reflejar_un_marcador_no_es_lo_mismo_que_filtrar_un_secreto():
    """Agregarlos bajo LLM07 hacía indistinguibles las dos cosas."""
    reflexion = classify_llm07({"evaluation": {"events": [
        {"type": "response_contains", "value": "VULNERABILIDAD"},
    ]}})
    fuga = classify_llm07({"evaluation": {"events": [
        {"type": "response_leaks", "canary": "API_KEY_INTERNAL", "claim_type": "SECRET"},
    ]}})
    assert reflexion == LLM07Subtype.MARKER_REFLECTION
    assert fuga == LLM07Subtype.PROTECTED_SECRET_LEAK


def test_un_fixture_sin_indicadores_de_contenido_es_extraccion_de_instrucciones():
    assert classify_llm07({"evaluation": {}}) == LLM07Subtype.INSTRUCTION_EXTRACTION


def test_los_fixtures_llm07_del_catalogo_se_clasifican_por_subtipo():
    llm07 = [f for f in load_prompts(kind=None) if f.get("category") == "LLM07"]
    assert llm07
    subtipos = {classify_llm07(f) for f in llm07}
    # Tras la migración de P04, la batería mide el valor del canario, no su alias.
    assert LLM07Subtype.PROTECTED_SECRET_LEAK in subtipos


# ── Pares baseline/defendida ────────────────────────────────────────────────

def test_conjuntos_distintos_entre_baseline_y_defendida_suprimen_el_claim():
    claim = evaluate_claim(
        _celda(aplicables=20, ejecutados=20, exitos=20),
        statement="el proxy protege LLM07",
        baseline_keys={"atk_1", "atk_2", "atk_3"},
        defended_keys={"atk_1", "atk_2"},
    )
    assert claim.status == ClaimStatus.SUPPRESSED
    assert "claves pareadas" in claim.blockers[0]


def test_conjuntos_identicos_permiten_el_claim():
    claim = evaluate_claim(
        _celda(aplicables=20, ejecutados=20, exitos=20),
        statement="el proxy protege LLM07",
        baseline_keys={"atk_1", "atk_2"}, defended_keys={"atk_1", "atk_2"},
    )
    assert claim.status == ClaimStatus.PUBLISHED


# ── Integración con el informe ──────────────────────────────────────────────

def _fila(fixture_id, categoria="LLM07", passed=True):
    return {
        "fixture_id": fixture_id, "fixture_kind": "attack-prompts",
        "traffic_kind": "ATTACK", "attack_family": "SYSTEM_PROMPT_LEAKAGE",
        "expected_result": "BLOCK", "method": "deterministic",
        "verdict": "BLOCKED" if passed else "SUCCESS", "passed": passed, "detail": "",
        "inconclusive": False, "status": "PASS" if passed else "FAIL",
        "disposition": "SECURITY_BLOCK", "decision_source": "deterministic",
        "category": categoria, "attack_type": "", "severity": "HIGH", "name": fixture_id,
        "session_file": "x.md", "model": "m", "tool_outcomes": {},
        "execution_status": "COMPLETED", "result_v2": None, "leak_assessments": [],
    }


def _plan(aplicables=20, target="proxy-full"):
    return {"rows": [
        {"fixture_execution_id": f"e{i}", "fixture_id": f"atk_{i}",
         "target": target, "category": "LLM07", "repetition": 1}
        for i in range(aplicables)
    ]}


def test_el_informe_suprime_el_claim_con_cobertura_parcial():
    stats = {"proxy-full": _compute_stats([_fila(f"atk_{i}") for i in range(10)])}
    claims = category_claims(_plan(20), stats)
    datos = claims["proxy-full/LLM07"]
    assert datos["status"] == "SUPPRESSED"
    assert datos["cell"]["applicable"] == 20
    assert datos["cell"]["executed"] == 10


def test_el_informe_publica_el_claim_con_cobertura_completa():
    stats = {"proxy-full": _compute_stats([_fila(f"atk_{i}") for i in range(20)])}
    claims = category_claims(_plan(20), stats)
    assert claims["proxy-full/LLM07"]["status"] == "PUBLISHED"


def test_el_markdown_muestra_ejecutados_sobre_aplicables():
    stats = {"proxy-full": _compute_stats([_fila(f"atk_{i}") for i in range(10)])}
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "category_claims": category_claims(_plan(20), stats),
        "by_endpoint": stats,
    })
    assert "Claims por categoría" in md
    assert "10/20" in md
    assert "claim suprimido" in md


def test_sin_plan_no_se_inventan_claims():
    stats = {"proxy-full": _compute_stats([_fila("atk_1")])}
    assert category_claims({}, stats) == {}
