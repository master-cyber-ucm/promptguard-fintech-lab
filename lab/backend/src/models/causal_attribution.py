"""Atribución causal por capa: quién impidió el efecto, no quién dejó un log.

P13: la métrica decía que no se observó brecha, pero no qué capa cambió el resultado.
Sumar «intervenciones por componente» duplica sesiones —una ejecución puede atravesar
cinco controles— y no demuestra contribución marginal: un `BLOCK` posterior a un commit
deja un log idéntico al de una prevención real.

Tres cantidades distintas por componente:

    detectó      emitió un evento sobre el vector
    intervino    su decisión enforced cambió flujo, artefacto o autoridad
    contuvo      esa intervención impidió el punto de efecto, verificado

Y una cuarta que ninguna de las tres puede sustituir: la **contribución marginal**,
que solo se estima con posturas de ablación emparejadas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class AttributionConfidence(_Str):
    """Cuánto sostiene metodológicamente la atribución."""

    #: Una única intervención aplicable antes del punto de efecto.
    ATTRIBUTED = "ATTRIBUTED"
    #: Varias intervenciones concurrentes: se conservan todas, sin elegir una.
    MULTIPLE_OR_UNKNOWN = "MULTIPLE_OR_UNKNOWN"
    #: No hubo intervención que pudiera contener.
    NOT_ATTRIBUTED = "NOT_ATTRIBUTED"


class BlockPhase(_Str):
    """Cuándo actuó el control respecto al punto de efecto."""

    #: Antes de que el efecto pudiera producirse. Es la única fase que previene.
    PREVENTIVE = "PREVENTIVE"
    #: Después de que el efecto ya se consumó. Reduce la exposición, no la evita.
    LATE = "LATE"
    UNKNOWN = "UNKNOWN"


@dataclass
class CausalAttribution:
    """Resultado de recorrer la línea temporal de una Fixture Execution."""

    schema_version: int = 1
    fixture_execution_id: str | None = None
    first_effective_blocker: str | None = None
    intervention_event_id: str | None = None
    contributing_components: tuple[str, ...] = ()
    detected_only: tuple[str, ...] = ()
    phase: BlockPhase = BlockPhase.UNKNOWN
    confidence: AttributionConfidence = AttributionConfidence.NOT_ATTRIBUTED
    prevented_effect_type: str | None = None
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "fixture_execution_id": self.fixture_execution_id,
            "first_effective_blocker": self.first_effective_blocker,
            "intervention_event_id": self.intervention_event_id,
            "contributing_components": list(self.contributing_components),
            "detected_only": list(self.detected_only),
            "phase": str(self.phase),
            "confidence": str(self.confidence),
            "prevented_effect_type": self.prevented_effect_type,
            "notes": list(self.notes),
        }


def attribute(
    events,
    *,
    applicable_controls: list[str] | None = None,
    effect_observed: bool = False,
    effect_sequence: int | None = None,
    fixture_execution_id: str | None = None,
    prevented_effect_type: str | None = None,
) -> CausalAttribution:
    """Recorre el timeline y decide quién —si alguien— impidió el efecto.

    `effect_sequence` marca el punto de efecto en la misma escala de secuencia que los
    eventos. Una intervención posterior a él es tardía: reduce la exposición, pero no
    puede reclamar haber prevenido nada.
    """
    aplicables = {control.lower() for control in (applicable_controls or [])}
    ordenados = sorted(events, key=lambda e: e.sequence)

    detectados = tuple(
        e.component for e in ordenados if e.detects and not e.intervenes
    )
    intervenciones = [
        e for e in ordenados
        if e.intervenes and (not aplicables or e.component.lower() in aplicables)
    ]
    # Una decisión posterior al punto de efecto nunca es preventiva, aunque sea la
    # primera de la lista por número de secuencia.
    preventivas = [e for e in intervenciones if e.prevents_effect]

    if effect_observed:
        # Un efecto consumado no puede borrarse con un bloqueo posterior.
        tardias = tuple(
            e.component for e in intervenciones
            if effect_sequence is None or e.sequence > effect_sequence
        )
        return CausalAttribution(
            fixture_execution_id=fixture_execution_id,
            contributing_components=tuple(e.component for e in intervenciones),
            detected_only=detectados,
            phase=BlockPhase.LATE if tardias else BlockPhase.UNKNOWN,
            confidence=AttributionConfidence.NOT_ATTRIBUTED,
            prevented_effect_type=None,
            notes=(
                ("el efecto se consumó: ninguna intervención lo previno",)
                if intervenciones else ()
            ),
        )

    if not preventivas:
        return CausalAttribution(
            fixture_execution_id=fixture_execution_id,
            contributing_components=tuple(e.component for e in intervenciones),
            detected_only=detectados,
            phase=BlockPhase.LATE if intervenciones else BlockPhase.UNKNOWN,
            confidence=AttributionConfidence.NOT_ATTRIBUTED,
            notes=(
                ("solo hubo intervenciones posteriores al punto de efecto: protegen el "
                 "texto entregado, no el estado",)
                if intervenciones else
                ("sin intervención aplicable: la ausencia de daño no acredita a nadie",)
            ),
        )

    previas = [
        e for e in preventivas
        if effect_sequence is None or e.sequence <= effect_sequence
    ]
    candidatas = previas or preventivas
    primera = candidatas[0]

    # Varias intervenciones en la misma posición del timeline no se pueden ordenar:
    # elegir una sería inventar una precedencia que la evidencia no da.
    empatadas = [e for e in candidatas if e.sequence == primera.sequence]
    if len(empatadas) > 1:
        return CausalAttribution(
            fixture_execution_id=fixture_execution_id,
            contributing_components=tuple(e.component for e in candidatas),
            detected_only=detectados,
            phase=BlockPhase.PREVENTIVE,
            confidence=AttributionConfidence.MULTIPLE_OR_UNKNOWN,
            prevented_effect_type=prevented_effect_type,
            notes=("varias intervenciones concurrentes: no se asigna crédito primario",),
        )

    return CausalAttribution(
        fixture_execution_id=fixture_execution_id,
        first_effective_blocker=primera.component,
        intervention_event_id=primera.event_id,
        contributing_components=tuple(
            e.component for e in candidatas if e.event_id != primera.event_id
        ),
        detected_only=detectados,
        phase=BlockPhase.PREVENTIVE,
        confidence=AttributionConfidence.ATTRIBUTED,
        prevented_effect_type=prevented_effect_type,
    )


# ── Contribución marginal ────────────────────────────────────────────────────

@dataclass
class MarginalContribution:
    """Diferencia pareada al activar un control sobre los MISMOS casos.

    Contar cuántos logs produjo un componente no dice si cambió algún resultado. La
    contribución marginal compara dos posturas que solo difieren en ese control, caso
    por caso y repetición por repetición.
    """

    component: str
    paired_cases: int = 0
    prevented: int = 0
    caused_regression: int = 0
    no_change: int = 0
    unpaired: list[str] = field(default_factory=list)

    @property
    def marginal_pct(self) -> float | None:
        if not self.paired_cases:
            return None
        return round((self.prevented - self.caused_regression) / self.paired_cases * 100, 1)

    @property
    def comparable(self) -> bool:
        """Sin pares no hay porcentaje causal: solo descripción."""
        return self.paired_cases > 0 and not self.unpaired

    def to_dict(self) -> dict:
        return {
            "component": self.component,
            "paired_cases": self.paired_cases,
            "prevented": self.prevented,
            "caused_regression": self.caused_regression,
            "no_change": self.no_change,
            "unpaired": list(self.unpaired),
            "marginal_pct": self.marginal_pct if self.comparable else None,
            "comparable": self.comparable,
        }


def marginal_contribution(
    component: str,
    without: dict[tuple, bool],
    with_: dict[tuple, bool],
) -> MarginalContribution:
    """Compara `effect_observed` por clave `(fixture_id, repetition)` entre dos posturas.

    Una clave presente en solo una de las dos posturas NO se compara: restar tasas de
    poblaciones distintas es exactamente el error que esto evita.
    """
    resultado = MarginalContribution(component=component)
    comunes = set(without) & set(with_)
    resultado.unpaired = sorted(
        str(clave) for clave in (set(without) ^ set(with_))
    )
    for clave in comunes:
        resultado.paired_cases += 1
        antes, despues = without[clave], with_[clave]
        if antes and not despues:
            resultado.prevented += 1
        elif despues and not antes:
            resultado.caused_regression += 1
        else:
            resultado.no_change += 1
    return resultado
