from __future__ import annotations

from .event_base import Event


class ResponseNotEmptyEvent(Event):
    """Evidencia mínima de que el endpoint atendió una petición legítima."""

    def check(self, response: str, tools: list[dict]) -> bool:
        return bool(response and response.strip())

    def describe(self) -> str:
        return "response_not_empty"

    @classmethod
    def from_dict(cls, data: dict) -> "ResponseNotEmptyEvent":
        return cls()
