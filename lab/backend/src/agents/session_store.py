"""Almacén en memoria del historial de conversación por sesión.

Cada sesión guarda la lista de `ModelMessage` que Clara ha intercambiado.
La clave es el `session_id` que viaja en el ChatRequest: si el cliente no lo
envía, el backend crea una sesión nueva y devuelve su id de referencia en la
respuesta para que el cliente pueda seguir la conversación.

La memoria es simple y volátil: vive mientras el backend esté levantado.

Denegación de Servicio (#8, LLM10:2025) — "Sesiones sin cota": antes de esto, `_store`
crecía sin límite de entradas ni expiración; cada `session_id` nuevo (trivial de generar
— basta con omitirlo) era memoria retenida indefinidamente. Ver
docs/defensas/LLM10-unbounded-consumption/denegacion-de-servicio.md §3.3. Cota LRU +
TTL por inactividad — ninguno de los dos cambia el comportamiento para tráfico
legítimo: una conversación normal no se acerca a ninguno de los dos límites.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import OrderedDict

from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

# Turnos de conversación retenidos por sesión. Cada turno es un step del
# fixture; los fixtures multi-step de la librería no superan 3 pasos.
MAX_TURNS = 20

# Cota de sesiones vivas simultáneas (LRU: la menos usada recientemente se libera
# primero) y TTL por inactividad — ambos configurables porque el valor correcto
# depende de la memoria disponible del contenedor y del patrón de tráfico real.
MAX_SESSIONS = int(os.environ.get("SESSION_STORE_MAX_SESSIONS", 1000))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_STORE_TTL_SECONDS", 1800))  # 30 min

# OrderedDict para poder desalojar por LRU (`move_to_end` en cada acceso) — la entrada
# al principio es siempre la menos usada recientemente.
_store: "OrderedDict[str, tuple[list[ModelMessage], float]]" = OrderedDict()
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


def _purge_expired_locked() -> None:
    """Libera las sesiones cuya última actividad superó el TTL. Debe llamarse con
    `_lock` ya adquirido."""
    if not SESSION_TTL_SECONDS:
        return
    limite = time.time() - SESSION_TTL_SECONDS
    expiradas = [sid for sid, (_, last_seen) in _store.items() if last_seen < limite]
    for sid in expiradas:
        del _store[sid]


def get_history(session_id: str) -> list[ModelMessage]:
    """Devuelve una copia del historial de la sesión (vacío si no existe o expiró)."""
    with _lock:
        _purge_expired_locked()
        entrada = _store.get(session_id)
        if entrada is None:
            return []
        messages, _ = entrada
        _store[session_id] = (messages, time.time())  # toca la sesión: sigue viva
        _store.move_to_end(session_id)
        return list(messages)


def store_history(session_id: str, messages: list[ModelMessage]) -> None:
    """Persiste el historial completo de la sesión, recortado a MAX_TURNS.

    Aplica la cota LRU y el TTL antes de insertar — una sesión nueva nunca hace crecer
    `_store` más allá de `MAX_SESSIONS`: si ya está al límite, se desaloja la entrada
    menos usada recientemente antes de admitir la nueva.
    """
    trimmed = trim_history(messages)
    with _lock:
        _purge_expired_locked()
        if session_id not in _store and len(_store) >= MAX_SESSIONS:
            _store.popitem(last=False)  # desaloja la LRU (la primera del OrderedDict)
        _store[session_id] = (trimmed, time.time())
        _store.move_to_end(session_id)


def session_count() -> int:
    """Número de sesiones vivas — expuesto para tests y observabilidad, no para lógica
    de negocio."""
    with _lock:
        return len(_store)


def clear_all() -> None:
    """Vacía el almacén — usado por los tests para no compartir estado entre casos."""
    with _lock:
        _store.clear()
