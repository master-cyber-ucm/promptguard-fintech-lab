"""Motores de evolución — interfaz común, intercambiable por config de Campaña.

Cada motor solo decide el PAYLOAD DE APERTURA del siguiente Intento dentro de un
Ejercicio. La escalada DENTRO de un Intento multi-turn (tras un veredicto CONTINUE)
la resuelve siempre `attacker.AttackerBrain.continuar()`, con independencia del motor
— es la misma "memoria por Ejercicio" para los tres, ver CONTEXT.md.
"""

from __future__ import annotations

from typing import Protocol

from attacker import AttackerBrain
from models import Intento


class EvolutionEngine(Protocol):
    name: str

    def abrir_intento(self, *, tecnica: dict, historial: list[Intento], brain: AttackerBrain) -> str:
        """Devuelve el payload de apertura del siguiente Intento."""
        ...


def get_engine(nombre: str) -> EvolutionEngine:
    if nombre == "autorreflexivo":
        from evolution.self_reflect import SelfReflectEngine
        return SelfReflectEngine()
    if nombre == "genetico":
        from evolution.genetic import GeneticEngine
        return GeneticEngine()
    if nombre == "taxonomia":
        from evolution.taxonomy_guided import TaxonomyGuidedEngine
        return TaxonomyGuidedEngine()
    raise ValueError(f"Motor de evolución desconocido: {nombre!r}")
