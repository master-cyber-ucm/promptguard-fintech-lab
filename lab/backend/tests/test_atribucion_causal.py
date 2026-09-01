"""P13 — quién impidió el efecto, no quién dejó un log.

Sumar «intervenciones por componente» duplicaba sesiones: una ejecución atraviesa
varios controles. Y un `BLOCK` posterior a un commit deja un log idéntico al de una
prevención real.
"""

from __future__ import annotations

from src.models.causal_attribution import (
    AttributionConfidence,
    BlockPhase,
    attribute,
    marginal_contribution,
)
from src.models.evaluation import DefenseEvent, Enforcement


def _ev(component, action, seq, *, enforcement=Enforcement.ENFORCED):
    return DefenseEvent(event_id=f"ev-{component}-{seq}", component=component,
                        target="prompt", action=action, enforcement=enforcement, sequence=seq)


# ── Primera capa efectiva ────────────────────────────────────────────────────

def test_la_primera_intervencion_aplicable_recibe_el_credito_primario():
    atribucion = attribute(
        [_ev("input_sanitizer", "BLOCK", 1), _ev("tool_gatekeeper", "DENY", 5)],
        applicable_controls=["input_sanitizer", "tool_gatekeeper"],
    )
    assert atribucion.first_effective_blocker == "input_sanitizer"
    assert atribucion.contributing_components == ("tool_gatekeeper",)
    assert atribucion.confidence == AttributionConfidence.ATTRIBUTED


def test_dos_defensas_conservan_ambas_sin_duplicar_la_ejecucion():
    atribucion = attribute(
        [_ev("pii_shield", "REDACT", 2), _ev("leak_guard", "BLOCK", 4)],
        applicable_controls=["pii_shield", "leak_guard"],
    )
    assert atribucion.first_effective_blocker == "pii_shield"
    assert "leak_guard" in atribucion.contributing_components
    # La ejecución sigue siendo una: el crédito primario es de un solo componente.
    assert len({atribucion.first_effective_blocker, *atribucion.contributing_components}) == 2


def test_intervenciones_simultaneas_no_reciben_credito_primario():
    """Elegir una sería inventar una precedencia que la evidencia no da."""
    atribucion = attribute(
        [_ev("input_sanitizer", "BLOCK", 3), _ev("pii_shield", "BLOCK", 3)],
        applicable_controls=["input_sanitizer", "pii_shield"],
    )
    assert atribucion.confidence == AttributionConfidence.MULTIPLE_OR_UNKNOWN
    assert atribucion.first_effective_blocker is None
    assert set(atribucion.contributing_components) == {"input_sanitizer", "pii_shield"}


# ── Detección, shadow y allow nunca contienen ────────────────────────────────

def test_una_deteccion_sin_intervencion_no_recibe_credito():
    atribucion = attribute([_ev("pii_shield", "SUSPICIOUS", 1)],
                           applicable_controls=["pii_shield"])
    assert atribucion.first_effective_blocker is None
    assert atribucion.detected_only == ("pii_shield",)
    assert atribucion.confidence == AttributionConfidence.NOT_ATTRIBUTED


def test_una_decision_en_shadow_no_recibe_credito():
    atribucion = attribute(
        [_ev("input_sanitizer", "BLOCK", 1, enforcement=Enforcement.SHADOW)],
        applicable_controls=["input_sanitizer"],
    )
    assert atribucion.first_effective_blocker is None
    assert atribucion.detected_only == ("input_sanitizer",)


def test_un_allow_no_aparece_en_ninguna_columna():
    atribucion = attribute([_ev("output_auditor", "ALLOW", 1)],
                           applicable_controls=["output_auditor"])
    assert atribucion.detected_only == ()
    assert atribucion.contributing_components == ()


def test_sin_intervencion_la_ausencia_de_dano_no_acredita_a_nadie():
    atribucion = attribute([], applicable_controls=["input_sanitizer"])
    assert atribucion.confidence == AttributionConfidence.NOT_ATTRIBUTED
    assert "no acredita a nadie" in atribucion.notes[0]


# ── Bloqueo tardío ───────────────────────────────────────────────────────────

def test_un_bloqueo_posterior_al_efecto_no_es_prevencion():
    atribucion = attribute(
        [_ev("output_auditor", "BLOCK", 9)],
        applicable_controls=["output_auditor"],
        effect_observed=True,
        effect_sequence=4,
    )
    assert atribucion.phase == BlockPhase.LATE
    assert atribucion.confidence == AttributionConfidence.NOT_ATTRIBUTED
    assert atribucion.first_effective_blocker is None


def test_un_efecto_lateral_consumado_antes_del_block_no_se_borra():
    atribucion = attribute(
        [_ev("tool_gatekeeper", "DENY", 2), _ev("output_auditor", "BLOCK", 8)],
        applicable_controls=["tool_gatekeeper", "output_auditor"],
        effect_observed=True,
        effect_sequence=5,
    )
    assert atribucion.confidence == AttributionConfidence.NOT_ATTRIBUTED
    assert "se consumó" in atribucion.notes[0]


