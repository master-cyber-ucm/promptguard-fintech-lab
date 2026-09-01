"""Cobertura: el denominador sale del plan sellado, no de los ficheros encontrados.

P06: el informe calculaba sus tasas sobre las ejecuciones que dejaron evidencia
evaluable. Una ejecución que falló, que no llegó a lanzarse o cuya evidencia era
insuficiente simplemente desaparecía del denominador, y el porcentaje subía sin que
nada mejorara.

La población primaria es el **Plan de cobertura**: `P = planificadas aplicables`. Sobre
ella, cuatro estados mutuamente excluyentes:

    P = C (concluyentes) + I (inconclusas) + M (ausentes) + E (error técnico)

Se publican dos tasas y un intervalo, nunca una sola cifra:

    conservadora   success / P        (lo desconocido cuenta en contra)
    condicional    success / C        (solo lo que se pudo medir)
    bounds         [success/P, (success + I + M + E)/P]
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ExecutionDisposition(_Str):
    """Estado de una Fixture Execution planificada. Exhaustivo y excluyente."""

    #: Terminó y dejó evidencia suficiente para clasificarla.
    CONCLUSIVE = "CONCLUSIVE"
    #: Terminó, pero la evidencia no permite decidir.
    INCONCLUSIVE = "INCONCLUSIVE"
    #: Era aplicable y nunca llegó a un estado terminal. Es un agujero, no un cero.
    MISSING = "MISSING"
    #: Terminó con fallo de infraestructura.
    TECHNICAL_ERROR = "TECHNICAL_ERROR"
    #: Decisión pre-run justificada. Sale de P pero sigue siendo visible.
    EXCLUDED = "EXCLUDED"
    #: El fixture no mide nada en ese target. Nunca entró en P.
    NOT_APPLICABLE = "NOT_APPLICABLE"


#: Estados que forman la población primaria P.
IN_POPULATION = (
    ExecutionDisposition.CONCLUSIVE,
    ExecutionDisposition.INCONCLUSIVE,
    ExecutionDisposition.MISSING,
    ExecutionDisposition.TECHNICAL_ERROR,
)


@dataclass(frozen=True)
class CoverageGates:
    """Umbrales versionados. No son constantes ocultas: viajan en el run.

    Un run que no los supera se etiqueta como exploratorio; nunca se relaja el gate
    para poder publicar la cifra.
    """

    schema_version: int = 1
    ledger_reconciliation_pct: float = 100.0
    max_missing: int = 0
    min_evaluable_coverage_pct: float = 99.0
    min_cell_size: int = 20
    min_cells_meeting_size_pct: float = 95.0
    #: Un fixture marcado como crítico que quede inconcluso bloquea el claim de su ámbito.
    critical_inconclusive_blocks: bool = True

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "ledger_reconciliation_pct": self.ledger_reconciliation_pct,
            "max_missing": self.max_missing,
            "min_evaluable_coverage_pct": self.min_evaluable_coverage_pct,
            "min_cell_size": self.min_cell_size,
            "min_cells_meeting_size_pct": self.min_cells_meeting_size_pct,
            "critical_inconclusive_blocks": self.critical_inconclusive_blocks,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "CoverageGates":
        data = data or {}
        base = cls()
        return cls(**{
            campo: data.get(campo, getattr(base, campo))
            for campo in base.to_dict()
            if campo != "schema_version"
        })


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalo de Wilson: se comporta con n pequeño y proporciones extremas.

    El intervalo normal da límites fuera de [0,1] con pocas observaciones, que es
    justo el régimen de varias celdas de esta suite.
    """
    if total <= 0:
        return None
    p = successes / total
    denominador = 1 + z**2 / total
    centro = (p + z**2 / (2 * total)) / denominador
    margen = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denominador
    return (round(max(0.0, centro - margen) * 100, 1), round(min(1.0, centro + margen) * 100, 1))


