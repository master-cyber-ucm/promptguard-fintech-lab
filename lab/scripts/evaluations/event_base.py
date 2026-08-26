from __future__ import annotations

from abc import ABC, abstractmethod


class Event(ABC):
    @abstractmethod
    def check(self, response: str, tools: list[dict]) -> bool: ...

    @abstractmethod
    def describe(self) -> str: ...

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "Event": ...
