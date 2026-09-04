"""P01 — ningún ataque puede evaluarse sin declarar qué puede contenerlo.

`applicable_controls` es lo que impide atribuir una contención a un control que
bloqueó por otro motivo. Si una familia entra en el catálogo de fixtures sin entrada
de rúbrica, la evaluación no puede atribuir nada y el test lo dice aquí, no en el
informe final.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from fixture_loader import load_prompts  # noqa: E402
from security_rubrics import (  # noqa: E402
    KNOWN_CONTROLS,
    RubricError,
    applicable_controls,
    load_catalog,
    missing_families,
    rubric_for,
)


def test_todas_las_familias_de_ataque_estan_en_el_catalogo():
    fixtures = load_prompts(kind=None)
    assert missing_families(fixtures) == []


def test_cada_familia_declara_controles_conocidos_y_rubrica():
    for family, entry in load_catalog()["families"].items():
        assert set(entry["applicable_controls"]) <= KNOWN_CONTROLS, family
        assert entry["rubric"].strip(), family
        assert entry["attacker_goal"].strip(), family


def test_todo_fixture_de_ataque_resuelve_controles_aplicables():
    for fixture in load_prompts(kind=None):
        if fixture.get("kind") == "legitimate-prompts":
            continue
        controles = applicable_controls(fixture)
        assert controles, f"{fixture['id']} sin controles aplicables"
        assert set(controles) <= KNOWN_CONTROLS, fixture["id"]


def test_todo_fixture_de_ataque_tiene_rubrica_de_conducta():
    for fixture in load_prompts(kind=None):
        if fixture.get("kind") == "legitimate-prompts":
            continue
        assert rubric_for(fixture).strip(), f"{fixture['id']} sin rúbrica"


def test_el_fixture_puede_acotar_los_controles_de_su_familia():
    fixture = {
        "id": "atk_x",
        "attack": "LLM02-sensitive-information-disclosure/pii-harvesting",
        "evaluation": {"applicable_controls": ["pii_shield"]},
    }
    assert applicable_controls(fixture) == ["pii_shield"]


def test_un_control_inventado_es_un_error_de_catalogo():
    fixture = {"id": "atk_y", "attack": "_extensiones/jailbreak",
               "evaluation": {"applicable_controls": ["firewall_magico"]}}
    with pytest.raises(RubricError):
        applicable_controls(fixture)


# ── P03: los fixtures no pueden medir intención como si fuera efecto ─────────

def test_ningun_fixture_usa_tool_called_with_como_evidencia_de_brecha():
    """`tool_called_with` cuenta como brecha una llamada pendiente o inválida.

    En el run auditado, 14 de las 26 "brechas" que producía quedaron en
    `pending_confirmation` y al menos 2 eran llamadas sin resultado. Un fixture nuevo
    debe declarar qué acredita: efecto consumado, autorización o mero intento.
    """
    from security_rubrics import legacy_tool_events  # noqa: PLC0415

    culpables = {
        fixture["id"]: legacy_tool_events(fixture)
        for fixture in load_prompts(kind=None)
        if legacy_tool_events(fixture)
    }
    assert culpables == {}
