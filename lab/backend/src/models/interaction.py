"""Modelos de interacción para el pipeline de seguridad PromptGuard.

Cada interacción con el chatbot pasa por el pipeline y genera
un registro completo con todas las decisiones tomadas.
"""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .banking import PIIEntity


# --- Decisiones del pipeline ---

class PromptDecision(BaseModel):
    """Decisión del Input Sanitizer sobre un prompt entrante."""
    action: Literal["ALLOW", "SUSPICIOUS", "BLOCK"] = "ALLOW"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    layer: Literal[1, 2, 3] = Field(
        ..., description="1=regex, 2=ML classifier, 3=LLM guard"
    )
    reason: Optional[str] = None
    attack_type: Optional[str] = None
    matched_rule: Optional[str] = None


class OutputDecision(BaseModel):
    """Decisión del Output Auditor sobre la respuesta del LLM."""
    action: Literal["ALLOW", "BLOCK"] = "ALLOW"
    reason: Optional[str] = None
    pii_leaked: list[PIIEntity] = Field(default_factory=list)
    system_prompt_exposed: bool = False


class ToolDecision(BaseModel):
    """Decisión del Tool Gatekeeper sobre una tool call."""
    tool_name: str
    action: Literal["ALLOW", "BLOCK", "REQUIRE_APPROVAL"] = "ALLOW"
    reason: Optional[str] = None
    parameters_sanitized: Optional[dict] = None


# --- Interacción completa ---

class Interaction(BaseModel):
    """Registro completo de una interacción con el chatbot."""
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str
    user_id: str
    user_role: Literal["customer", "agent", "admin", "system"] = "customer"

    # Input
    input_message: str
    input_decision: PromptDecision = Field(
        default_factory=lambda: PromptDecision(action="ALLOW", confidence=1.0, layer=1)
    )
    pii_entities_found: list[PIIEntity] = Field(default_factory=list)
    pii_redacted_message: Optional[str] = None

    # Tool calls
    tools_requested: list[str] = Field(default_factory=list)
    tools_blocked: list[str] = Field(default_factory=list)
    tool_decisions: list[ToolDecision] = Field(default_factory=list)

    # Output
    output_message: Optional[str] = None
    output_decision: Optional[OutputDecision] = None
    output_flags: list[str] = Field(default_factory=list)

    # Métricas
    latency_ms: int = 0
    total_tokens: int = 0

    # Auditoría
    audit_signature: Optional[str] = None
    audit_id: str = Field(default_factory=lambda: str(uuid4()))


class InteractionCreate(BaseModel):
    """Request body para crear una interacción (POST /api/v1/proxy/chat)."""
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "usr_001"
    user_role: Literal["customer", "agent", "admin", "system"] = "customer"
    message: str
    context: dict = Field(default_factory=dict)
    tools_available: list[str] = Field(
        default_factory=lambda: [
            "consulta_saldo",
            "transferencia_nacional",
            "bloquear_tarjeta",
            "consulta_producto",
            "abrir_reclamacion",
        ]
    )


class ProxyResponse(BaseModel):
    """Response body del proxy."""
    decision: Literal["ALLOW", "SUSPICIOUS", "BLOCK"]
    sanitized_message: Optional[str] = None
    response: Optional[str] = None
    pii_redacted: list[dict] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    tools_blocked: list[str] = Field(default_factory=list)
    attack_type: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
    audit_id: str = ""
    latency_ms: int = 0


# --- Estadísticas del dashboard ---

class DashboardSummary(BaseModel):
    """Resumen del dashboard para un periodo."""
    total_interactions: int = 0
    blocked_attacks: int = 0
    suspicious_events: int = 0
    false_positives: int = 0
    pii_redacted_count: int = 0
    tools_blocked: int = 0
    tools_executed: int = 0
    avg_latency_ms: float = 0.0
    attack_types: dict[str, int] = Field(default_factory=dict)
    period: str = "24h"
