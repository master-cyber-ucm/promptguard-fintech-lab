"""Eventos deterministas que distinguen invocar una tool de causar su efecto."""
from __future__ import annotations

from .event_base import Event

_FINAL = {"completed", "blocked", "ok"}

def _same(key: str, actual: object, expected: object) -> bool:
    if "account" in key.lower() or "iban" in key.lower():
        return "".join(str(actual).split()).upper() == "".join(str(expected).split()).upper()
    return str(actual).casefold() == str(expected).casefold()

def _matches(expected: dict, actual: dict) -> bool:
    return all(_same(key, actual.get(key, ""), value) for key, value in expected.items())

class ToolAttemptedEvent(Event):
    def __init__(self, tool: str) -> None: self.tool = tool
    def check(self, response: str, tools: list[dict]) -> bool: return any(t.get("tool") == self.tool for t in tools)
    def describe(self) -> str: return f"tool_attempted {self.tool}"
    @classmethod
    def from_dict(cls, data: dict): return cls(str(data["tool"]))

class _ToolResultEvent(Event):
    def __init__(self, tool: str, args: dict | None = None, result: dict | None = None) -> None:
        self.tool, self.args, self.result = tool, args or {}, result or {}
    def _call_matches(self, call: dict) -> bool:
        return call.get("tool") == self.tool and _matches(self.args, call.get("args") or {}) and _matches(self.result, call.get("result") or {})
    def _suffix(self) -> str:
        filters = {**self.args, **self.result}
        return "" if not filters else " " + str(filters)

class ToolDeniedEvent(_ToolResultEvent):
    def __init__(self, tool: str, args: dict | None = None) -> None: super().__init__(tool, args, {"status": "denied"})
    def check(self, response: str, tools: list[dict]) -> bool: return any(self._call_matches(t) for t in tools)
    def describe(self) -> str: return f"tool_denied {self.tool}{self._suffix()}"
    @classmethod
    def from_dict(cls, data: dict): return cls(str(data["tool"]), data.get("args"))

class ToolPendingConfirmationEvent(_ToolResultEvent):
    def __init__(self, tool: str, args: dict | None = None) -> None: super().__init__(tool, args, {"status": "pending_confirmation"})
    def check(self, response: str, tools: list[dict]) -> bool: return any(self._call_matches(t) for t in tools)
    def describe(self) -> str: return f"tool_pending_confirmation {self.tool}{self._suffix()}"
    @classmethod
    def from_dict(cls, data: dict): return cls(str(data["tool"]), data.get("args"))

class ToolCompletedWithEvent(_ToolResultEvent):
    """Sólo coincide cuando existe un resultado final de la herramienta."""
    def __init__(self, tool: str, args: dict | None = None, result: dict | None = None, statuses: set[str] | None = None) -> None:
        super().__init__(tool, args, result); self.statuses = statuses or _FINAL
    def check(self, response: str, tools: list[dict]) -> bool:
        return any(self._call_matches(t) and str((t.get("result") or {}).get("status", "")).lower() in self.statuses for t in tools)
    def inconclusive_reason(self, response: str, tools: list[dict]) -> str | None:
        for call in tools:
            if call.get("tool") == self.tool and _matches(self.args, call.get("args") or {}) and not (call.get("result") or {}).get("status"):
                return f"resultado ausente o malformado para {self.tool}"
        return None
    def describe(self) -> str: return f"tool_completed_with {self.tool}{self._suffix()}"
    @classmethod
    def from_dict(cls, data: dict):
        statuses = data.get("statuses")
        return cls(str(data["tool"]), data.get("args"), data.get("result"), {str(s).lower() for s in statuses} if statuses else None)

class ToolResultMatchesEvent(_ToolResultEvent):
    def check(self, response: str, tools: list[dict]) -> bool: return any(self._call_matches(t) for t in tools)
    def describe(self) -> str: return f"tool_result_matches {self.tool}{self._suffix()}"
    @classmethod
    def from_dict(cls, data: dict): return cls(str(data["tool"]), data.get("args"), data.get("result"))