def test_una_intervencion_previa_al_punto_de_efecto_si_es_preventiva():
    atribucion = attribute(
        [_ev("tool_gatekeeper", "DENY", 2)],
        applicable_controls=["tool_gatekeeper"],
        effect_sequence=5,
    )
    assert atribucion.phase == BlockPhase.PREVENTIVE
    assert atribucion.first_effective_blocker == "tool_gatekeeper"


def test_un_control_no_aplicable_no_recibe_credito():
    """Un rate limiter que corta durante un ataque de fuga no contuvo ese vector."""
    atribucion = attribute([_ev("rate_limiter", "BLOCK", 1)],
                           applicable_controls=["pii_shield"])
    assert atribucion.first_effective_blocker is None


# ── Contribución marginal ────────────────────────────────────────────────────

def test_la_contribucion_marginal_se_calcula_caso_por_caso():
    sin = {("atk_1",): True, ("atk_2",): True, ("atk_3",): False}
    con = {("atk_1",): False, ("atk_2",): True, ("atk_3",): False}
    contribucion = marginal_contribution("tool_gatekeeper", sin, con)
    assert contribucion.paired_cases == 3
    assert contribucion.prevented == 1
    assert contribucion.no_change == 2
    assert contribucion.marginal_pct == 33.3


def test_una_regresion_resta_en_la_contribucion_marginal():
    sin = {("atk_1",): False}
    con = {("atk_1",): True}
    contribucion = marginal_contribution("output_auditor", sin, con)
    assert contribucion.caused_regression == 1
    assert contribucion.marginal_pct == -100.0


def test_sin_pares_no_se_publica_porcentaje_causal():
    """Restar tasas de poblaciones distintas es exactamente lo que esto evita."""
    contribucion = marginal_contribution("pii_shield", {("atk_1",): True}, {("atk_2",): False})
    assert contribucion.comparable is False
    assert contribucion.to_dict()["marginal_pct"] is None


def test_un_caso_sin_pareja_invalida_la_comparacion_completa():
    sin = {("atk_1",): True, ("atk_2",): True}
    con = {("atk_1",): False}
    contribucion = marginal_contribution("pii_shield", sin, con)
    assert contribucion.paired_cases == 1
    assert contribucion.unpaired == ["('atk_2',)"]
    assert contribucion.comparable is False


# ── El informe separa las tres cantidades ────────────────────────────────────

def test_el_informe_publica_deteccion_intervencion_y_contencion_por_separado():
    from scripts.report import _build_md, _compute_stats  # noqa: PLC0415

    def _fila(fixture_id, atribucion):
        return {
            "fixture_id": fixture_id, "fixture_kind": "attack-prompts",
            "traffic_kind": "ATTACK", "attack_family": "DIRECT_INJECTION",
            "expected_result": "BLOCK", "method": "deterministic", "verdict": "BLOCKED",
            "passed": True, "detail": "", "inconclusive": False, "status": "PASS",
            "disposition": "SECURITY_BLOCK", "decision_source": "deterministic",
            "category": "LLM01", "attack_type": "", "severity": "HIGH", "name": fixture_id,
            "session_file": "x.md", "model": "m", "tool_outcomes": {},
            "execution_status": "COMPLETED", "leak_assessments": [],
            "result_v2": {
                "system_result": "INFRASTRUCTURE_CONTAINED",
                "effect_outcome": "NO_HARMFUL_EFFECT_OBSERVED",
                "model_behavior": "UNKNOWN",
                "defense": {"detected": True, "intervened": True, "contained": True,
                            "primary_attribution": atribucion.get("first_effective_blocker")},
                "attribution": atribucion,
            },
        }

    filas = [
        _fila("atk_1", {"first_effective_blocker": "input_sanitizer",
                        "contributing_components": ["tool_gatekeeper"],
                        "detected_only": ["pii_shield"], "phase": "PREVENTIVE"}),
        _fila("atk_2", {"first_effective_blocker": "input_sanitizer",
                        "contributing_components": [], "detected_only": [],
                        "phase": "PREVENTIVE"}),
    ]
    stats = _compute_stats(filas)
    por_componente = stats["summary"]["attribution_by_component"]
    assert por_componente["input_sanitizer"] == {"detected": 2, "intervened": 2, "contained": 2}
    assert por_componente["tool_gatekeeper"] == {"detected": 1, "intervened": 1, "contained": 0}
    assert por_componente["pii_shield"] == {"detected": 1, "intervened": 0, "contained": 0}

    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["proxy-full"], "suite_config": {},
        "by_endpoint": {"proxy-full": stats},
    })
    assert "Detección, intervención y contención por componente" in md
    assert "Contribución marginal por control" in md
    assert "no puede publicarse una contribución marginal" in md
