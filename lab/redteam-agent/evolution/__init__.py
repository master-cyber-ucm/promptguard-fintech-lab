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
    en CADA Intento de un Ejercicio consulta primero si quedan semillas para esa
    Técnica y, si las hay, usa la siguiente en vez de generarla; solo cuando la
    fuente se agota (o nunca tuvo semillas para esa Técnica) delega en el motor
    envuelto sin cambios. `ultima_fuente` queda expuesto para que el orquestador
    registre la procedencia del payload en el Informe.

    v1 (2026-09-06) solo sembraba el Intento 1 (`if not historial`) y dejaba la
    evolución del resto en manos del motor — pero con --max-attempts 20 eso deja
    la fuente externa en ~1,7% de los payloads reales de una Campaña (2/120,
    campaña del 2026-09-07), sin importar cuántas semillas hubiera disponibles.
    Ahora se agotan las semillas primero (34 para `directa`, 10 para
    `filtrado-por-repeticion`) antes de pasar a generación propia — cobertura
    sistemática del catálogo externo por delante de la adaptación del motor, no
    al revés."""

    def __init__(self, inner: EvolutionEngine, source: SeedSource) -> None:
        self.name = f"{inner.name}+{source.name}"
        self._inner = inner
        self._source = source
        self.ultima_fuente = "propio"

    def abrir_intento(self, *, tecnica: dict, historial: list[Intento], brain: AttackerBrain) -> str:
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
