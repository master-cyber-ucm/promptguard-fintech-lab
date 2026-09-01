"""P15 — añadir bloqueos rápidos no puede "mejorar" la latencia.

`proxy-full` publicaba p50 ≈ 6,8 s frente a los 7,7 s del baseline y parecía más
rápido. Esa mediana incluía 115 bloqueos pre-modelo de 3–5 ms; sobre las 476 peticiones
que llegaron al modelo, la p50 real era 8,2 s.
"""

from __future__ import annotations

from src.models.latency import (
    LatencyCohort,
    LatencyGates,
    classify_cohort,
    compare_allowed_path,
    percentile,
    summarize,
)


def _obs(cohorte, ms, censored=False):
    return {"cohort": str(cohorte), "latency_ms": ms, "censored": censored}


# ── Clasificación de cohorte ─────────────────────────────────────────────────

def test_un_bloqueo_previo_al_modelo_tiene_su_propia_cohorte():
    assert classify_cohort(model_invoked=False) == LatencyCohort.PRE_MODEL_BLOCK


def test_una_respuesta_servida_sin_tools_es_camino_permitido():
    assert classify_cohort(model_invoked=True) == LatencyCohort.MODEL_PATH_ALLOWED


def test_una_respuesta_con_tools_tiene_su_propia_cohorte():
    assert classify_cohort(model_invoked=True, tools_used=2) == LatencyCohort.TOOL_PATH


def test_un_control_de_salida_que_sustituye_la_respuesta_es_post_modelo():
    assert classify_cohort(model_invoked=True, output_blocked=True) == LatencyCohort.POST_MODEL_BLOCK


def test_un_error_no_contamina_ninguna_cohorte_de_exito():
    assert classify_cohort(model_invoked=True, execution_status="TECHNICAL_ERROR") == LatencyCohort.ERROR


# ── El sesgo del agregado global ─────────────────────────────────────────────

def test_los_bloqueos_rapidos_no_entran_en_el_camino_permitido():
    """El caso del run: 115 bloqueos de 4 ms junto a 476 respuestas de segundos."""
    observaciones = [
        *[_obs(LatencyCohort.PRE_MODEL_BLOCK, 4) for _ in range(115)],
        *[_obs(LatencyCohort.MODEL_PATH_ALLOWED, 8200) for _ in range(476)],
    ]
    resumen = summarize(observaciones)
    # La media global se hunde con los bloqueos rápidos…
    global_media = sum(o["latency_ms"] for o in observaciones) / len(observaciones)
    assert global_media < 8200
    # …pero la cohorte que describe al usuario atendido no se mueve.
    assert resumen["allowed_path"]["p50_ms"] == 8200
    assert resumen["allowed_path"]["mean_ms"] == 8200
    assert resumen["allowed_path"]["n"] == 476


def test_bastantes_bloqueos_rapidos_hunden_incluso_la_mediana_global():
    """Con suficientes fast-blocks, la mediana agregada deja de describir a nadie."""
    observaciones = [
        *[_obs(LatencyCohort.PRE_MODEL_BLOCK, 4) for _ in range(600)],
        *[_obs(LatencyCohort.MODEL_PATH_ALLOWED, 8200) for _ in range(476)],
    ]
    assert percentile([o["latency_ms"] for o in observaciones], 0.50) == 4.0
    assert summarize(observaciones)["allowed_path"]["p50_ms"] == 8200


def test_anadir_mas_bloqueos_rapidos_no_cambia_el_camino_permitido():
    base = [_obs(LatencyCohort.MODEL_PATH_ALLOWED, 9000) for _ in range(20)]
    antes = summarize(base)["allowed_path"]
    despues = summarize(base + [_obs(LatencyCohort.PRE_MODEL_BLOCK, 3) for _ in range(500)])
    assert antes == despues["allowed_path"]


def test_el_camino_permitido_incluye_las_dos_cohortes_atendidas():
    resumen = summarize([
        _obs(LatencyCohort.MODEL_PATH_ALLOWED, 1000),
        _obs(LatencyCohort.TOOL_PATH, 3000),
        _obs(LatencyCohort.PRE_MODEL_BLOCK, 5),
    ])
    assert resumen["allowed_path"]["n"] == 2


# ── Percentiles con n visible ────────────────────────────────────────────────

