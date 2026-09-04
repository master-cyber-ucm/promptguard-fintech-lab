"""Propuesta de acción: el modelo propone, la policy valida, el backend consuma.

P23: el Output Auditor corre DESPUÉS de que el agente haya invocado las tools. Puede
ocultar el texto que ve el cliente, pero no deshacer una transferencia ni un bloqueo de
tarjeta. En el run había sesiones con `Output Auditor = BLOCK` que seguían clasificadas
como brecha porque la llamada previa ya había ocurrido: desde el cliente parecía que el
sistema se negó; desde el banco, el estado ya había cambiado.

El orden correcto separa proponer de ejecutar:

    LLM → ActionProposal → validación de procedencia → PolicyDecision
        → autorización independiente (si aplica) → commit → EffectReceipt
        → composición segura de la respuesta

El Output Auditor conserva su función sobre el texto. Lo que no puede es contarse como
la defensa que impidió una transferencia.
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum

PROPOSAL_SCHEMA_VERSION = 1


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ProposalState(_Str):
    DRAFTED = "DRAFTED"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    AWAITING_AUTHORIZATION = "AWAITING_AUTHORIZATION"
    COMMITTED = "COMMITTED"


@dataclass
class ActionProposal:
    """Acción que el modelo propone y que todavía NO es ejecutable."""

    proposal_id: str = field(default_factory=lambda: f"prop_{uuid.uuid4().hex[:12]}")
    schema_version: int = PROPOSAL_SCHEMA_VERSION
    tool: str = ""
    #: Argumentos tal como los pidió el modelo, con su procedencia (P24).
    requested_arguments: dict = field(default_factory=dict)
    #: Atributos que resolvió el backend. El modelo no los controla.
    resolved_attributes: dict = field(default_factory=dict)
    subject: str = ""
    state: ProposalState = ProposalState.DRAFTED
    rejection_reason: str | None = None
    #: Clave de idempotencia: la misma operación no puede consumarse dos veces.
    operation_key: str | None = None

    @property
    def effective_arguments(self) -> dict:
        """Lo resuelto por el backend gana siempre sobre lo pedido por el modelo."""
        return {**self.requested_arguments, **self.resolved_attributes}

    def digest(self) -> str:
        material = json.dumps(
            {"tool": self.tool, "arguments": self.effective_arguments, "subject": self.subject},
            sort_keys=True, ensure_ascii=False, default=str,
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "proposal_id": self.proposal_id,
            "tool": self.tool,
            "requested_arguments": self.requested_arguments,
            "resolved_attributes": self.resolved_attributes,
            "effective_arguments": self.effective_arguments,
            "subject": self.subject,
            "state": str(self.state),
            "rejection_reason": self.rejection_reason,
            "operation_key": self.operation_key,
            "digest": self.digest(),
        }


class CommitLedger:
    """Idempotencia del commit: una `operation_key` produce como máximo un efecto."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._committed: dict[str, dict] = {}

    def claim(self, operation_key: str) -> bool:
        """Reserva la clave. `False` si otra ejecución ya la tomó."""
        with self._lock:
            if operation_key in self._committed:
                return False
            self._committed[operation_key] = {}
            return True

    def record(self, operation_key: str, result: dict) -> None:
        with self._lock:
            self._committed[operation_key] = result

    def previous(self, operation_key: str) -> dict | None:
        with self._lock:
            return self._committed.get(operation_key)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._committed.clear()


default_commit_ledger = CommitLedger()


class ProposalRejected(Exception):
    """La propuesta no llegó a ser ejecutable. No hubo efecto."""

    def __init__(self, proposal: ActionProposal) -> None:
        super().__init__(proposal.rejection_reason or "propuesta rechazada")
        self.proposal = proposal


def draft(
    *, tool: str, subject: str, requested_arguments: dict, resolved_attributes: dict,
    operation_key: str | None = None,
) -> ActionProposal:
    return ActionProposal(
        tool=tool, subject=subject,
        requested_arguments=dict(requested_arguments),
        resolved_attributes=dict(resolved_attributes),
        operation_key=operation_key,
    )


def reject(proposal: ActionProposal, reason: str) -> ActionProposal:
    proposal.state = ProposalState.REJECTED
    proposal.rejection_reason = reason
    return proposal


def validate(proposal: ActionProposal) -> ActionProposal:
    proposal.state = ProposalState.VALIDATED
    return proposal


def commit(
    proposal: ActionProposal, execute, *, ledger: CommitLedger | None = None,
) -> dict:
    """Consuma la propuesta validada. Nunca se llama desde el wrapper de la tool.

    Una propuesta que no llegó a `VALIDATED` no puede consumarse: es lo que impide que
    un texto inyectado en la respuesta cause —o revierta— un commit.
    """
    if proposal.state not in (ProposalState.VALIDATED, ProposalState.AWAITING_AUTHORIZATION):
        raise ProposalRejected(
            reject(proposal, f"no se puede consumar en estado {proposal.state}")
        )

    ledger = ledger or default_commit_ledger
    clave = proposal.operation_key or proposal.digest()
    if not ledger.claim(clave):
        # Un doble envío no produce un segundo efecto: se devuelve el primero.
        anterior = ledger.previous(clave)
        proposal.state = ProposalState.COMMITTED
        return {**(anterior or {}), "idempotent_replay": True}

    resultado = execute()
    ledger.record(clave, resultado)
    proposal.state = ProposalState.COMMITTED
    return resultado