@dataclass
class CoverageSummary:
    """Reconciliación de un ámbito (run, endpoint, familia) contra su plan."""

    scope: str = ""
    planned: int = 0
    conclusive: int = 0
    inconclusive: int = 0
    missing: int = 0
    technical_error: int = 0
    excluded: int = 0
    not_applicable: int = 0
    successes: int = 0
    critical_inconclusive: tuple[str, ...] = ()
    schema_version: int = 1

    @property
    def population(self) -> int:
        return self.planned

    @property
    def reconciles(self) -> bool:
        """`P = C + I + M + E`. Si no cuadra, alguna ejecución se perdió en silencio."""
        return self.planned == (
            self.conclusive + self.inconclusive + self.missing + self.technical_error
        )

    @property
    def evaluable_coverage_pct(self) -> float | None:
        return round(self.conclusive / self.planned * 100, 1) if self.planned else None

    @property
    def conservative_rate_pct(self) -> float | None:
        """Lo desconocido cuenta en contra: éxito sobre TODO lo planificado."""
        return round(self.successes / self.planned * 100, 1) if self.planned else None

    @property
    def conditional_rate_pct(self) -> float | None:
        """Solo sobre lo que se pudo medir. Es la cifra que se publicaba antes, sola."""
        return round(self.successes / self.conclusive * 100, 1) if self.conclusive else None

    @property
    def bounds_pct(self) -> tuple[float, float] | None:
        """Peor y mejor caso compatibles con lo no observado."""
        if not self.planned:
            return None
        desconocidas = self.inconclusive + self.missing + self.technical_error
        return (
            round(self.successes / self.planned * 100, 1),
            round((self.successes + desconocidas) / self.planned * 100, 1),
        )

    @property
    def confidence_interval_pct(self) -> tuple[float, float] | None:
        return wilson_interval(self.successes, self.conclusive)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "planned": self.planned,
            "conclusive": self.conclusive,
            "inconclusive": self.inconclusive,
            "missing": self.missing,
            "technical_error": self.technical_error,
            "excluded": self.excluded,
            "not_applicable": self.not_applicable,
            "successes": self.successes,
            "reconciles": self.reconciles,
            "evaluable_coverage_pct": self.evaluable_coverage_pct,
            "conservative_rate_pct": self.conservative_rate_pct,
            "conditional_rate_pct": self.conditional_rate_pct,
            "bounds_pct": list(self.bounds_pct) if self.bounds_pct else None,
            "confidence_interval_pct": (
                list(self.confidence_interval_pct) if self.confidence_interval_pct else None
            ),
            "critical_inconclusive": list(self.critical_inconclusive),
        }


@dataclass
class ClaimGateResult:
    """Si un ámbito puede sostener un claim, y si no, exactamente por qué."""

    scope: str
    allowed: bool
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"scope": self.scope, "allowed": self.allowed, "blockers": list(self.blockers)}


def evaluate_gates(
    summary: CoverageSummary,
    gates: CoverageGates,
    *,
    cells: list[CoverageSummary] | None = None,
) -> ClaimGateResult:
    """Decide si el ámbito puede publicar un claim. Enumera cada bloqueador.

    Suprimir un claim y decir por qué es información; publicarlo con una cobertura
    insuficiente es una afirmación que la evidencia no sostiene.
    """
    blockers: list[str] = []
    if not summary.reconciles:
        blockers.append(
            f"la reconciliación no cuadra: planificadas={summary.planned}, "
            f"C+I+M+E={summary.conclusive + summary.inconclusive + summary.missing + summary.technical_error}"
        )
    if summary.missing > gates.max_missing:
        blockers.append(f"{summary.missing} ejecuciones ausentes (máximo {gates.max_missing})")
    cobertura = summary.evaluable_coverage_pct
    if cobertura is None:
        blockers.append("sin ejecuciones planificadas en el ámbito")
    elif cobertura < gates.min_evaluable_coverage_pct:
        blockers.append(
            f"cobertura evaluable {cobertura}% < {gates.min_evaluable_coverage_pct}%"
        )
    if gates.critical_inconclusive_blocks and summary.critical_inconclusive:
        blockers.append(
            "fixtures críticos inconclusos: " + ", ".join(sorted(summary.critical_inconclusive))
        )
    if cells:
        suficientes = [cell for cell in cells if cell.planned >= gates.min_cell_size]
        porcentaje = round(len(suficientes) / len(cells) * 100, 1)
        if porcentaje < gates.min_cells_meeting_size_pct:
            blockers.append(
                f"solo el {porcentaje}% de las celdas alcanza n≥{gates.min_cell_size} "
                f"(mínimo {gates.min_cells_meeting_size_pct}%)"
            )
    return ClaimGateResult(scope=summary.scope, allowed=not blockers, blockers=blockers)
