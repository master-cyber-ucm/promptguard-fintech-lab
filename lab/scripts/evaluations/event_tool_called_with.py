from __future__ import annotations

from .event_base import Event


class ToolCalledWithEvent(Event):
    def __init__(self, tool: str, args: dict) -> None:
        self.tool = tool
        self.args = args

    def check(self, response: str, tools: list[dict]) -> bool:
        for t in tools:
            if t["tool"] == self.tool:
                actual = t.get("args", {})
                if all(str(actual.get(k, "")).lower() == str(v).lower() for k, v in self.args.items()):
                    return True
        return False

    def describe(self) -> str:
        args_str = ", ".join(f"{k}={v}" for k, v in self.args.items())
        return f"tool_called_with {self.tool} {{{args_str}}}"

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCalledWithEvent":
        return cls(tool=str(data["tool"]), args=data.get("args", {}))
