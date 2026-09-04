"""Latencia por cohorte: un bloqueo de 4 ms y una respuesta de 16 s no promedian.

P15: `proxy-full` publicaba p50 ≈ 6,8 s frente a los 7,7 s del baseline, y parecía más
rápido. Pero esa mediana incluía 115 bloqueos pre-modelo de 3–5 ms; sobre las 476
peticiones que sí llegaron al modelo, la p50 real era 8,2 s. Añadir bloqueos rápidos
bajaba la métrica global mientras la experiencia del usuario legítimo empeoraba.

La regla: **nunca se comparan cohortes distintas**. Un bloqueo pre-modelo no compite
con una respuesta servida; compite con otro bloqueo pre-modelo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class LatencyCohort(_Str):
    """Camino que recorrió la petición. Determina con qué es comparable."""

    #: Bloqueada antes de invocar al modelo. Milisegundos.
    PRE_MODEL_BLOCK = "PRE_MODEL_BLOCK"
    #: Llegó al modelo y se sirvió sin tools.
    MODEL_PATH_ALLOWED = "MODEL_PATH_ALLOWED"
    #: Llegó al modelo e invocó al menos una tool.
    TOOL_PATH = "TOOL_PATH"
    #: El modelo respondió y un control de salida sustituyó o recortó la respuesta.
    POST_MODEL_BLOCK = "POST_MODEL_BLOCK"
    #: Terminó en error o timeout. Su duración está censurada.
    ERROR = "ERROR"


#: Cohortes en las que la latencia refleja la experiencia de un usuario atendido.
ALLOWED_PATH_COHORTS = (LatencyCohort.MODEL_PATH_ALLOWED, LatencyCohort.TOOL_PATH)


def classify_cohort(
    *,
    model_invoked: bool,
    execution_status: str = "COMPLETED",
    output_blocked: bool = False,
    tools_used: int = 0,
) -> LatencyCohort:
    if execution_status != "COMPLETED":
        return LatencyCohort.ERROR
    if not model_invoked:
        return LatencyCohort.PRE_MODEL_BLOCK
    if output_blocked:
        return LatencyCohort.POST_MODEL_BLOCK
    return LatencyCohort.TOOL_PATH if tools_used else LatencyCohort.MODEL_PATH_ALLOWED


def percentile(values: list[float], q: float) -> float | None:
    """Percentil por interpolación lineal sobre las observaciones reales."""
    if not values:
        return None
    ordenados = sorted(values)
    if len(ordenados) == 1:
        return round(ordenados[0], 1)
    posicion = q * (len(ordenados) - 1)
    inferior = math.floor(posicion)
    superior = math.ceil(posicion)
    peso = posicion - inferior
    return round(ordenados[inferior] * (1 - peso) + ordenados[superior] * peso, 1)


@dataclass
class LatencyDistribution:
    """Distribución de una cohorte. Con `n` visible: una media sin `n` no dice nada."""

    cohort: str
    observations: list[float] = field(default_factory=list)
    censored: int = 0

    @property
    def n(self) -> int:
        return len(self.observations)

    @property
    def mean_ms(self) -> float | None:
        return round(sum(self.observations) / self.n, 1) if self.n else None

    def p(self, q: float) -> float | None:
        return percentile(self.observations, q)

    def to_dict(self) -> dict:
        return {
            "cohort": self.cohort,
            "n": self.n,
            "censored": self.censored,
            "mean_ms": self.mean_ms,
            "p50_ms": self.p(0.50),
            "p95_ms": self.p(0.95),
            "p99_ms": self.p(0.99),
        }


def summarize(observations: list[dict]) -> dict:
    """Agrupa por cohorte. Nunca devuelve un único número global.

    Cada observación es `{"cohort": ..., "latency_ms": ..., "censored": bool}`.
    """
    por_cohorte: dict[str, LatencyDistribution] = {}
    for observacion in observations:
        cohorte = str(observacion.get("cohort") or LatencyCohort.ERROR)
        distribucion = por_cohorte.setdefault(cohorte, LatencyDistribution(cohort=cohorte))
        if observacion.get("censored"):
            distribucion.censored += 1
        latencia = observacion.get("latency_ms")
        if latencia is not None:
            distribucion.observations.append(float(latencia))

    allowed = LatencyDistribution(cohort="ALLOWED_PATH")
    for cohorte in ALLOWED_PATH_COHORTS:
        origen = por_cohorte.get(str(cohorte))
        if origen:
            allowed.observations.extend(origen.observations)

    return {
        "by_cohort": {clave: dist.to_dict() for clave, dist in sorted(por_cohorte.items())},
        # La vista que importa para la experiencia del usuario atendido. Es la que un
        # agregado global escondía: añadir bloqueos rápidos no puede mejorarla.
        "allowed_path": allowed.to_dict(),
        "total_observations": sum(dist.n for dist in por_cohorte.values()),
    }


@dataclass(frozen=True)
class LatencyGates:
    """Umbrales versionados del coste de las defensas."""

    schema_version: int = 1
    #: Overhead de los controles que no llaman al LLM.
    max_non_llm_overhead_p95_ms: float = 100.0
    #: Tolerancia del camino permitido frente al baseline.
    allowed_path_absolute_ms: float = 2000.0
    allowed_path_relative_pct: float = 20.0

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "max_non_llm_overhead_p95_ms": self.max_non_llm_overhead_p95_ms,
            "allowed_path_absolute_ms": self.allowed_path_absolute_ms,
            "allowed_path_relative_pct": self.allowed_path_relative_pct,
        }


def compare_allowed_path(
    baseline: dict, defended: dict, gates: LatencyGates | None = None,
) -> dict:
    """Compara SOLO el camino permitido entre dos posturas.

    Es la única comparación honesta: el agregado global premia bloquear más.
    """
    gates = gates or LatencyGates()
    base = (baseline.get("allowed_path") or {}).get("p95_ms")
    defendida = (defended.get("allowed_path") or {}).get("p95_ms")
    n_base = (baseline.get("allowed_path") or {}).get("n", 0)
    n_defendida = (defended.get("allowed_path") or {}).get("n", 0)

    if base is None or defendida is None or not n_base or not n_defendida:
        return {
            "comparable": False,
            "reason": "alguna de las posturas no tiene observaciones de camino permitido",
            "baseline_p95_ms": base, "defended_p95_ms": defendida,
            "baseline_n": n_base, "defended_n": n_defendida,
        }

    tolerancia = max(gates.allowed_path_absolute_ms, base * gates.allowed_path_relative_pct / 100)
    delta = round(defendida - base, 1)
    return {
        "comparable": True,
        "baseline_p95_ms": base,
        "defended_p95_ms": defendida,
        "baseline_n": n_base,
        "defended_n": n_defendida,
        "delta_p95_ms": delta,
        "tolerance_ms": round(tolerancia, 1),
        "within_gate": delta <= tolerancia,
    }
