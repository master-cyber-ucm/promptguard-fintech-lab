from __future__ import annotations

from .event_base import Event


class ResponseContainsEvent(Event):
    def __init__(self, value: str) -> None:
        self.value = value

    def check(self, response: str, tools: list[dict]) -> bool:
        return self.value.lower() in response.lower()

    def describe(self) -> str:
        return f'response_contains "{self.value}"'

    @classmethod
    def from_dict(cls, data: dict) -> "ResponseContainsEvent":
        return cls(value=str(data["value"]))
