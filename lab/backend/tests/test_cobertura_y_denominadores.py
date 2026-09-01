"""P06 — lo que no se pudo medir no puede caerse del denominador.

El informe calculaba sus tasas sobre las ejecuciones que dejaron evidencia evaluable.
Una que fallara, no llegara a lanzarse o no dejara evidencia desaparecía, y el
porcentaje subía sin que nada mejorara.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.coverage import (
    CoverageGates,
    CoverageSummary,
    ExecutionDisposition,
    evaluate_gates,
    wilson_interval,
)
from scripts.report import (
    _build_md,
    _compute_stats,
    causal_comparison,
    coverage_gates,
    coverage_summaries,
    load_ledger,
    load_plan,
)


def _resumen(**kwargs):
    base = {"scope": "proxy-full", "planned": 100, "conclusive": 100, "successes": 80}
    return CoverageSummary(**{**base, **kwargs})


# ── Invariante de reconciliación ─────────────────────────────────────────────

def test_la_poblacion_es_la_suma_exacta_de_los_cuatro_estados():
    resumen = _resumen(planned=100, conclusive=90, inconclusive=6, missing=2, technical_error=2)
    assert resumen.reconciles


def test_una_ejecucion_perdida_rompe_la_reconciliacion():
    resumen = _resumen(planned=100, conclusive=90, inconclusive=5, missing=0, technical_error=0)
    assert not resumen.reconciles
    resultado = evaluate_gates(resumen, CoverageGates())
    assert not resultado.allowed
    assert any("reconciliación" in razon for razon in resultado.blockers)


def test_los_excluidos_salen_de_la_poblacion_y_siguen_visibles():
    resumen = _resumen(planned=90, conclusive=90, excluded=10)
    assert resumen.population == 90
    assert resumen.to_dict()["excluded"] == 10


# ── Tasas y bounds ───────────────────────────────────────────────────────────

def test_la_tasa_conservadora_carga_lo_desconocido_en_contra():
    resumen = _resumen(planned=100, conclusive=80, inconclusive=20, successes=72)
    assert resumen.conservative_rate_pct == 72.0
    assert resumen.conditional_rate_pct == 90.0


def test_los_bounds_reflejan_lo_no_observado():
    resumen = _resumen(planned=100, conclusive=80, inconclusive=15, technical_error=5, successes=72)
    assert resumen.bounds_pct == (72.0, 92.0)


def test_inyectar_inconclusos_mueve_la_tasa_conservadora_sin_borrarlos():
    antes = _resumen(planned=100, conclusive=100, successes=80)
    despues = _resumen(planned=100, conclusive=80, inconclusive=20, successes=80)
    assert antes.conservative_rate_pct == despues.conservative_rate_pct == 80.0
    # La condicional sube porque el denominador encogió: publicarla sola engaña.
    assert despues.conditional_rate_pct == 100.0
    assert despues.bounds_pct == (80.0, 100.0)


def test_el_intervalo_se_comporta_con_n_pequena():
    intervalo = wilson_interval(1, 3)
    assert intervalo is not None
    assert 0.0 <= intervalo[0] < intervalo[1] <= 100.0


def test_sin_ejecuciones_concluyentes_no_hay_intervalo():
    assert _resumen(planned=10, conclusive=0, missing=10, successes=0).confidence_interval_pct is None


# ── Gates ────────────────────────────────────────────────────────────────────

def test_una_ejecucion_ausente_bloquea_el_claim():
    resultado = evaluate_gates(
        _resumen(planned=100, conclusive=99, missing=1, successes=80), CoverageGates()
    )
    assert not resultado.allowed
    assert any("ausentes" in razon for razon in resultado.blockers)


def test_una_cobertura_evaluable_baja_bloquea_el_claim():
    resultado = evaluate_gates(
        _resumen(planned=100, conclusive=90, inconclusive=10, successes=80), CoverageGates()
    )
    assert not resultado.allowed
    assert any("cobertura evaluable" in razon for razon in resultado.blockers)


def test_un_fixture_critico_inconcluso_bloquea_su_ambito():
    resumen = _resumen(planned=100, conclusive=99, inconclusive=1, successes=80,
                       critical_inconclusive=("atk_010",))
    resultado = evaluate_gates(resumen, CoverageGates(min_evaluable_coverage_pct=98.0))
    assert not resultado.allowed
    assert any("atk_010" in razon for razon in resultado.blockers)


def test_una_celda_pequena_suprime_solo_lo_que_la_incluye():
    celdas = [_resumen(scope="a", planned=30), _resumen(scope="b", planned=3)]
    resultado = evaluate_gates(_resumen(), CoverageGates(), cells=celdas)
    assert not resultado.allowed
    assert any("n≥20" in razon for razon in resultado.blockers)


def test_los_umbrales_son_configuracion_versionada_no_constantes_ocultas():
    gates = CoverageGates.from_dict({"min_evaluable_coverage_pct": 50.0, "max_missing": 5})
    assert gates.min_evaluable_coverage_pct == 50.0
    assert gates.max_missing == 5
    resultado = evaluate_gates(
        _resumen(planned=100, conclusive=60, inconclusive=40, successes=50), gates
    )
    assert resultado.allowed


# ── Reconciliación plan ↔ ledger ↔ evaluación ────────────────────────────────

def _run_folder(tmp_path: Path, filas, eventos):
    (tmp_path / "coverage-plan.json").write_text(
        json.dumps({"schema_version": 1, "rows": filas, "gates": CoverageGates().to_dict()}),
        encoding="utf-8",
    )
    (tmp_path / "execution-ledger.jsonl").write_text(
        "\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8",
    )
    return tmp_path


def _fila_plan(exec_id, fixture_id="atk_1", target="proxy-full", severity="HIGH"):
    return {"fixture_execution_id": exec_id, "fixture_id": fixture_id, "target": target,
            "repetition": 1, "severity": severity, "fixture_kind": "attack-prompts"}


def _resultado_eval(exec_id, *, passed=True, inconclusive=False):
    return {
        "fixture_id": "atk_1", "fixture_kind": "attack-prompts", "passed": passed,
        "inconclusive": inconclusive, "result_v2": {"fixture_execution_id": exec_id},
    }


def test_una_ejecucion_sin_evento_terminal_se_cuenta_como_ausente(tmp_path):
    carpeta = _run_folder(
        tmp_path,
        [_fila_plan("e1"), _fila_plan("e2")],
        [{"event": "FINISHED", "fixture_execution_id": "e1", "execution_status": "COMPLETED"}],
    )
    plan, ledger = load_plan(carpeta), load_ledger(carpeta)
    por_target, total = coverage_summaries(plan, ledger, {"proxy-full": [_resultado_eval("e1")]})
    assert total.planned == 2
    assert total.missing == 1
    assert total.conclusive == 1
    assert total.reconciles


def test_un_error_tecnico_se_cuenta_aparte_de_un_inconcluso(tmp_path):
    carpeta = _run_folder(
        tmp_path,
        [_fila_plan("e1"), _fila_plan("e2")],
        [
            {"event": "FINISHED", "fixture_execution_id": "e1", "execution_status": "TECHNICAL_ERROR"},
            {"event": "FINISHED", "fixture_execution_id": "e2", "execution_status": "COMPLETED"},
        ],
    )
    plan, ledger = load_plan(carpeta), load_ledger(carpeta)
    _, total = coverage_summaries(
        plan, ledger, {"proxy-full": [_resultado_eval("e2", passed=False, inconclusive=True)]},
    )
    assert total.technical_error == 1
    assert total.inconclusive == 1
    assert total.conclusive == 0
    assert total.reconciles


def test_un_fixture_critico_inconcluso_se_propaga_al_gate(tmp_path):
    carpeta = _run_folder(
        tmp_path,
        [_fila_plan("e1", severity="CRITICAL")],
        [{"event": "FINISHED", "fixture_execution_id": "e1", "execution_status": "COMPLETED"}],
    )
    plan, ledger = load_plan(carpeta), load_ledger(carpeta)
    por_target, total = coverage_summaries(
        plan, ledger, {"proxy-full": [_resultado_eval("e1", passed=False, inconclusive=True)]},
    )
    gates = coverage_gates(plan, por_target, total)
    assert not gates["run"].allowed
    assert any("atk_1" in razon for razon in gates["run"].blockers)


def test_una_linea_truncada_del_ledger_no_invalida_el_resto(tmp_path):
    (tmp_path / "execution-ledger.jsonl").write_text(
        '{"event": "FINISHED", "fixture_execution_id": "e1"}\n{"event": "FINI',
        encoding="utf-8",
    )
    assert len(load_ledger(tmp_path)) == 1


# ── El claim causal se suprime si la cobertura no llega ──────────────────────

def test_una_cobertura_insuficiente_suprime_la_comparacion_causal():
    from src.models.posture import TargetPosture  # noqa: PLC0415

    invariantes = {"prompt_hash": "a", "context_injection": True, "document_channel": False,
                   "tool_catalog_hash": "b", "policy_hash": "c", "model_config_hash": "d"}
    controles = {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
                 "output_auditor": False, "leak_guard": False, "shadow": False}

    def _postura(target, **extra):
        efectiva = {**controles, **invariantes, **extra, "target": target}
        return TargetPosture(target=target, requested=dict(efectiva), effective=efectiva)

    stats = {
        "proxy-baseline": _compute_stats([]),
        "proxy-full": _compute_stats([]),
    }
    gates = {
        "proxy-baseline": evaluate_gates(
            _resumen(scope="proxy-baseline", planned=10, conclusive=8, missing=2), CoverageGates()
        ),
        "proxy-full": evaluate_gates(
            _resumen(scope="proxy-full", planned=10, conclusive=10), CoverageGates()
        ),
    }
    comparacion = causal_comparison(
        {"proxy-baseline": _postura("proxy-baseline"),
         "proxy-full": _postura("proxy-full", tool_gatekeeper=True)},
        stats, gates,
    )
    assert comparacion["proxy-full"]["comparable"] is False
    assert any("cobertura de `proxy-baseline`" in razon
               for razon in comparacion["proxy-full"]["blockers"])


# ── El informe deja visible que no hay plan ─────────────────────────────────

def test_un_run_sin_plan_se_marca_como_no_comparable():
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "coverage": {"plan_present": False},
        "by_endpoint": {"proxy-full": _compute_stats([])},
    })
    assert "no tiene `coverage-plan.json`" in md


def test_el_informe_publica_numerador_denominador_y_bounds():
    resumen = _resumen(planned=100, conclusive=90, inconclusive=8, missing=1,
                       technical_error=1, successes=72)
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "coverage": {
            "plan_present": True,
            "run": resumen.to_dict(),
            "by_target": {"proxy-full": resumen.to_dict()},
            "gates": {"run": {"scope": "run", "allowed": False,
                              "blockers": ["1 ejecuciones ausentes (máximo 0)"]}},
        },
        "by_endpoint": {"proxy-full": _compute_stats([])},
    })
    assert "## Cobertura" in md
    assert "Claims suprimidos por cobertura insuficiente" in md
    assert "[72.0%, 82.0%]" in md
