"""Reglas declarativas compartidas para detectar prompt injection."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from src.models.interaction import PromptDecision


RULES_PATH = Path(__file__).parent.parent.parent / "config" / "rules" / "injection_signatures.yaml"
_ACTION_ORDER = {"ALLOW": 0, "SUSPICIOUS": 1, "BLOCK": 2}


@lru_cache(maxsize=1)
def load_injection_rules() -> tuple[dict, ...]:
    """Carga una vez las firmas de capa 1 mantenidas en configuración."""
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    return tuple(data["rules"])


def evaluate_injection_rules(text: str, *, conceal_reason: bool = True) -> PromptDecision:
    """Devuelve la coincidencia más restrictiva de las firmas de capa 1."""
    best: PromptDecision | None = None
    for rule in load_injection_rules():
        if not re.search(rule["pattern"], text):
            continue
        candidate = PromptDecision(
            action=rule["action"],
            confidence=1.0,
            layer=1,
            reason=("Patrón de inyección detectado." if conceal_reason else rule["description"]),
            attack_type=("prompt_injection" if conceal_reason else rule["name"]),
            matched_rule=rule["name"],
        )
        if best is None or _ACTION_ORDER[candidate.action] > _ACTION_ORDER[best.action]:
            best = candidate
    return best or PromptDecision(action="ALLOW", confidence=1.0, layer=1)