def test_se_publican_p50_p95_y_p99_no_solo_la_media():
    resumen = summarize([_obs(LatencyCohort.MODEL_PATH_ALLOWED, ms) for ms in range(1, 101)])
    cohorte = resumen["by_cohort"]["MODEL_PATH_ALLOWED"]
    assert cohorte["p50_ms"] and cohorte["p95_ms"] and cohorte["p99_ms"]
    assert cohorte["p95_ms"] > cohorte["p50_ms"]
    assert cohorte["n"] == 100


def test_los_percentiles_salen_de_las_observaciones_reales():
    assert percentile([10.0, 20.0, 30.0], 0.5) == 20.0
    assert percentile([10.0], 0.95) == 10.0
    assert percentile([], 0.5) is None


def test_un_error_conserva_su_duracion_censurada_y_su_tasa():
    resumen = summarize([
        _obs(LatencyCohort.ERROR, 30000, censored=True),
        _obs(LatencyCohort.MODEL_PATH_ALLOWED, 1000),
    ])
    assert resumen["by_cohort"]["ERROR"]["censored"] == 1
    assert resumen["by_cohort"]["ERROR"]["n"] == 1
    assert resumen["allowed_path"]["n"] == 1


# ── Comparación entre posturas ───────────────────────────────────────────────

def _postura(ms_permitido, n=30, bloqueos=0):
    return summarize([
        *[_obs(LatencyCohort.MODEL_PATH_ALLOWED, ms_permitido) for _ in range(n)],
        *[_obs(LatencyCohort.PRE_MODEL_BLOCK, 4) for _ in range(bloqueos)],
    ])


def test_solo_se_comparan_caminos_equivalentes():
    comparacion = compare_allowed_path(_postura(7700), _postura(8200, bloqueos=115))
    assert comparacion["comparable"] is True
    assert comparacion["baseline_p95_ms"] == 7700
    assert comparacion["defended_p95_ms"] == 8200
    assert comparacion["delta_p95_ms"] == 500


def test_una_regresion_grande_dispara_el_gate():
    comparacion = compare_allowed_path(_postura(5000), _postura(20000), LatencyGates())
    assert comparacion["within_gate"] is False


def test_una_penalizacion_dentro_de_la_tolerancia_pasa_el_gate():
    comparacion = compare_allowed_path(_postura(5000), _postura(6500), LatencyGates())
    assert comparacion["within_gate"] is True
    assert comparacion["tolerance_ms"] == 2000.0


def test_sin_observaciones_de_camino_permitido_no_se_compara():
    solo_bloqueos = summarize([_obs(LatencyCohort.PRE_MODEL_BLOCK, 4) for _ in range(50)])
    comparacion = compare_allowed_path(solo_bloqueos, _postura(5000))
    assert comparacion["comparable"] is False


def test_los_umbrales_son_configuracion_versionada():
    gates = LatencyGates(allowed_path_absolute_ms=500, allowed_path_relative_pct=5)
    assert gates.to_dict()["allowed_path_absolute_ms"] == 500
    comparacion = compare_allowed_path(_postura(5000), _postura(6500), gates)
    assert comparacion["within_gate"] is False


# ── El informe lo publica ────────────────────────────────────────────────────

def test_el_informe_publica_la_latencia_por_cohorte():
    from scripts.report import _build_md, _compute_stats  # noqa: PLC0415

    fila = {
        "fixture_id": "atk_1", "fixture_kind": "attack-prompts", "traffic_kind": "ATTACK",
        "attack_family": "DIRECT_INJECTION", "expected_result": "BLOCK",
        "method": "deterministic", "verdict": "BLOCKED", "passed": True, "detail": "",
        "inconclusive": False, "status": "PASS", "disposition": "SECURITY_BLOCK",
        "decision_source": "deterministic", "category": "LLM01", "attack_type": "",
        "severity": "HIGH", "name": "atk_1", "session_file": "x.md", "model": "m",
        "tool_outcomes": {}, "execution_status": "COMPLETED", "result_v2": None,
        "leak_assessments": [],
        "latency": [_obs(LatencyCohort.PRE_MODEL_BLOCK, 4),
                    _obs(LatencyCohort.MODEL_PATH_ALLOWED, 8200)],
    }
    stats = _compute_stats([fila])
    assert stats["summary"]["latency"]["allowed_path"]["n"] == 1

    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "by_endpoint": {"proxy-full": stats},
    })
    assert "Latencia por cohorte" in md
    assert "ALLOWED_PATH" in md
    assert "PRE_MODEL_BLOCK" in md
