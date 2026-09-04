"""Almacén del historial de conversación, con la sesión vinculada a su dueño.

P17: el store indexaba por `session_id` y `chat.py` recuperaba el historial en cuanto
el cliente aportaba ese ID. Un identificador filtrado o adivinado bastaba para reutilizar
el contexto de otra persona, contaminar su conversación o inducir fugas entre
identidades — y una defensa de salida que actúa al final no cierra ese vector, porque
el historial ajeno ya influyó en el prompt y en las tool calls.

Ahora la clave interna es `(tenant_id, owner_subject, session_id)`. Un `session_id`
correcto bajo otro Principal simplemente no existe: no se carga ni un mensaje.

La memoria sigue siendo volátil y acotada (LRU + TTL) por el ataque #8 de LLM10:2025 —
antes `_store` crecía sin límite y cada `session_id` nuevo era memoria retenida. Ver
docs/defensas/LLM10-unbounded-consumption/denegacion-de-servicio.md §3.3.
"""

from __future__ import annotations

import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field

from pydantic_ai.messages import ModelMessage, ModelRequest, UserPromptPart

# Turnos de conversación retenidos por sesión. Cada turno es un step del
# fixture; los fixtures multi-step de la librería no superan 3 pasos.
MAX_TURNS = 20

# Cota de sesiones vivas simultáneas (LRU: la menos usada recientemente se libera
# primero) y TTL por inactividad — ambos configurables porque el valor correcto
# depende de la memoria disponible del contenedor y del patrón de tráfico real.
MAX_SESSIONS = int(os.environ.get("SESSION_STORE_MAX_SESSIONS", 1000))
SESSION_TTL_SECONDS = int(os.environ.get("SESSION_STORE_TTL_SECONDS", 1800))  # 30 min


class SessionOwnershipError(PermissionError):
    """Se pidió una sesión que no pertenece al Principal. No revela si existe."""


@dataclass
class SessionRecord:
    """Sesión con su dueño. El ID público localiza; el owner autoriza."""

    session_id: str
    owner_subject: str
    tenant_id: str
    messages: list[ModelMessage] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    revoked: bool = False
    #: Compare-and-set: dos workers concurrentes no pueden pisarse en silencio.
    version: int = 0
    #: Estado de riesgo acumulado (P22). Vive en el mismo boundary de ownership que
    #: el historial: expirar la sesión no puede dejar el riesgo huérfano.
    security_state: dict = field(default_factory=dict)


# OrderedDict para poder desalojar por LRU (`move_to_end` en cada acceso) — la entrada
# al principio es siempre la menos usada recientemente.
_store: "OrderedDict[tuple[str, str, str], SessionRecord]" = OrderedDict()
_lock = threading.Lock()

#: Intentos de abrir una sesión ajena. Es una señal de seguridad, no un error de uso.
_cross_access_attempts: list[dict] = []


def new_session_id() -> str:
    """Identificador público de alta entropía. No concede acceso por sí solo."""
    return f"ses_{uuid.uuid4().hex[:24]}_{int(time.time())}"


