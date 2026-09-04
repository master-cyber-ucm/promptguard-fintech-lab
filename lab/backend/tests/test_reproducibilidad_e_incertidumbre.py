"""P14 — un porcentaje sin `n` ni intervalo no es un resultado.

El manifiesto registraba `defense_version: dev`, sin commit, sin estado del árbol, sin
parámetros del modelo ni versión del juez. Y una familia con 15 observaciones publicaba
«60%» como si fuera comparable con otra cifra cercana.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.models.uncertainty import (
    MIN_INFORMATIVE_N,
    PairedDelta,
    ProportionEstimate,
    is_informative,
    paired_bootstrap,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import provenance  # noqa: E402
from report import _build_md, _compute_stats, family_uncertainty  # noqa: E402


# ── Procedencia ──────────────────────────────────────────────────────────────

def _manifiesto(**overrides):
    base = provenance.build(
        {"model": "qwen2.5:3b", "provider": "ollama"},
        seed=7, repeat=5, judge_bundle={"model": "qwen3.5:9b", "prompt_hash": "abc"},
    )
    for clave, valor in overrides.items():
        base[clave] = {**base.get(clave, {}), **valor}
    return base


def test_el_manifiesto_registra_commit_y_estado_del_arbol():
    git = _manifiesto()["git"]
    assert "commit" in git
    assert isinstance(git["dirty"], bool)
    # Un árbol sucio es un dato, no un detalle: el commit deja de identificar el código.
    assert "dirty_files" in git


def test_el_manifiesto_registra_los_digests_de_lo_que_define_el_experimento():
    artefactos = _manifiesto()["artifacts"]
    for clave in ("system_prompt", "tool_permissions", "security_rubrics", "fixtures",
                  "evaluation_schema", "evaluators"):
        assert artefactos.get(clave), f"falta el digest de {clave}"


def test_el_manifiesto_registra_seed_juez_y_parametros_del_modelo():
    manifiesto = _manifiesto()
    assert manifiesto["execution_design"]["seed"] == 7
    assert manifiesto["judge"]["model"] == "qwen3.5:9b"
    assert manifiesto["target_model"]["max_output_tokens"]


def test_se_declara_que_el_proveedor_no_garantiza_determinismo():
    """Prometerlo sería falso; declararlo permite interpretar la variabilidad."""
    modelo = _manifiesto()["target_model"]
    assert modelo["seed_honored"] is False
    assert "determinismo" in modelo["seed_limitation"]


def test_dos_manifiestos_con_los_mismos_artefactos_comparten_huella():
    assert provenance.fingerprint(_manifiesto()) == provenance.fingerprint(_manifiesto())


def test_cambiar_un_prompt_cambia_la_huella_y_prohibe_agregar():
    a = _manifiesto(git={"dirty": False})
    b = _manifiesto(git={"dirty": False})
    b["artifacts"]["system_prompt"] = "OTRO_DIGEST"
    assert provenance.fingerprint(a) != provenance.fingerprint(b)
    razones = provenance.aggregation_blockers(a, b)
    assert any("system_prompt" in razon for razon in razones)


def test_un_arbol_sucio_impide_agregar_runs():
    a = _manifiesto(git={"dirty": True})
    b = _manifiesto(git={"dirty": True})
    assert any("árbol de trabajo sucio" in razon for razon in provenance.aggregation_blockers(a, b))


def test_dos_runs_identicos_y_limpios_si_pueden_agregarse():
    a = _manifiesto(git={"dirty": False})
    b = _manifiesto(git={"dirty": False})
    assert provenance.aggregation_blockers(a, b) == []


# ── Intervalos ───────────────────────────────────────────────────────────────

def test_una_proporcion_se_publica_con_su_denominador():
    estimacion = ProportionEstimate("CHAINED_ATTACK", 9, 15)
    datos = estimacion.to_dict()
    assert datos["successes"] == 9 and datos["total"] == 15
    assert datos["pct"] == 60.0
    assert datos["ci_pct"] is not None


def test_una_familia_pequena_no_sostiene_una_comparacion():
    """15 observaciones: una sola distinta mueve la cifra 6,7 puntos."""
    pequena = ProportionEstimate("CHAINED_ATTACK", 9, 15)
    grande = ProportionEstimate("DIRECT_INJECTION", 60, 100)
    assert not is_informative(pequena)
    assert is_informative(grande)
    assert pequena.half_width_pct > grande.half_width_pct


def test_el_intervalo_se_estrecha_al_crecer_la_muestra():
    estrecha = ProportionEstimate("x", 60, 100).half_width_pct
    ancha = ProportionEstimate("x", 6, 10).half_width_pct
    assert estrecha < ancha


def test_el_umbral_de_informatividad_esta_declarado():
    assert MIN_INFORMATIVE_N == 20


# ── Bootstrap pareado ────────────────────────────────────────────────────────

def _observaciones(fixtures, repeticiones, valor):
    return {(f"atk_{i}", r): valor for i in range(fixtures) for r in range(repeticiones)}


def test_el_delta_pareado_usa_los_mismos_fixtures_y_repeticiones():
    base = _observaciones(10, 5, True)
    defendido = {clave: False for clave in base}
    delta = paired_bootstrap("baseline→full", base, defendido, iterations=200)
    assert delta.delta_pct == -100.0
    assert delta.observations == 50
    assert delta.clusters == 10
    assert delta.significant


def test_la_unidad_de_remuestreo_es_el_fixture_no_la_fila():
    """Cinco repeticiones del mismo caso están correlacionadas."""
    base = _observaciones(4, 5, True)
    defendido = {clave: False for clave in base}
    delta = paired_bootstrap("x", base, defendido, iterations=200)
    assert delta.resample_unit == "fixture"
    assert delta.clusters == 4
    assert delta.observations == 20


def test_un_delta_nulo_produce_un_intervalo_que_cruza_cero():
    base = {("atk_1", r): (r % 2 == 0) for r in range(6)}
    base.update({("atk_2", r): (r % 2 == 0) for r in range(6)})
    delta = paired_bootstrap("x", base, dict(base), iterations=300)
    assert delta.delta_pct == 0.0
    assert not delta.significant


def test_sin_pares_no_hay_delta():
    delta = paired_bootstrap("x", {("atk_1", 1): True}, {("atk_2", 1): False}, iterations=50)
    assert delta.delta_pct is None
    assert delta.to_dict()["comparable"] is False


def test_un_delta_sin_intervalo_nunca_se_declara_significativo():
    assert PairedDelta(label="x", delta_pct=42.0).significant is False


def test_el_bootstrap_es_reproducible_con_la_misma_semilla():
    base = _observaciones(6, 3, True)
    defendido = {clave: (i % 3 == 0) for i, clave in enumerate(base)}
    a = paired_bootstrap("x", base, defendido, iterations=200, seed=99)
    b = paired_bootstrap("x", base, defendido, iterations=200, seed=99)
    assert a.ci_pct == b.ci_pct


# ── El informe publica ambas cosas ───────────────────────────────────────────

def _fila(fixture_id, familia, passed):
    return {
        "fixture_id": fixture_id, "fixture_kind": "attack-prompts", "traffic_kind": "ATTACK",
        "attack_family": familia, "expected_result": "BLOCK", "method": "deterministic",
        "verdict": "BLOCKED" if passed else "SUCCESS", "passed": passed, "detail": "",
        "inconclusive": False, "status": "PASS" if passed else "FAIL",
        "disposition": "SECURITY_BLOCK", "decision_source": "deterministic",
        "category": "LLM01", "attack_type": "", "severity": "HIGH", "name": fixture_id,
        "session_file": "x.md", "model": "m", "tool_outcomes": {},
        "execution_status": "COMPLETED", "leak_assessments": [], "result_v2": None,
    }


def test_el_informe_publica_n_y_intervalo_por_familia():
    filas = [_fila(f"atk_{i}", "CHAINED_ATTACK", i < 9) for i in range(15)]
    incertidumbre = family_uncertainty(_compute_stats(filas))
    fila = incertidumbre[0]
    assert fila["successes"] == 9 and fila["total"] == 15
    assert fila["informative"] is False


def test_el_markdown_avisa_cuando_no_hay_procedencia():
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "by_endpoint": {"proxy-full": _compute_stats([])},
    })
    assert "no tiene `provenance.json`" in md


def test_el_markdown_publica_procedencia_e_incertidumbre():
    filas = [_fila(f"atk_{i}", "CHAINED_ATTACK", i < 9) for i in range(15)]
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "provenance": _manifiesto(),
        "by_endpoint": {"proxy-full": _compute_stats(filas)},
    })
    assert "## Procedencia del run" in md
    assert "Incertidumbre por familia" in md
    assert "9/15" in md
