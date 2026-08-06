"""Output Auditor -- capa de defensa determinista para LLM07 (System Prompt Leakage).

Escanea la respuesta final del modelo antes de entregarla al cliente, en busca de
patrones de secretos de configuracion conocidos embebidos en el system prompt del
laboratorio (API key interna, host de base de datos, bucket S3). Si detecta una
coincidencia, sustituye la respuesta completa por un mensaje generico.

Deliberadamente NO intenta detectar "intencion sospechosa" en el prompt de entrada:
esa aproximacion (bloqueo semantico sobre el texto de entrada) genero falsos
positivos sobre peticiones legitimas en otras pruebas del equipo. Esta capa actua
solo sobre la salida, contra patrones conocidos y verificables, para mantener la
tasa de falsos positivos en 0% sobre trafico legitimo.
"""

from __future__ import annotations

import re

from .base import Stage, StageContext
from src.models.interaction import PromptDecision

_SECRET_PATTERNS = [
    re.compile(r"pg_internal_sk_[a-zA-Z0-9]+"),
    re.compile(r"db-banking\.internal\.verdabank\.es"),
    re.compile(r"s3://verdabank-audit-logs-prod\S*"),
]

_GENERIC_REFUSAL = "No puedo compartir esa informacion."


def audit_response(text: str) -> tuple[str, bool]:
    """Escanea `text` en busca de secretos conocidos.

    Devuelve (texto_final, fuga_detectada). Si fuga_detectada es True, `texto_final`
    ya es el mensaje generico de sustitucion, no el original.
    """
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            return _GENERIC_REFUSAL, True
    return text, False


class OutputAuditorStage(Stage):
    """Envoltorio de `audit_response()` sobre el contrato de stage genérico.

    `audit_response()` sigue siendo la función usada directamente en
    `api/routes/chat.py` para todos los endpoints (comportamiento sin cambios);
    esta clase existe para que el orquestador del proxy (`/chat/proxy`) pueda
    tratar el Output Auditor como una stage más del pipeline, junto a Input
    Sanitizer y PII Shield.
    """

    name = "output_auditor"

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        _, leaked = audit_response(ctx.text)
        return PromptDecision(
            action="BLOCK" if leaked else "ALLOW",
            confidence=1.0,
            layer=1,
            reason="secreto de configuración conocido en la respuesta" if leaked else None,
            attack_type="system_prompt_leakage" if leaked else None,
            matched_rule="output_auditor" if leaked else None,
        )
