"""Almacén en memoria del historial de conversación por sesión.

Cada sesión guarda la lista de `ModelMessage` que Clara ha intercambiado.
La clave es el `session_id` que viaja en el ChatRequest: si el cliente no lo
envía, el backend crea una sesión nueva y devuelve su id de referencia en la
respuesta para que el cliente pueda seguir la conversación.

La memoria es simple y volátil: vive mientras el backend esté levantado.
"""

from __future__ import annotations

import threading
import time
import uuid

from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

# Turnos de conversación retenidos por sesión. Cada turno es un step del
# fixture; los fixtures multi-step de la librería no superan 3 pasos.
MAX_TURNS = 20

_store: dict[str, list[ModelMessage]] = {}
_lock = threading.Lock()


def new_session_id() -> str:
    """Genera un id de sesión nuevo para una conversación que empieza."""
    return f"ses_{uuid.uuid4().hex[:12]}_{int(time.time())}"


def _user_prompt_indices(messages: list[ModelMessage]) -> list[int]:
    return [
        i
        for i, m in enumerate(messages)
        if isinstance(m, ModelRequest)
        and any(isinstance(p, UserPromptPart) for p in m.parts)
    ]


def trim_history(
    messages: list[ModelMessage], max_turns: int = MAX_TURNS
) -> list[ModelMessage]:
    """Mantiene solo los últimos `max_turns` turnos completos.

    Cada turno empieza con un user prompt, así que cortar por su índice nunca
    parte por la mitad una respuesta o un ciclo de tools.
    """
    indices = _user_prompt_indices(messages)
    if len(indices) <= max_turns:
        return messages
    return messages[indices[-max_turns]:]


def get_history(session_id: str) -> list[ModelMessage]:
    """Devuelve una copia del historial de la sesión (vacío si no existe)."""
    with _lock:
        return list(_store.get(session_id, []))


def store_history(session_id: str, messages: list[ModelMessage]) -> None:
    """Persiste el historial completo de la sesión, recortado a MAX_TURNS."""
    trimmed = trim_history(messages)
    with _lock:
        _store[session_id] = trimmed
