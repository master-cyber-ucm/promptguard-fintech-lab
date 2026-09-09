"""Expone los fixtures de test al Playground frontend."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.utils.fixture_loader import load_prompts
from src.utils.fixture_writer import FixtureWriteError, write_fixture

router = APIRouter(tags=["fixtures"])

_ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]


# --- Modelos de creación (Fixture Draft) ---

class EventSpec(BaseModel):
    type: str = Field(
        ...,
        description=("response_contains | tool_attempted | "
                     "tool_denied | tool_pending_confirmation | tool_completed_with | tool_result_matches"),
    )
    value: Optional[str] = None
    tool: Optional[str] = None
    args: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    statuses: Optional[list[str]] = None


class EvaluationSpec(BaseModel):
    method: str = Field(default="deterministic", description="deterministic | hybrid | hybrid_attack")
    events: list[EventSpec] = Field(default_factory=list)
    question: Optional[str] = None
    system: Optional[str] = Field(default="neutral", description="neutral | security")


class StepSpec(BaseModel):
    content: str


class CreateFixtureRequest(BaseModel):
    category: str = Field(..., description="LLM01 | LLM02 | LLM06 | LLM07 | _extensiones")
    subcategory: str
    kind: str
    id: str
    name: str
    severity: str = "HIGH"
    expected_result: str
    description: str = ""
    steps: list[StepSpec]
    evaluation: EvaluationSpec


@router.get("/fixtures")
async def list_fixtures():
    """Lista todos los fixtures (attack, legitimate, navi) para el Playground."""
    result = []
    for kind in _ALL_KINDS:
        for p in load_prompts(kind=kind):
            result.append(
                {
                    "id": p.get("id"),
                    "name": p.get("name"),
                    "description": p.get("description", ""),
                    "category": p.get("category", ""),
                    "attack": p.get("attack", ""),
                    "attack_type": p.get("attack_type", ""),
                    "severity": p.get("severity", ""),
                    "expected_result": p.get("expected_result", ""),
                    "kind": p.get("kind", ""),
                    "type": p.get("type", "single"),
                    "rendered_steps": p.get("rendered_steps", []),
                }
            )
    return {"total": len(result), "fixtures": result}


@router.post("/fixtures")
async def create_fixture(request: CreateFixtureRequest):
    """Persiste un Fixture Draft autorizado desde el Playground como YAML.

    Valida metadatos, unicidad de id y seguridad de la ruta; escribe el fichero
    en el árbol de fixtures (visible en el repo vía bind-mount).
    """
    draft = request.model_dump()
    try:
        dest = write_fixture(draft)
    except FixtureWriteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    from src.utils.fixture_loader import FIXTURES_DIR

    rel = dest.relative_to(FIXTURES_DIR)
    return {
        "ok": True,
        "id": request.id,
        "path": str(rel),
        "file": dest.name,
    }
