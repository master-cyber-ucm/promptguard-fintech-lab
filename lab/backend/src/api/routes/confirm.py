"""Autorización de operaciones fuera del canal conversacional.

P18: antes, `POST /confirm/{operation_id}` aceptaba `token` y `user_id` del cuerpo, y
la tool devolvía ambos dentro de su resultado. El mismo canal comprometido obtenía y
usaba todo lo necesario para confirmar.

Ahora la identidad sale del Principal, el desafío se recoge de la bandeja fuera de
banda (la app), y el endpoint recarga los detalles del store: no acepta importes ni
beneficiarios sustitutos en la petición.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.auth import Principal, principal_dependency
from src.core import transaction_authorization

router = APIRouter(tags=["confirm"])


class AuthorizeBody(BaseModel):
    challenge_response: str = Field(
        ...,
        description=(
            "Desafío recibido en el canal fuera de banda (la app). Nunca viaja por el "
            "canal conversacional ni aparece en el resultado de la tool."
        ),
    )
    decision: str = Field(
        default="approve", description="approve | reject",
    )


@router.get("/authorizations")
def list_authorizations(principal: Principal = Depends(principal_dependency)):
    """Bandeja fuera de banda del sujeto autenticado. La consulta la app, no el modelo."""
    return {"operations": transaction_authorization.inbox(principal)}


@router.get("/authorizations/{operation_id}")
def authorization_detail(
    operation_id: str, principal: Principal = Depends(principal_dependency),
):
    """Detalle exacto que la persona ve antes de firmar."""
    resumen = transaction_authorization.pending_summary(operation_id, principal)
    if resumen is None:
        # No enumerativa: no distingue "no existe" de "no es tuya".
        raise HTTPException(status_code=404, detail="Operación no disponible")
    return resumen


@router.post("/confirm/{operation_id}")
def confirm_operation(
    operation_id: str,
    body: AuthorizeBody,
    principal: Principal = Depends(principal_dependency),
):
    """Aprueba o rechaza una operación pendiente. Un solo uso, TTL corto.

    El canal conversacional que originó la petición no puede completarla: no conoce el
    desafío y no puede sustituir al Principal.
    """
    return transaction_authorization.authorize(
        operation_id,
        principal=principal,
        challenge_response=body.challenge_response,
        decision=body.decision,
    )
