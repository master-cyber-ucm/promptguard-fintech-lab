"""P10 — un fixture cargado y nunca ejecutado no puede pasar desapercibido.

Once fixtures documentales entraban en `fixture_count: 111` y ningún target del run
aceptaba su modalidad: seis ataques de inyección indirecta y cinco legítimos sobre
documentos benignos que nunca generaron una petición, una sesión ni un error.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.models.capabilities import (
    Applicability,
    Capability,
    FixtureCapabilities,
    Modality,
    ReasonCode,
    audit_coverage,
    capabilities_of_target,
    decide,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from fixture_loader import load_prompts  # noqa: E402
from run_attack_suite import applicable_targets  # noqa: E402

DOC_FIXTURES = ("atk_035", "atk_036", "atk_037", "atk_069", "atk_072", "atk_076",
                "leg_030", "leg_031", "leg_032", "leg_033", "leg_034")

MATRIZ_SIN_DOCUMENTOS = ["simple-prompt", "complex-prompt", "complex-with-context",
                         "proxy-baseline", "proxy-full"]
MATRIZ_COMPLETA = [*MATRIZ_SIN_DOCUMENTOS, "proxy-document-baseline", "proxy-document-full"]


def _doc(fixture_id="atk_035"):
    return {"id": fixture_id, "document": "payload.pdf", "kind": "attack-prompts"}


def _chat(fixture_id="atk_001", steps=1):
    return {"id": fixture_id, "kind": "attack-prompts",
            "rendered_steps": [{"content": "x"}] * steps}


# ── Aplicabilidad por capacidades ────────────────────────────────────────────

def test_un_fixture_documental_necesita_subida_de_documentos():
    necesita = FixtureCapabilities.of(_doc())
    assert necesita.modality == Modality.DOCUMENT
    assert Capability.DOCUMENT_UPLOAD in necesita.required


def test_un_fixture_multi_step_necesita_memoria_entre_turnos():
    assert Capability.MULTI_TURN in FixtureCapabilities.of(_chat(steps=3)).required


def test_un_target_sin_la_capacidad_no_es_aplicable():
    decision = decide(_doc(), "proxy-full")
    assert decision.applicability == Applicability.NOT_APPLICABLE
    assert decision.reason_code == ReasonCode.UNSUPPORTED_MODALITY
    assert not decision.in_population


def test_el_canal_documental_no_atiende_fixtures_sin_documento():
    """Compararlos mediría la diferencia entre dos canales, no la de la defensa."""
    decision = decide(_chat(), "proxy-document-full")
    assert decision.applicability == Applicability.NOT_APPLICABLE
    assert decision.reason_code == ReasonCode.UNSUPPORTED_MODALITY


def test_renombrar_una_ruta_no_cambia_la_aplicabilidad():
    """La decisión depende de capacidades declaradas, no del nombre del endpoint."""
    assert capabilities_of_target("proxy-full").supported == capabilities_of_target(
        "proxy-gatekeeper"
    ).supported
    assert decide(_chat(), "proxy-full").applicability == decide(
        _chat(), "proxy-gatekeeper"
    ).applicability


def test_retirar_una_capacidad_si_cambia_la_aplicabilidad():
    import src.models.capabilities as modulo  # noqa: PLC0415

    original = modulo.TARGET_CAPABILITIES["complex-prompt"]
    try:
        modulo.TARGET_CAPABILITIES["complex-prompt"] = modulo.TargetCapabilities(
            "complex-prompt", (Capability.CHAT,),
        )
        assert decide(_chat(steps=3), "complex-prompt").applicability == Applicability.NOT_APPLICABLE
    finally:
        modulo.TARGET_CAPABILITIES["complex-prompt"] = original


# ── Cobertura cero ───────────────────────────────────────────────────────────

def test_la_matriz_sin_canal_documental_deja_huerfanos_los_once_fixtures():
    fixtures = [f for f in load_prompts(kind=None) if f["id"] in DOC_FIXTURES]
    assert len(fixtures) == len(DOC_FIXTURES), "el catálogo cambió: revisa la lista"
    auditoria = audit_coverage(fixtures, MATRIZ_SIN_DOCUMENTOS)
    assert sorted(auditoria.orphans) == sorted(DOC_FIXTURES)


def test_la_matriz_actual_ejecuta_todos_los_fixtures_cargados():
    """Ningún fixture del catálogo queda sin target aplicable con la matriz por defecto."""
    auditoria = audit_coverage(load_prompts(kind=None), MATRIZ_COMPLETA)
    assert auditoria.orphans == []


def test_la_auditoria_registra_la_razon_por_fixture_y_target():
    auditoria = audit_coverage([_doc()], MATRIZ_SIN_DOCUMENTOS)
    decisiones = auditoria.by_fixture["atk_035"]
    assert {d["applicability"] for d in decisiones} == {"NOT_APPLICABLE"}
    assert {d["reason_code"] for d in decisiones} == {"unsupported_modality"}


def test_no_ejecutarse_nunca_cuenta_como_exclusion():
    """`NOT_APPLICABLE` describe incompatibilidad; `EXCLUDED` exige una decisión."""
    decision = decide(_doc(), "proxy-full")
    assert decision.applicability != Applicability.EXCLUDED
    assert decision.owner is None


def test_una_exclusion_declara_razon_responsable_y_caducidad():
    fixture = {
        **_chat(),
        "excluded_from": {"proxy-full": {
            "reason": "pendiente de rúbrica", "owner": "evaluación",
            "expires": "2026-12-31", "issue": "TFM-123",
        }},
    }
    decision = decide(fixture, "proxy-full")
    assert decision.applicability == Applicability.EXCLUDED
    assert decision.owner == "evaluación"
    assert decision.expires == "2026-12-31"
    assert decision.issue == "TFM-123"
    assert not decision.in_population, "lo excluido sale del denominador"


# ── Documentos benignos ──────────────────────────────────────────────────────

def test_los_documentos_benignos_tambien_se_ejecutan():
    """Sin ellos, una defensa que bloquea todos los adjuntos parecería perfecta."""
    legitimos = [f for f in load_prompts(kind="legitimate-prompts") if f.get("document")]
    assert legitimos, "no hay controles legítimos documentales en el catálogo"
    for fixture in legitimos:
        assert applicable_targets(fixture, {t: "/d" for t in MATRIZ_COMPLETA})


def test_los_ataques_documentales_se_comparan_entre_posturas_del_mismo_pipeline():
    targets = applicable_targets(_doc(), {t: "/d" for t in MATRIZ_COMPLETA})
    assert set(targets) == {"proxy-document-baseline", "proxy-document-full"}


# ── Sin división por cero ────────────────────────────────────────────────────

def test_una_matriz_vacia_no_rompe_la_auditoria():
    auditoria = audit_coverage([_chat()], [])
    assert auditoria.orphans == ["atk_001"]
    assert auditoria.by_fixture["atk_001"] == []
