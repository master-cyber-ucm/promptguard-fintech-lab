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
from sources import SeedSource


class EvolutionEngine(Protocol):
    name: str

    def abrir_intento(self, *, tecnica: dict, historial: list[Intento], brain: AttackerBrain) -> str:
        """Devuelve el payload de apertura del siguiente Intento."""
        ...


class SeededEngine:
    """Envuelve cualquier motor con una Fuente de semillas externa (`sources/`):
    en el primer Intento de un Ejercicio (historial vacío) usa la siguiente semilla
    disponible para esa Técnica en vez de generarla; si la fuente no tiene semillas
    para esa Técnica, o ya se agotaron, delega en el motor envuelto sin cambios —
    ver plan-fusion-redteam.md. `ultima_fuente` queda expuesto para que el
    orquestador pueda registrar la procedencia del payload en el Informe."""

    def __init__(self, inner: EvolutionEngine, source: SeedSource) -> None:
        self.name = f"{inner.name}+{source.name}"
        self._inner = inner
        self._source = source
        self.ultima_fuente = "propio"

    def abrir_intento(self, *, tecnica: dict, historial: list[Intento], brain: AttackerBrain) -> str:
        if not historial:
            semilla = self._source.siguiente(tecnica)
            if semilla:
                self.ultima_fuente = self._source.name
                return semilla
        self.ultima_fuente = "propio"
        return self._inner.abrir_intento(tecnica=tecnica, historial=historial, brain=brain)


def get_engine(nombre: str, seed_source: SeedSource | None = None) -> EvolutionEngine:
    if nombre == "autorreflexivo":
        from evolution.self_reflect import SelfReflectEngine
        engine: EvolutionEngine = SelfReflectEngine()
    elif nombre == "genetico":
        from evolution.genetic import GeneticEngine
        engine = GeneticEngine()
    elif nombre == "taxonomia":
        from evolution.taxonomy_guided import TaxonomyGuidedEngine
        engine = TaxonomyGuidedEngine()
    else:
        raise ValueError(f"Motor de evolución desconocido: {nombre!r}")
    if seed_source is not None:
        engine = SeededEngine(engine, seed_source)
    return engine
