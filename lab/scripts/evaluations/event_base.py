from __future__ import annotations

from abc import ABC, abstractmethod


class Event(ABC):
    """Predicado determinista sobre la evidencia de una ejecución.

    La forma histórica —`check(response, tools)`— basta para eventos que solo miran la
    salida. Los que necesitan procedencia (¿estaba ya en el prompt del atacante?) usan
    `check_in(context)`, que recibe toda la evidencia de la ejecución. El default
    delega, así que ningún evento existente cambia de comportamiento.
    """

    @abstractmethod
    def check(self, response: str, tools: list[dict]) -> bool: ...

    @abstractmethod
    def describe(self) -> str: ...

    def inconclusive_reason(self, response: str, tools: list[dict]) -> str | None:
        return None

    def check_in(self, context) -> bool:
        return self.check(context.response, context.tools)

    def inconclusive_in(self, context) -> str | None:
        return self.inconclusive_reason(context.response, context.tools)

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict) -> "Event": ...
