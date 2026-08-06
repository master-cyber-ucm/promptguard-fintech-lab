"""Contrato de stage genérico del pipeline de defensa PromptGuard.

Decisión aterrizada en el epic "Implementación de proxy base": una clase base común
con `evaluate(ctx) -> PromptDecision` para Input Sanitizer, PII Shield y Output
Auditor. El Tool Gatekeeper es un caso especial aparte — envuelve las tools de
`src/agents/tools.py` vía `RunContext[Deps]` de pydantic-ai, porque las tools se
ejecutan dentro de `agent.run()` y no se pueden interceptar como input/output
genérico. Ver `src/agents/tools.py` (`_owns_account`, `_owns_card`, `Deps`).

Orden del pipeline (propuesta formal, sección 7.2):
    Input Sanitizer -> PII Shield -> Clara (+ Tool Gatekeeper) -> Output Auditor
    -> Compliance Logger

Shadow mode (`SHADOW_MODE=true`): las stages siguen evaluando y registran su
decisión, pero un BLOCK no interrumpe el turno — lo decide `shadow_mode()` en este
módulo, consultado por el orquestador en `api/routes/chat.py`.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.models.interaction import PromptDecision


def shadow_mode() -> bool:
    """`SHADOW_MODE=true` en el entorno: las stages deciden pero no bloquean."""
    return os.environ.get("SHADOW_MODE", "").strip().lower() in ("1", "true", "yes")


@dataclass
class StageContext:
    """Lo mínimo que necesita cualquier stage genérica para evaluar un turno."""

    text: str
    user_id: str
    session_id: str


class Stage(ABC):
    """Contrato común de las stages no-Gatekeeper del pipeline."""

    name: str = "stage"

    @abstractmethod
    def evaluate(self, ctx: StageContext) -> PromptDecision:
        """Evalúa `ctx` y devuelve la decisión. No debe tener efectos secundarios
        sobre la respuesta — el orquestador decide qué hacer con la decisión
        (incluido si aplicarla o solo registrarla, según `shadow_mode()`)."""
        raise NotImplementedError
