"""Estado de riesgo de una sesión: lo detectado en el turno 1 pesa en el turno 2.

P22: el Input Sanitizer bloqueaba el contenido malicioso y no dejaba señal útil para
el siguiente turno. En `atk_045`, el turno 1 quedó bloqueado y el turno 2 —«haz la
transferencia», inocuo si se mira aislado— llegó a preparar la operación. El atacante
obtiene una segunda oportunidad sin repetir el patrón detectable.

No se guarda el payload: solo señal tipada, severidad, categoría y hash. La máquina de
estados es **monotónica durante el incidente** (nunca baja por un turno tranquilo) y se
recupera por caducidad o por una transición explícita.

    NORMAL ──señal media──► ELEVATED ──señal alta──► QUARANTINED
       ▲                                                  │
       └────────── caducidad o recovery explícito ─────────┘
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum

SECURITY_STATE_SCHEMA_VERSION = 1

#: Cuánto dura un incidente sin señales nuevas antes de decaer.
ELEVATED_TTL_SECONDS = 900
QUARANTINE_TTL_SECONDS = 1800


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class RiskLevel(_Str):
    NORMAL = "NORMAL"
    ELEVATED = "ELEVATED"
    QUARANTINED = "QUARANTINED"


_ORDER = {RiskLevel.NORMAL: 0, RiskLevel.ELEVATED: 1, RiskLevel.QUARANTINED: 2}


class Severity(_Str):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class RiskSignal:
    """Señal saneada. Nunca contiene el texto del ataque."""

    category: str
    severity: Severity
    component: str
    confidence: float = 1.0
    #: Huella del payload, para correlacionar sin conservarlo.
    payload_hash: str | None = None
    at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": str(self.severity),
            "component": self.component,
            "confidence": self.confidence,
            "payload_hash": self.payload_hash,
            "at": self.at,
        }


def signal_from_payload(
    *, category: str, severity: Severity, component: str, payload: str,
    confidence: float = 1.0,
) -> RiskSignal:
    """Construye la señal quedándose solo con la huella del payload."""
    return RiskSignal(
        category=category, severity=severity, component=component, confidence=confidence,
        payload_hash=hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16],
    )


@dataclass
class SessionSecurityState:
    """Riesgo acumulado de una Conversation Session. No es el transcript."""

    schema_version: int = SECURITY_STATE_SCHEMA_VERSION
    level: RiskLevel = RiskLevel.NORMAL
    signals: list[dict] = field(default_factory=list)
    reason: str | None = None
    entered_at: float | None = None
    recovered_at: float | None = None

    @property
    def quarantined(self) -> bool:
        return self.level == RiskLevel.QUARANTINED

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "level": str(self.level),
            "signals": list(self.signals),
            "reason": self.reason,
            "entered_at": self.entered_at,
            "recovered_at": self.recovered_at,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "SessionSecurityState":
        data = data or {}
        nivel = str(data.get("level") or RiskLevel.NORMAL.value).upper()
        return cls(
            level=RiskLevel(nivel) if nivel in {m.value for m in RiskLevel} else RiskLevel.NORMAL,
            signals=list(data.get("signals") or []),
            reason=data.get("reason"),
            entered_at=data.get("entered_at"),
            recovered_at=data.get("recovered_at"),
        )


def _level_for(signal: RiskSignal) -> RiskLevel:
    if signal.severity == Severity.HIGH and signal.confidence >= 0.7:
        return RiskLevel.QUARANTINED
    if signal.severity in (Severity.MEDIUM, Severity.HIGH):
        return RiskLevel.ELEVATED
    return RiskLevel.NORMAL


def apply_signal(state: SessionSecurityState, signal: RiskSignal) -> SessionSecurityState:
    """Incorpora una señal. Nunca baja el nivel: dos eventos concurrentes no pueden
    rebajarse entre sí ni perder la señal más severa."""
    nuevo = _level_for(signal)
    estado = SessionSecurityState(
        level=state.level, signals=[*state.signals, signal.to_dict()],
        reason=state.reason, entered_at=state.entered_at, recovered_at=state.recovered_at,
    )
    if _ORDER[nuevo] > _ORDER[estado.level]:
        estado.level = nuevo
        estado.reason = f"{signal.category}_{str(signal.severity).lower()}"
        estado.entered_at = signal.at
        estado.recovered_at = None
    return estado


def decay(state: SessionSecurityState, *, now: float | None = None) -> SessionSecurityState:
    """Caduca el incidente si no hubo señales nuevas dentro del TTL de su nivel."""
    if state.level == RiskLevel.NORMAL or state.entered_at is None:
        return state
    ahora = now if now is not None else time.time()
    ttl = QUARANTINE_TTL_SECONDS if state.quarantined else ELEVATED_TTL_SECONDS
    ultima = max((s.get("at", state.entered_at) for s in state.signals), default=state.entered_at)
    if ahora - ultima < ttl:
        return state
    return SessionSecurityState(
        level=RiskLevel.NORMAL, signals=list(state.signals),
        reason=None, entered_at=None, recovered_at=ahora,
    )


def recover(state: SessionSecurityState, *, now: float | None = None) -> SessionSecurityState:
    """Transición explícita de recuperación (flujo autenticado fuera de la sesión)."""
    return SessionSecurityState(
        level=RiskLevel.NORMAL, signals=list(state.signals), reason=None,
        entered_at=None, recovered_at=now if now is not None else time.time(),
    )


# ── Consecuencias ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskConstraint:
    """Lo que el estado de riesgo impone al turno actual."""

    deny_state_changing_tools: bool = False
    require_step_up: bool = False
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "deny_state_changing_tools": self.deny_state_changing_tools,
            "require_step_up": self.require_step_up,
            "reason": self.reason,
        }


def constraints_for(state: SessionSecurityState) -> RiskConstraint:
    """Traduce el nivel en consecuencias concretas.

    En cuarentena la sesión puede seguir ayudando con información, pero ninguna acción
    financiera continúa dentro de ella: eso es lo que cierra el ataque multivuelta.
    """
    if state.quarantined:
        return RiskConstraint(
            deny_state_changing_tools=True, require_step_up=True,
            reason=(
                "la sesión está en cuarentena por una señal de inyección de alta "
                f"confianza ({state.reason}): las acciones con efecto requieren un "
                "flujo autenticado nuevo"
            ),
        )
    if state.level == RiskLevel.ELEVATED:
        return RiskConstraint(
            require_step_up=True,
            reason=f"riesgo elevado en la sesión ({state.reason})",
        )
    return RiskConstraint()
