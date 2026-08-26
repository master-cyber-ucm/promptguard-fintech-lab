from __future__ import annotations

from .event_base import Event


class ToolCalledEvent(Event):
    def __init__(self, tool: str) -> None:
        self.tool = tool

    def check(self, response: str, tools: list[dict]) -> bool:
        return any(t["tool"] == self.tool for t in tools)

    def describe(self) -> str:
        return f"tool_called {self.tool}"

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCalledEvent":
        return cls(tool=str(data["tool"]))
