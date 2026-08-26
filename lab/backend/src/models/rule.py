"""Modelo de reglas personalizadas del Input Sanitizer."""

from datetime import datetime
from typing import Optional, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class Rule(BaseModel):
    """Regla de detección personalizable."""
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., description="Nombre descriptivo de la regla")
    pattern: str = Field(..., description="Patrón regex o texto a buscar")
    action: Literal["BLOCK", "SUSPICIOUS", "LOG"] = "BLOCK"
    priority: int = Field(default=50, ge=0, le=100)
    enabled: bool = True
    category: str = Field(
        default="custom",
        description="Categoría: injection, leakage, agency, pii, custom"
    )
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    hit_count: int = 0
