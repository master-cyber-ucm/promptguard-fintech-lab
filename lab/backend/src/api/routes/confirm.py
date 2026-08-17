"""Confirmación fuera de banda de operaciones pendientes (Tool Gatekeeper, §A1 del plan
de excelencia). Cuando una tool queda `pending_confirmation` (importe sobre el umbral de
`tool_permissions.yaml::requires_approval_above`), este endpoint es el único camino para
que se ejecute — el canal conversacional que originó la petición no puede completarla
por sí solo.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core import tool_permissions

router = APIRouter(tags=["confirm"])


class ConfirmBody(BaseModel):
    token: str = Field(..., description="Token devuelto al crear la operación pendiente")
    user_id: str = Field(..., description="Usuario que confirma — debe coincidir con quien la originó")


@router.post("/confirm/{operation_id}")
def confirm_operation(operation_id: str, body: ConfirmBody):
    """Confirma (o rechaza) una operación pendiente. Un solo uso, TTL corto — ver
    `src/core/tool_permissions.py::confirmar`."""
    return tool_permissions.confirmar(operation_id, body.token, body.user_id)
