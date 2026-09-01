"""P02 — el informe no publica un delta cuando la comparación no es causal."""

from __future__ import annotations

from src.models.posture import TargetPosture
from scripts.report import _build_md, _compute_stats, causal_comparison

_INVARIANTES = {
    "prompt_hash": "aaaa", "context_injection": True, "document_channel": False,
    "tool_catalog_hash": "bbbb", "policy_hash": "cccc", "model_config_hash": "dddd",
}


def _postura(target, **controles):
    base = {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
            "output_auditor": False, "leak_guard": False, "shadow": False}
    efectiva = {**base, **_INVARIANTES, **controles, "target": target}
    return TargetPosture(target=target, requested=dict(efectiva), effective=efectiva)


def _resultados(vulnerables: int, contenidos: int):
    filas = []
    for i in range(vulnerables):
        filas.append(_fila(f"atk_v{i}", "VULNERABLE", "HARMFUL_EFFECT_OBSERVED"))
    for i in range(contenidos):
        filas.append(_fila(f"atk_c{i}", "INFRASTRUCTURE_CONTAINED", "NO_HARMFUL_EFFECT_OBSERVED"))
    return filas


def _fila(fixture_id, system_result, effect):
    contenido = system_result != "VULNERABLE"
    return {
        "fixture_id": fixture_id, "fixture_kind": "attack-prompts",
        "expected_result": "BLOCK", "method": "deterministic",
        "verdict": "BLOCKED" if contenido else "SUCCESS", "passed": contenido,
        "detail": "", "inconclusive": False, "status": "PASS" if contenido else "FAIL",
        "disposition": "SECURITY_BLOCK" if contenido else "SECURITY_BREACH",
        "decision_source": "deterministic", "category": "LLM01",
        "attack_type": "prompt_injection", "severity": "HIGH", "name": fixture_id,
        "session_file": "x.md", "model": "qwen2.5:3b", "tool_outcomes": {},
        "execution_status": "COMPLETED",
        "result_v2": {
            "system_result": system_result, "effect_outcome": effect,
            "model_behavior": "UNKNOWN",
            "defense": {"detected": contenido, "intervened": contenido,
                        "contained": system_result == "INFRASTRUCTURE_CONTAINED",
                        "primary_attribution": "tool_gatekeeper" if contenido else None},
        },
    }


def _stats():
    return {
        "proxy-baseline": _compute_stats(_resultados(8, 2)),
        "proxy-full": _compute_stats(_resultados(2, 8)),
        "complex-with-context": _compute_stats(_resultados(9, 1)),
    }


def test_dos_posturas_del_mismo_agente_producen_arr_y_rrr():
    posturas = {
        "proxy-baseline": _postura("proxy-baseline"),
        "proxy-full": _postura("proxy-full", input_sanitizer=True, pii_shield=True,
                               tool_gatekeeper=True, output_auditor=True, leak_guard=True),
    }
    comparacion = causal_comparison(posturas, _stats())["proxy-full"]
    assert comparacion["comparable"] is True
    assert comparacion["baseline_vulnerable_rate"] == 80.0
    assert comparacion["defended_vulnerable_rate"] == 20.0
    assert comparacion["absolute_risk_reduction"] == 60.0
    assert comparacion["relative_risk_reduction"] == 75.0


def test_un_endpoint_pedagogico_no_aparece_como_postura_comparable():
    posturas = {
        "proxy-baseline": _postura("proxy-baseline"),
        "complex-with-context": _postura("complex-with-context"),
    }
    comparacion = causal_comparison(posturas, _stats())
    assert "complex-with-context" not in comparacion


def test_una_linea_base_contaminada_suprime_el_delta():
    posturas = {
        "proxy-baseline": _postura("proxy-baseline", output_auditor=True),
        "proxy-full": _postura("proxy-full", tool_gatekeeper=True, output_auditor=True),
    }
    comparacion = causal_comparison(posturas, _stats())["proxy-full"]
    assert comparacion["comparable"] is False
    assert any("no es pura" in razon for razon in comparacion["blockers"])
    assert "absolute_risk_reduction" not in comparacion


def test_un_prompt_distinto_suprime_el_delta():
    baseline = _postura("proxy-baseline")
    defended = _postura("proxy-full", tool_gatekeeper=True)
    defended.effective["prompt_hash"] = "OTRO"
    comparacion = causal_comparison({"proxy-baseline": baseline, "proxy-full": defended}, _stats())
    assert comparacion["proxy-full"]["comparable"] is False


def test_sin_postura_registrada_no_se_afirma_nada():
    comparacion = causal_comparison({}, _stats())["proxy-full"]
    assert comparacion["comparable"] is False
    assert "postura efectiva no registrada" in comparacion["blockers"][0]


def test_el_markdown_explica_por_que_suprime_una_comparacion():
    posturas = {
        "proxy-baseline": _postura("proxy-baseline", output_auditor=True),
        "proxy-full": _postura("proxy-full", tool_gatekeeper=True, output_auditor=True),
    }
    stats = _stats()
    run_data = {
        "run_timestamp": "2026-08-31T00:00:00Z", "model": "qwen2.5:3b",
        "model_provenance": {"requested_model": "qwen2.5:3b", "provider": "ollama",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["complex-with-context", "proxy-baseline", "proxy-full"],
        "suite_config": {},
        "causal_comparison": causal_comparison(posturas, stats),
        "by_endpoint": stats,
    }
    md = _build_md(run_data)
    assert "Comparación causal frente a `proxy-baseline`" in md
    assert "Comparaciones suprimidas y por qué" in md
    assert "Endpoints pedagógicos" in md
