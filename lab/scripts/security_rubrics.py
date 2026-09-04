"""Catálogo de rúbricas de seguridad por familia de ataque.

Resuelve, para un fixture, qué Componentes pueden contener causalmente su vector y
qué criterio declarativo debe aplicar el juez de conducta. El fixture puede concretar
ambos; si no lo hace, hereda los de su familia.

Vive fuera de los YAML de fixture a propósito: copiar la misma rúbrica en más de cien
ficheros garantiza que se desincronicen, y `applicable_controls` es una afirmación
sobre el catálogo de defensas —deriva de `docs/defensas/README.md`—, no sobre un caso
de prueba concreto.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from lab_paths import find_config  # noqa: E402

CONFIG_FILENAME = "security-rubrics.yaml"

#: Componentes que pueden aparecer en `applicable_controls`. Un nombre fuera de esta
#: lista es un error de catálogo, no un control desconocido tolerable.
KNOWN_CONTROLS = frozenset({
    "input_sanitizer",
    "document_sanitizer",
    "document_structural_detector",
    "pii_shield",
    "tool_gatekeeper",
    "output_auditor",
    "leak_guard",
    "rate_limiter",
    "budget_guard",
})


class RubricError(ValueError):
    """El catálogo o un fixture declaran algo que no se puede aplicar."""


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    path = find_config(CONFIG_FILENAME, env_var="SECURITY_RUBRICS_PATH")
    if path is None:
        raise RubricError(f"no se encontró {CONFIG_FILENAME}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    _validate(data)
    return data


def _validate(data: dict) -> None:
    families = data.get("families") or {}
    if not families:
        raise RubricError("el catálogo de rúbricas está vacío")
    for family, entry in families.items():
        controls = entry.get("applicable_controls") or []
        if not controls:
            raise RubricError(f"{family}: sin applicable_controls")
        unknown = sorted(set(controls) - KNOWN_CONTROLS)
        if unknown:
            raise RubricError(f"{family}: controles desconocidos {unknown}")
        if not (entry.get("rubric") or "").strip():
            raise RubricError(f"{family}: sin rúbrica de conducta")
        if not (entry.get("attacker_goal") or "").strip():
            raise RubricError(f"{family}: sin attacker_goal")


def family_of(fixture: dict) -> str | None:
    """Familia de un fixture: su subcategoría dentro de la taxonomía."""
    attack = fixture.get("attack")
    return str(attack) if attack else None


def entry_for(fixture: dict) -> dict:
    """Entrada del catálogo para el fixture, o `{}` si su familia no está declarada."""
    family = family_of(fixture)
    if not family:
        return {}
    return (load_catalog().get("families") or {}).get(family, {})


def applicable_controls(fixture: dict) -> list[str]:
    """Controles que pueden acreditar la contención de este fixture.

    El fixture manda sobre el catálogo: un caso concreto puede excluir un control que
    su familia sí tiene (por ejemplo, un ataque de fuga que no pasa por tools).
    """
    declared = (fixture.get("evaluation") or {}).get("applicable_controls")
    if declared:
        unknown = sorted(set(declared) - KNOWN_CONTROLS)
        if unknown:
            raise RubricError(f"{fixture.get('id')}: controles desconocidos {unknown}")
        return list(declared)
    return list(entry_for(fixture).get("applicable_controls") or [])


def rubric_for(fixture: dict) -> str:
    """Criterio de conducta que aplica el juez, con el objetivo concreto del fixture."""
    evaluation = fixture.get("evaluation") or {}
    declared = (evaluation.get("fallback") or {}).get("rubric") or evaluation.get("question")
    if declared:
        return str(declared)
    entry = entry_for(fixture)
    if not entry:
        return ""
    goal = (
        evaluation.get("attacker_goal")
        or fixture.get("attacker_goal")
        or entry.get("attacker_goal", "")
    )
    return f"Objetivo del atacante: {goal.strip()}\n\n{entry.get('rubric', '').strip()}"


#: Eventos de tool que miden INTENCIÓN, no efecto. Un fixture de ataque no puede
#: sostener su brecha solo sobre ellos (P03).
LEGACY_TOOL_EVENTS = frozenset({"tool_called_with"})

#: Eventos que sí acreditan un efecto o su ausencia de forma explícita.
TYPED_TOOL_EVENTS = frozenset({
    "tool_effect_committed", "tool_effect_not_committed", "tool_completed_with",
    "tool_denied", "tool_pending_confirmation", "tool_authorized", "tool_result_matches",
})


def legacy_tool_events(fixture: dict) -> list[str]:
    """Eventos de intención usados como evidencia de brecha en este fixture."""
    evaluation = fixture.get("evaluation") or {}
    encontrados = []
    for clave in ("events", "forbidden_events", "breach_events", "hard_events", "required_events"):
        for evento in evaluation.get(clave) or []:
            if isinstance(evento, dict) and evento.get("type") in LEGACY_TOOL_EVENTS:
                encontrados.append(f"{clave}:{evento['type']}")
    return encontrados


def missing_families(fixtures: list[dict]) -> list[str]:
    """Familias de ataque presentes en los fixtures y ausentes del catálogo."""
    families = set(load_catalog().get("families") or {})
    faltan = set()
    for fixture in fixtures:
        if fixture.get("kind") == "legitimate-prompts":
            continue
        family = family_of(fixture)
        if family and family not in families:
            faltan.add(family)
    return sorted(faltan)
