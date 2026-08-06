"""Input Sanitizer — ESQUELETO no-op.

Placeholder que cumple el contrato de stage (`evaluate(ctx) -> PromptDecision`,
siempre ALLOW) para que el pipeline del proxy sea ejecutable de punta a punta
desde el día 1. La lógica real de detección de Prompt Injection Directa vive en
su propio epic ("Defensa — Prompt Injection Directa", Input Sanitizer sobre
`layer=2/3`) y sobreescribe únicamente `evaluate()` — no la integración con el
orquestador.

Nota de alcance: la detección de inyección INDIRECTA vía documento adjunto ya
existe y es real (`document_sanitizer.py` + `document_structural_detector.py`),
pero corre en el flujo de `/chat/complex-with-document` antes de llegar aquí,
no como parte de esta stage genérica de texto plano.
"""

from __future__ import annotations

from .base import Stage, StageContext
from src.models.interaction import PromptDecision


class InputSanitizerStage(Stage):
    name = "input_sanitizer"

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        return PromptDecision(
            action="ALLOW",
            confidence=1.0,
            layer=1,
            reason="esqueleto no-op — lógica real pendiente (epic Defensa — Prompt Injection Directa)",
        )
