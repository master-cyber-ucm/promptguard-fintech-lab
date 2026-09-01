"""Errores de ejecución tipados y saneados.

P08: el runner contabilizaba 12 errores técnicos que solo existían en el log de
consola. Como el informe itera Session Files, esas ejecuciones desaparecían de los
denominadores: `atk_040` en `complex-prompt` mostraba dos observaciones concluyentes y
ninguna señal de que faltaban tres. Si los fallos se concentran en los prompts más
lentos —que suelen ser los más complejos—, el sesgo no es aleatorio.

Dos reglas:

* Un error se **clasifica** por la fase en la que ocurrió, no por su texto.
* Un error se **sanea** antes de persistirse: el mensaje de una excepción puede
  arrastrar el prompt, un token o un IBAN, y el registro de errores no puede
  convertirse en una segunda vía de exposición.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ErrorPhase(_Str):
    """Dónde falló. Determina quién debe arreglarlo y si es reintentable."""

    #: No se pudo abrir la conexión con el backend.
    CONNECT = "CONNECT"
    #: El backend respondió con un error propio.
    BACKEND = "BACKEND"
    #: El proveedor del modelo falló o agotó su tiempo.
    MODEL = "MODEL"
    #: La respuesta llegó pero no se pudo interpretar.
    PARSE = "PARSE"
    #: No se pudo persistir la evidencia.
    PERSIST = "PERSIST"
    UNKNOWN = "UNKNOWN"


#: Fases cuyo fallo suele desaparecer al repetir. Un reintento mejora la
#: disponibilidad, pero NO borra la observación de que hubo un fallo técnico.
RETRYABLE_PHASES = (ErrorPhase.CONNECT, ErrorPhase.MODEL, ErrorPhase.BACKEND)

_PATTERNS = (
    # IBAN
    (re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"), "[IBAN]"),
    # Claves y tokens con prefijo reconocible
    (re.compile(r"\b(?:pg_internal_sk|sk-|Bearer)\s*[A-Za-z0-9._\-]{6,}", re.IGNORECASE), "[TOKEN]"),
    # Tarjetas
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[PAN]"),
    # Importes con separador de miles o decimales, seguidos de divisa
    (re.compile(r"\b\d[\d.,]*\s*(?:€|EUR\b|USD\b)", re.IGNORECASE), "[AMOUNT]"),
    # Correo
    (re.compile(r"\b[\w.\-]+@[\w.\-]+\.\w+\b"), "[EMAIL]"),
)

_MAX_MESSAGE = 240


def sanitize(message: str) -> str:
    """Recorta y enmascara un mensaje de error antes de persistirlo."""
    texto = " ".join(str(message or "").split())
    for patron, reemplazo in _PATTERNS:
        texto = patron.sub(reemplazo, texto)
    return texto[:_MAX_MESSAGE]


def classify(exc: BaseException | None, *, status_code: int | None = None,
             backend_error: str | None = None) -> ErrorPhase:
    """Deduce la fase a partir del tipo de excepción y del estado HTTP.

    Se mira el tipo, no el texto: los mensajes cambian entre versiones de librería y
    clasificar por substring convierte la telemetría en una lotería.
    """
    if exc is not None:
        nombre = type(exc).__name__.lower()
        if "timeout" in nombre:
            return ErrorPhase.MODEL
        if "connect" in nombre or "network" in nombre or "proxy" in nombre:
            return ErrorPhase.CONNECT
        if "json" in nombre or "decode" in nombre or "valueerror" == nombre:
            return ErrorPhase.PARSE
        if "oserror" in nombre or "permission" in nombre:
            return ErrorPhase.PERSIST
    if status_code is not None and status_code >= 500:
        return ErrorPhase.BACKEND
    if backend_error:
        bajo = backend_error.lower()
        if "timeout" in bajo or "ollama" in bajo or "model" in bajo:
            return ErrorPhase.MODEL
        return ErrorPhase.BACKEND
    return ErrorPhase.UNKNOWN


@dataclass(frozen=True)
class ExecutionError:
    """Error de una Fixture Execution, listo para el ledger y el informe."""

    phase: ErrorPhase
    exception_type: str
    message: str
    retryable: bool
    status_code: int | None = None
    schema_version: int = 1

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "phase": str(self.phase),
            "exception_type": self.exception_type,
            "message": self.message,
            "retryable": self.retryable,
            "status_code": self.status_code,
        }


def from_exception(exc: BaseException, *, status_code: int | None = None) -> ExecutionError:
    fase = classify(exc, status_code=status_code)
    return ExecutionError(
        phase=fase,
        exception_type=type(exc).__name__,
        message=sanitize(str(exc)),
        retryable=fase in RETRYABLE_PHASES,
        status_code=status_code,
    )


def from_backend(message: str, *, status_code: int | None = None) -> ExecutionError:
    """Error que el backend reportó en el cuerpo de la respuesta."""
    fase = classify(None, status_code=status_code, backend_error=message)
    return ExecutionError(
        phase=fase,
        exception_type="BackendError",
        message=sanitize(message),
        retryable=fase in RETRYABLE_PHASES,
        status_code=status_code,
    )
