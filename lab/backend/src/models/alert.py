"""Modelos de alertas para el sistema PromptGuard."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Alert(BaseModel):
    """Alerta generada por el pipeline de seguridad."""
    id: UUID = Field(default_factory=uuid4)
    interaction_id: UUID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "MEDIUM"
    attack_type: str = ""
    description: str = ""
    status: Literal["NEW", "INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"] = "NEW"
    assigned_to: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None

    # Detalles del incidente
    input_message_snippet: Optional[str] = None
    decision_layer: Optional[int] = None
    confidence: Optional[float] = None
    matched_rule: Optional[str] = None


class AlertUpdate(BaseModel):
    """Actualización de estado de una alerta."""
    status: Literal["INVESTIGATING", "RESOLVED", "FALSE_POSITIVE"]
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
