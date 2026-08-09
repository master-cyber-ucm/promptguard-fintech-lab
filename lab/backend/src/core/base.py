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
from typing import Any

from src.models.interaction import PromptDecision


def shadow_mode() -> bool:
    """`SHADOW_MODE=true` en el entorno: las stages deciden pero no bloquean."""
    return os.environ.get("SHADOW_MODE", "").strip().lower() in ("1", "true", "yes")


@dataclass
class StageContext:
    """Lo mínimo que necesita cualquier stage genérica para evaluar un turno.

    `collector` es el `SocCollector` del turno (ver src/soc/collector.py). El
    orquestador ya emite un Analysis Event con la decisión final de cada stage, así que
    una stage no necesita tocarlo para que su decisión quede registrada. Está aquí para
    las que tengan algo MÁS que contar: cuando el Input Sanitizer real aterrice con sus
    tres capas (regex → clasificador → LLM guard), podrá emitir el detalle de cada una
    sin que haya que cambiar el contrato ni el orquestador.

    Se tipa como `Any` a propósito: `core` no debe importar de `soc`. La observabilidad
    depende de la defensa, nunca al revés.
    """

    text: str
    user_id: str
    session_id: str
    collector: Any = None


class Stage(ABC):
    """Contrato común de las stages no-Gatekeeper del pipeline."""

    name: str = "stage"

    @abstractmethod
    def evaluate(self, ctx: StageContext) -> PromptDecision:
        """Evalúa `ctx` y devuelve la decisión. No debe tener efectos secundarios
        sobre la respuesta — el orquestador decide qué hacer con la decisión
        (incluido si aplicarla o solo registrarla, según `shadow_mode()`)."""
        raise NotImplementedError
