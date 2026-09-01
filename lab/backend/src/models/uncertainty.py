"""Incertidumbre: un porcentaje puntual sobre 15 observaciones no es un resultado.

P14: una familia con 15 ejecuciones y 60% de bloqueo son 9 éxitos. Una sola
observación distinta mueve la cifra 6,7 puntos; presentarla frente a otra cercana
sugiere una precisión que no existe.

Dos herramientas, cada una para su caso:

* **Wilson** para una proporción simple (`n/N` de un mismo grupo).
* **Bootstrap pareado por fixture** para comparar dos posturas. La unidad de
  remuestreo es el *fixture*, no la fila: cinco repeticiones del mismo fixture están
  correlacionadas y tratarlas como cinco observaciones independientes estrecha el
  intervalo de forma artificial.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .coverage import wilson_interval


@dataclass
class ProportionEstimate:
    """Estimación con su denominador visible. Nunca solo el porcentaje."""

    label: str
    successes: int
    total: int

    @property
    def pct(self) -> float | None:
        return round(self.successes / self.total * 100, 1) if self.total else None

    @property
    def ci_pct(self) -> tuple[float, float] | None:
        return wilson_interval(self.successes, self.total)

    @property
    def half_width_pct(self) -> float | None:
        ci = self.ci_pct
        return round((ci[1] - ci[0]) / 2, 1) if ci else None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "successes": self.successes,
            "total": self.total,
            "pct": self.pct,
            "ci_pct": list(self.ci_pct) if self.ci_pct else None,
            "half_width_pct": self.half_width_pct,
        }


@dataclass
class PairedDelta:
    """Diferencia entre dos posturas sobre los MISMOS fixtures y repeticiones."""

    label: str
    delta_pct: float | None = None
    ci_pct: tuple[float, float] | None = None
    clusters: int = 0
    observations: int = 0
    resample_unit: str = "fixture"
    unpaired: list[str] = field(default_factory=list)

    @property
    def significant(self) -> bool:
        """El intervalo no cruza cero. Sin intervalo, nunca se afirma significancia."""
        if self.ci_pct is None:
            return False
        return self.ci_pct[0] > 0 or self.ci_pct[1] < 0

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "delta_pct": self.delta_pct,
            "ci_pct": list(self.ci_pct) if self.ci_pct else None,
            "clusters": self.clusters,
            "observations": self.observations,
            "resample_unit": self.resample_unit,
            "unpaired": list(self.unpaired),
            "significant": self.significant,
            "comparable": not self.unpaired and self.clusters > 0,
        }


def paired_bootstrap(
    label: str,
    baseline: dict[tuple[str, int], bool],
    defended: dict[tuple[str, int], bool],
    *,
    iterations: int = 2000,
    seed: int = 20260831,
    confidence: float = 0.95,
) -> PairedDelta:
    """Delta pareado con bootstrap por clúster de fixture.

    Las claves son `(fixture_id, repetición)`. Se remuestrean FIXTURES completos —con
    todas sus repeticiones— porque las repeticiones de un mismo caso comparten prompt,
    contexto y dificultad: no son independientes entre sí.
    """
    comunes = sorted(set(baseline) & set(defended))
    sin_pareja = sorted(str(clave) for clave in (set(baseline) ^ set(defended)))
    if not comunes:
        return PairedDelta(label=label, unpaired=sin_pareja)

    por_fixture: dict[str, list[tuple]] = {}
    for clave in comunes:
        por_fixture.setdefault(clave[0], []).append(clave)
    fixtures = sorted(por_fixture)

    def _tasa(claves: list[tuple]) -> float:
        base = sum(1 for k in claves if baseline[k])
        defendido = sum(1 for k in claves if defended[k])
        return (defendido - base) / len(claves) * 100

    observado = _tasa(comunes)

    rng = random.Random(seed)
    muestras: list[float] = []
    for _ in range(iterations):
        elegidos: list[tuple] = []
        for _ in fixtures:
            fixture = rng.choice(fixtures)
            elegidos.extend(por_fixture[fixture])
        muestras.append(_tasa(elegidos))
    muestras.sort()

    alfa = (1 - confidence) / 2
    bajo = muestras[int(alfa * len(muestras))]
    alto = muestras[min(int((1 - alfa) * len(muestras)), len(muestras) - 1)]

    return PairedDelta(
        label=label,
        delta_pct=round(observado, 1),
        ci_pct=(round(bajo, 1), round(alto, 1)),
        clusters=len(fixtures),
        observations=len(comunes),
        unpaired=sin_pareja,
    )


#: Cuántas observaciones hacen falta para que un intervalo sea informativo. Por debajo
#: de esto, la cifra se publica con su `n` bien visible y no sostiene una comparación.
MIN_INFORMATIVE_N = 20


def is_informative(estimate: ProportionEstimate) -> bool:
    return estimate.total >= MIN_INFORMATIVE_N
