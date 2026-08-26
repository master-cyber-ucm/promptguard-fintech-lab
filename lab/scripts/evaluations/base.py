from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

SUCCESS = "SUCCESS"
BLOCKED = "BLOCKED"


@dataclass
class EvaluationContext:
    response: str
    tools: list[dict] = field(default_factory=list)
    expected_result: str = "BLOCK"       # BLOCK | ALLOW
    system_prompt: str | None = None
    user_context: str | None = None
    client: "httpx.AsyncClient | None" = None


@dataclass
class EvaluationResult:
    verdict: str                 # SUCCESS | BLOCKED
    passed: bool
    detail: str | None = None    # evento disparado o razonamiento del juez


class Evaluator(ABC):
    @abstractmethod
    async def evaluate(self, context: EvaluationContext) -> EvaluationResult: ...


# ──────────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────────

def event_from_dict(data: dict):
    from .event_response_contains import ResponseContainsEvent
    from .event_tool_called import ToolCalledEvent
    from .event_tool_called_with import ToolCalledWithEvent

    etype = data.get("type")
    if etype == "response_contains":
        return ResponseContainsEvent.from_dict(data)
    if etype == "tool_called":
        return ToolCalledEvent.from_dict(data)
    if etype == "tool_called_with":
        return ToolCalledWithEvent.from_dict(data)
    raise ValueError(f"Unknown event type: {etype!r}")


def evaluator_from_fixture(fixture: dict) -> Evaluator:
    from .deterministic import DeterministicEvaluator
    from .llm import LLMEvaluator

    ev = fixture.get("evaluation") or {}
    method = ev.get("method", "deterministic")

    if method == "deterministic":
        events = [event_from_dict(e) for e in ev.get("events", [])]
        return DeterministicEvaluator(events=events)

    if method == "llm":
        question = ev.get("question", "")
        judge = ev.get("judge") or {}
        return LLMEvaluator(
            question=question,
            system=judge.get("system"),
            include=judge.get("include"),
            template=judge.get("template"),
        )

    raise ValueError(f"Unknown evaluation method: {method!r}")
