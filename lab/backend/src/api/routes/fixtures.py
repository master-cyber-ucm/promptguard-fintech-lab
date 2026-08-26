"""Expone los fixtures de test al Playground frontend."""

from __future__ import annotations

from fastapi import APIRouter

from src.utils.fixture_loader import load_prompts

router = APIRouter(tags=["fixtures"])

_ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]


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
