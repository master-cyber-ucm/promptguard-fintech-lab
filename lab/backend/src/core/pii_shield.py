"""PII Shield — ESQUELETO no-op.

Mismo tratamiento que `input_sanitizer.py`: placeholder ALLOW que cumple el
contrato de stage para que el pipeline sea ejecutable de punta a punta. La
lógica real (detección/redacción de PII vía `PIIEntity`, ya modelado en
`src/models/banking.py`) vive en su propio epic ("Defensa — PII Harvesting vía
Contexto").
"""

from __future__ import annotations

from .base import Stage, StageContext
from src.models.interaction import PromptDecision


class PIIShieldStage(Stage):
    name = "pii_shield"

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        return PromptDecision(
            action="ALLOW",
            confidence=1.0,
            layer=1,
            reason="esqueleto no-op — lógica real pendiente (epic Defensa — PII Harvesting vía Contexto)",
        )
