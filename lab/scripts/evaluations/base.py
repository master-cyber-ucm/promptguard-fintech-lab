from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import httpx

SUCCESS = "SUCCESS"
BLOCKED = "BLOCKED"
INCONCLUSIVE = "INCONCLUSIVE"

DETERMINISTIC_PASS = "DETERMINISTIC_PASS"
SECURITY_BREACH = "SECURITY_BREACH"
SECURITY_BLOCK = "SECURITY_BLOCK"
FUNCTIONAL_FAILURE = "FUNCTIONAL_FAILURE"
SEMANTIC_PASS = "SEMANTIC_PASS"
EVIDENCE_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"


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
    inconclusive: bool = False
    status: str = "PASS"
    disposition: str = DETERMINISTIC_PASS
    decision_source: str = "deterministic"
    deterministic_reason: str | None = None
    judge: dict | None = None


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
    from .event_tool_effect import ToolAttemptedEvent, ToolCompletedWithEvent, ToolDeniedEvent, ToolPendingConfirmationEvent, ToolResultMatchesEvent
    from .event_response_not_empty import ResponseNotEmptyEvent

    etype = data.get("type")
    if etype == "response_contains":
        return ResponseContainsEvent.from_dict(data)
    if etype == "response_not_empty":
        return ResponseNotEmptyEvent.from_dict(data)
    if etype == "tool_called":
        return ToolCalledEvent.from_dict(data)
    if etype == "tool_called_with":
        return ToolCalledWithEvent.from_dict(data)
    if etype == "tool_attempted": return ToolAttemptedEvent.from_dict(data)
    if etype == "tool_denied": return ToolDeniedEvent.from_dict(data)
    if etype == "tool_pending_confirmation": return ToolPendingConfirmationEvent.from_dict(data)
    if etype == "tool_completed_with": return ToolCompletedWithEvent.from_dict(data)
    if etype == "tool_result_matches": return ToolResultMatchesEvent.from_dict(data)
    raise ValueError(f"Unknown event type: {etype!r}")


def evaluator_from_fixture(fixture: dict) -> Evaluator:
    from .deterministic import DeterministicEvaluator
    from .llm import LLMEvaluator
    from .hybrid import HybridEvaluator
    from .hybrid_attack import HybridAttackEvaluator

    ev = fixture.get("evaluation") or {}
    method = ev.get("method", "deterministic")

    if method == "deterministic":
        # ``events`` fue el nombre original de los eventos prohibidos. Se conserva
        # para que los fixtures de ataque existentes no cambien de significado.
        forbidden = ev.get("forbidden_events", ev.get("events", []))
        required = ev.get("required_events", [])
        return DeterministicEvaluator(
            required_events=[event_from_dict(e) for e in required],
            forbidden_events=[event_from_dict(e) for e in forbidden],
            hard_events=[event_from_dict(e) for e in ev.get("hard_events", [])],
        )

    if method == "llm":
        question = ev.get("question", "")
        judge = ev.get("judge") or {}
        return LLMEvaluator(
            question=question,
            system=judge.get("system"),
            include=judge.get("include"),
            template=judge.get("template"),
        )

    if method == "hybrid":
        forbidden = ev.get("forbidden_events", ev.get("events", []))
        fallback = ev.get("fallback") or {}
        judge = fallback.get("judge") or {}
        return HybridEvaluator(
            required_events=[event_from_dict(e) for e in ev.get("required_events", [])],
            forbidden_events=[event_from_dict(e) for e in forbidden],
            hard_events=[event_from_dict(e) for e in ev.get("hard_events", [])],
            fallback_when=fallback.get("when"),
            rubric=fallback.get("rubric", ""),
            system=judge.get("system"),
            include=judge.get("include"),
        )

    if method == "hybrid_attack":
        breach = ev.get("breach_events", ev.get("events", ev.get("forbidden_events", [])))
        fallback = ev.get("fallback") or {}
        judge = fallback.get("judge", ev.get("judge") or {})
        return HybridAttackEvaluator(
            hard_events=[event_from_dict(e) for e in ev.get("hard_events", [])],
            breach_events=[event_from_dict(e) for e in breach],
            fallback_when=fallback.get("when", "no_breach_observed"),
            rubric=fallback.get("rubric", ev.get("question", "")),
            include=judge.get("include"),
        )

    raise ValueError(f"Unknown evaluation method: {method!r}")
