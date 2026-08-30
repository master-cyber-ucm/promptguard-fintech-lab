"""Capa 1 del Input Sanitizer para prompt injection directa.

Aplica las firmas declarativas de ``injection_signatures.yaml`` al turno actual
y a una ventana acotada de mensajes seguros de la misma sesión. Es una capa de
reducción de riesgo: la garantía determinista sigue estando en Tool Gatekeeper
y Output Auditor.
"""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from collections import deque

from src.models.interaction import PromptDecision

from .base import Stage, StageContext
from .injection_rules import evaluate_injection_rules


_INVISIBLE_CHARS = "\u200b\u200c\u200d\ufeff"
_BASE64_TOKEN = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{20,}={0,2}(?![A-Za-z0-9+/=])")


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.translate({ord(character): None for character in _INVISIBLE_CHARS})
    return re.sub(r"\s+", " ", text).strip()


def _decode_base64_layers(text: str, max_layers: int = 3) -> str:
    """Extrae texto Base64 imprimible para volver a aplicar las mismas firmas."""
    decoded_texts: list[str] = []
    pending = [text]
    for _ in range(max_layers):
        next_layer: list[str] = []
        for candidate in pending:
            for token in _BASE64_TOKEN.findall(candidate):
                try:
                    decoded = base64.b64decode(token, validate=True).decode("utf-8")
                except (ValueError, binascii.Error, UnicodeDecodeError):
                    continue
                if decoded.isprintable() or any(character.isspace() for character in decoded):
                    decoded = _normalise(decoded)
                    decoded_texts.append(decoded)
                    next_layer.append(decoded)
        pending = next_layer
        if not pending:
            break
    return "\n".join(decoded_texts)


class InputSanitizerStage(Stage):
    name = "input_sanitizer"

    def __init__(self, history_size: int = 5):
        self._histories: dict[str, deque[str]] = {}
        self._history_size = history_size

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        history = self._histories.setdefault(ctx.session_id, deque(maxlen=self._history_size))
        current = _normalise(ctx.text)
        text_to_evaluate = "\n".join((*history, current))
        decoded = _decode_base64_layers(text_to_evaluate)
        decision = evaluate_injection_rules(
            f"{text_to_evaluate}\n{decoded}" if decoded else text_to_evaluate,
            channel="chat",
        )

        # Un turno bloqueado no se conserva: no debe permanecer activo en el contexto.
        if decision.action != "BLOCK":
            history.append(current)
        return decision
