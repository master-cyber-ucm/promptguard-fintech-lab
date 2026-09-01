"""Autorización de transacción fuera del canal del LLM.

P18: la tool devolvía `confirm_token` y `operation_id` dentro de su resultado, y
`POST /confirm/{operation_id}` aceptaba token y `user_id` del cliente. Todo el segundo
factor viajaba por el primer canal: un prompt comprometido podía pedir al modelo que
mostrara el token y después confirmarlo. Eso no es una aprobación humana independiente,
es un formalismo.

Ahora:

* la tool solo ve una **referencia opaca** y un resumen no sensible;
* el desafío se entrega a un canal separado (`out_of_band`) que el modelo no lee;
* la aprobación exige el Principal autenticado y recarga los detalles server-side —
  no acepta importes ni beneficiarios sustitutos;
* el `proposal_digest` ata todos los campos: cambiar cualquiera invalida la aprobación;
* el commit es de un solo uso, aunque lleguen dos aprobadores a la vez.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

AUTHORIZATION_SCHEMA_VERSION = 1

#: TTL corto: una propuesta que nadie aprueba deja de ser aprobable.
TTL_SECONDS = int(__import__("os").environ.get("AUTHORIZATION_TTL", "120"))

_lock = threading.Lock()
_pending: dict[str, "PendingOperation"] = {}
#: Bandeja fuera de banda por sujeto. Representa la app bancaria: el canal
#: conversacional no puede leerla ni escribir en ella.
_out_of_band: dict[str, list[dict]] = {}


def canonical_digest(details: dict) -> str:
    """Huella de la operación EXACTA que se propone.

    Cubre todos los campos, no solo el identificador: si tras la aprobación cambia el
    beneficiario o el importe, el digest deja de coincidir y el commit no ocurre.
    """
    material = json.dumps(details, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


@dataclass
class PendingOperation:
    """Propuesta a la espera de una autorización independiente."""

    operation_id: str
    tool: str
    owner_subject: str
    tenant_id: str
    details: dict
    proposal_digest: str
    displayed_fields: dict
    execute: Callable[[], dict]
    challenge: str
    expires_at: float
    consumed: bool = False
    approved_by: str | None = None
    schema_version: int = AUTHORIZATION_SCHEMA_VERSION

    @property
    def expired(self) -> bool:
        return time.time() > self.expires_at

    def to_reference(self) -> dict:
        """Lo ÚNICO que puede ver el canal conversacional.

        Ni el desafío ni el digest salen por aquí: si el modelo puede leerlos, el
        atacante que controla el prompt también.
        """
        return {
            "operation_reference": self.operation_id,
            "requires": "out_of_band_approval",
            "message": (
                "La operación está preparada y NO se ha ejecutado. Confírmala desde tu "
                "app de VerdaBank, donde verás el detalle completo."
            ),
            "summary": self.displayed_fields,
        }


def reset_for_tests() -> None:
    with _lock:
        _pending.clear()
        _out_of_band.clear()


def propose(
    *,
    tool: str,
    principal,
    details: dict,
    displayed_fields: dict,
    execute: Callable[[], dict],
) -> PendingOperation:
    """Registra una propuesta y entrega su desafío fuera de banda.

    `execute` se evalúa de forma perezosa: nada ocurre al proponer.
    """
    operation_id = f"op_{uuid.uuid4().hex[:12]}"
    # Desafío de alta entropía. No vuelve por el canal del LLM en ningún caso.
    challenge = secrets.token_urlsafe(24)
    operacion = PendingOperation(
        operation_id=operation_id,
        tool=tool,
        owner_subject=getattr(principal, "subject", str(principal)),
        tenant_id=getattr(principal, "tenant_id", "verdabank"),
        details=dict(details),
        proposal_digest=canonical_digest(details),
        displayed_fields=dict(displayed_fields),
        execute=execute,
        challenge=challenge,
        expires_at=time.time() + TTL_SECONDS,
    )
    with _lock:
        _pending[operation_id] = operacion
        _out_of_band.setdefault(operacion.owner_subject, []).append({
            "operation_id": operation_id,
            "tool": tool,
            # La app muestra el detalle real; es lo que la persona confirma.
            "displayed_fields": dict(displayed_fields),
            "challenge": challenge,
            "expires_at": operacion.expires_at,
        })
    return operacion


def inbox(principal) -> list[dict]:
    """Bandeja fuera de banda del sujeto. La consulta la app, nunca el modelo."""
    subject = getattr(principal, "subject", str(principal))
    with _lock:
        return [dict(mensaje) for mensaje in _out_of_band.get(subject, [])]


def pending_summary(operation_id: str, principal) -> dict | None:
    """Detalle que la app muestra antes de firmar. Solo para el dueño."""
    subject = getattr(principal, "subject", str(principal))
    with _lock:
        operacion = _pending.get(operation_id)
        if operacion is None or operacion.owner_subject != subject or operacion.expired:
            return None
        return {
            "operation_id": operacion.operation_id,
            "tool": operacion.tool,
            "displayed_fields": dict(operacion.displayed_fields),
            "expires_at": operacion.expires_at,
        }


class AuthorizationOutcome:
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    DENIED = "DENIED"


def authorize(
    operation_id: str,
    *,
    principal,
    challenge_response: str,
    decision: str = "approve",
) -> dict:
    """Aprueba o rechaza una propuesta. Como máximo un commit por operación.

    Los detalles se recargan del store: el aprobador confirma la operación registrada,
    no unos campos que llegan en la petición.
    """
    subject = getattr(principal, "subject", str(principal))
    tenant = getattr(principal, "tenant_id", "verdabank")

    with _lock:
        operacion = _pending.get(operation_id)
        if operacion is None:
            return _denied("operation_id desconocido o ya procesado")
        # Un sujeto o tenant distinto no puede aprobar, aunque conozca el desafío.
        if operacion.owner_subject != subject or operacion.tenant_id != tenant:
            return _denied("la operación pendiente no pertenece a este principal")
        if operacion.consumed:
            return _denied("la operación ya fue resuelta")
        if operacion.expired:
            _pending.pop(operation_id, None)
            return _denied(f"autorización expirada (TTL {TTL_SECONDS}s)")
        if not secrets.compare_digest(challenge_response, operacion.challenge):
            return _denied("desafío de autorización inválido")
        if canonical_digest(operacion.details) != operacion.proposal_digest:
            # Los detalles cambiaron después de proponerse: lo aprobado ya no es esto.
            return _denied("los detalles de la operación no coinciden con lo propuesto")

        # Marcar consumida DENTRO del lock es lo que hace que un doble clic, un replay
        # o dos aprobadores concurrentes produzcan como máximo un commit.
        operacion.consumed = True
        operacion.approved_by = subject
        ejecutar = operacion.execute
        detalles = dict(operacion.details)
        digest = operacion.proposal_digest
        assurance = getattr(principal, "assurance_level", "UNVERIFIED")
        _pending.pop(operation_id, None)
        _consume_out_of_band(subject, operation_id)

    if decision != "approve":
        return {
            "status": "rejected",
            "outcome": AuthorizationOutcome.REJECTED,
            "operation_id": operation_id,
        }

    resultado = ejecutar()
    resultado["authorization"] = {
        "schema_version": AUTHORIZATION_SCHEMA_VERSION,
        "operation_id": operation_id,
        "proposal_digest": digest,
        "approver_subject": subject,
        "approver_assurance": assurance,
        "approved_at": time.time(),
        "displayed": detalles,
    }
    return resultado


def _consume_out_of_band(subject: str, operation_id: str) -> None:
    bandeja = _out_of_band.get(subject)
    if not bandeja:
        return
    _out_of_band[subject] = [m for m in bandeja if m["operation_id"] != operation_id]


def _denied(reason: str) -> dict:
    return {"status": "denied", "outcome": AuthorizationOutcome.DENIED, "reason": reason}