def _key(principal, session_id: str) -> tuple[str, str, str]:
    return (
        getattr(principal, "tenant_id", "verdabank"),
        getattr(principal, "subject", str(principal)),
        session_id,
    )


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
    `_lock` ya adquirido. Expirar borra historial y estado de riesgo a la vez: son
    del mismo dueño y del mismo ciclo de vida."""
    if not SESSION_TTL_SECONDS:
        return
    limite = time.time() - SESSION_TTL_SECONDS
    expiradas = [clave for clave, record in _store.items() if record.last_seen < limite]
    for clave in expiradas:
        del _store[clave]


def get_owned(principal, session_id: str) -> SessionRecord | None:
    """Sesión del Principal, o `None`. Nunca busca solo por `session_id`.

    Devolver `None` en vez de lanzar cuando la sesión no es suya es deliberado: una
    respuesta distinta revelaría que ese identificador existe para otro.
    """
    if not session_id:
        return None
    with _lock:
        _purge_expired_locked()
        record = _store.get(_key(principal, session_id))
        if record is None:
            _registrar_acceso_cruzado_locked(principal, session_id)
            return None
        if record.revoked:
            return None
        record.last_seen = time.time()
        _store.move_to_end(_key(principal, session_id))
        return record


def _registrar_acceso_cruzado_locked(principal, session_id: str) -> None:
    """Anota el intento si ese `session_id` existe para OTRO dueño.

    Que un identificador ajeno aparezca en una petición no es ruido: es la señal de
    que se filtró o se está adivinando.
    """
    for (tenant, owner, sid) in _store:
        if sid == session_id:
            _cross_access_attempts.append({
                "session_id": session_id,
                "requested_by": getattr(principal, "subject", str(principal)),
                "requested_tenant": getattr(principal, "tenant_id", None),
                "owner_tenant": tenant,
                "ts": time.time(),
            })
            return


def cross_access_attempts() -> list[dict]:
    """Intentos de acceso cruzado observados. Para tests y observabilidad."""
    with _lock:
        return list(_cross_access_attempts)


def get_history(principal, session_id: str) -> list[ModelMessage]:
    """Historial de una sesión propia (vacío si no existe, expiró o no es suya)."""
    record = get_owned(principal, session_id)
    return list(record.messages) if record else []


def store_history(principal, session_id: str, messages: list[ModelMessage]) -> SessionRecord:
    """Persiste el historial bajo el Principal, recortado a MAX_TURNS.

    Crear una sesión la ata a su dueño desde el primer turno. Aplica la cota LRU y el
    TTL antes de insertar: una sesión nueva nunca hace crecer `_store` más allá de
    `MAX_SESSIONS`.
    """
    trimmed = trim_history(messages)
    clave = _key(principal, session_id)
    with _lock:
        _purge_expired_locked()
        record = _store.get(clave)
        if record is None:
            if len(_store) >= MAX_SESSIONS:
                _store.popitem(last=False)  # desaloja la LRU
            record = SessionRecord(
                session_id=session_id,
                owner_subject=clave[1],
                tenant_id=clave[0],
            )
            _store[clave] = record
        record.messages = trimmed
        record.last_seen = time.time()
        record.version += 1
        _store.move_to_end(clave)
        return record


def update_security_state(principal, session_id: str, **changes) -> SessionRecord | None:
    """Muta el estado de riesgo de una sesión propia con compare-and-set."""
    clave = _key(principal, session_id)
    with _lock:
        record = _store.get(clave)
        if record is None or record.revoked:
            return None
        record.security_state = {**record.security_state, **changes}
        record.last_seen = time.time()
        record.version += 1
        return record


def is_taken_by_other(principal, session_id: str) -> bool:
    """¿Ese `session_id` ya pertenece a otro sujeto o tenant?"""
    if not session_id:
        return False
    propia = _key(principal, session_id)
    with _lock:
        return any(
            sid == session_id and clave != propia
            for clave in _store
            for sid in (clave[2],)
        )


def claim_session(principal, session_id: str | None) -> tuple[str, list[ModelMessage]]:
    """Resuelve el identificador de sesión efectivo y el historial que puede cargarse.

    Tres casos, y solo uno es un problema de seguridad:

    * la sesión es suya → se continúa, con su historial;
    * el identificador no existe para nadie → se adopta bajo este Principal (el
      Playground y el runner eligen sus propios IDs, y eso no es una violación);
    * el identificador pertenece a **otro** → no se reutiliza ni se confirma su
      existencia: se abre una sesión nueva y queda anotado el intento cruzado.
    """
    if not session_id:
        nueva = new_session_id()
        store_history(principal, nueva, [])
        return nueva, []
    if is_taken_by_other(principal, session_id):
        with _lock:
            _registrar_acceso_cruzado_locked(principal, session_id)
        nueva = new_session_id()
        store_history(principal, nueva, [])
        return nueva, []
    record = get_owned(principal, session_id)
    if record is None:
        # Se materializa al reclamarla: el estado de riesgo de un turno bloqueado no
        # tiene dónde vivir si la sesión solo existe tras invocar al modelo (P22).
        record = store_history(principal, session_id, [])
    return session_id, list(record.messages)


def revoke(principal, session_id: str) -> bool:
    """Revoca una sesión propia: historial y estado de riesgo dejan de estar vivos."""
    clave = _key(principal, session_id)
    with _lock:
        record = _store.get(clave)
        if record is None:
            return False
        record.revoked = True
        record.messages = []
        record.security_state = {}
        return True


def session_count() -> int:
    """Número de sesiones vivas — expuesto para tests y observabilidad, no para lógica
    de negocio."""
    with _lock:
        return len(_store)


def clear_all() -> None:
    """Vacía el almacén — usado por los tests para no compartir estado entre casos."""
    with _lock:
        _store.clear()
        _cross_access_attempts.clear()
