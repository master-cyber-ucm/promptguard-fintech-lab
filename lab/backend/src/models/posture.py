"""Postura experimental — qué configuración corrió de verdad, y con quién se compara.

P02: una comparación solo es causal cuando baseline y defended difieren
*exclusivamente* en el vector de controles. `simple-prompt` frente a `proxy-full`
cambia además system prompt, contexto inyectado y catálogo de tools: la diferencia que
mide no es la defensa, es el agente entero.

`TargetPostureV1` separa dos cosas que hasta ahora se confundían:

* **requested** — lo que el runner pidió.
* **effective** — lo que el backend aplicó, con los hashes de aquello que define el
  agente (prompt, contexto, catálogo de tools, policy, configuración de modelo).

El `comparable_fingerprint` se calcula sobre todo *salvo* los controles defensivos. Dos
posturas con el mismo fingerprint son un contrafactual válido; con fingerprints
distintos, cualquier delta que se publique estaría mezclando factores.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

#: Controles externos del pipeline. Son la ÚNICA dimensión que puede variar dentro de
#: un grupo comparable.
DEFENSE_CONTROLS = (
    "input_sanitizer",
    "document_sanitizer",
    "document_structural_detector",
    "pii_shield",
    "tool_gatekeeper",
    "output_auditor",
    "leak_guard",
    "separacion_semantica",
    "separacion_tool_framing",
    "shadow",
)

#: Endpoints pedagógicos: existen para enseñar la progresión del agente, no para servir
#: de línea base causal del proxy. Se informan aparte.
PEDAGOGICAL_TARGETS = (
    "simple-prompt",
    "complex-prompt",
    "complex-with-context",
    "complex-with-document",
)

#: La única línea base causal del proxy: todos los controles externos apagados sobre el
#: mismo agente, el mismo prompt y el mismo catálogo de tools que la postura defendida.
CAUSAL_BASELINE_TARGET = "proxy-baseline"


def _digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


@dataclass
class TargetPosture:
    """Postura de un target concreto, con lo pedido y lo efectivamente aplicado."""

    schema_version: int = 1
    target: str = ""
    requested: dict = field(default_factory=dict)
    effective: dict = field(default_factory=dict)

    # -- proyecciones ------------------------------------------------------

    @property
    def controls(self) -> dict:
        return {name: bool(self.effective.get(name)) for name in DEFENSE_CONTROLS}

    @property
    def invariants(self) -> dict:
        """Todo lo que NO puede variar dentro de un grupo comparable."""
        return {
            key: value
            for key, value in sorted(self.effective.items())
            if key not in DEFENSE_CONTROLS and key not in {"target", "proxy_profile"}
        }

    @property
    def comparable_fingerprint(self) -> str:
        return _digest(self.invariants)

    @property
    def is_pedagogical(self) -> bool:
        return self.target in PEDAGOGICAL_TARGETS

    @property
    def is_causal_baseline(self) -> bool:
        """Baseline significa cero controles externos, no llamarse `baseline`."""
        return not any(self.controls[name] for name in DEFENSE_CONTROLS if name != "shadow")

    def divergences(self) -> list[str]:
        """Controles cuya postura solicitada no coincide con la aplicada.

        Una divergencia es un error de instrumentación: el experimento midió algo
        distinto de lo que declaró medir. No es un resultado.
        """
        return sorted(
            name for name in DEFENSE_CONTROLS
            if name in self.requested
            and bool(self.requested[name]) != bool(self.effective.get(name))
        )

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "target": self.target,
            "requested": self.requested,
            "effective": self.effective,
            "comparable_fingerprint": self.comparable_fingerprint,
            "is_pedagogical": self.is_pedagogical,
            "is_causal_baseline": self.is_causal_baseline,
            "divergences": self.divergences(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TargetPosture":
        return cls(
            schema_version=int(data.get("schema_version") or 1),
            target=str(data.get("target") or ""),
            requested=dict(data.get("requested") or {}),
            effective=dict(data.get("effective") or {}),
        )


def comparable(a: TargetPosture, b: TargetPosture) -> bool:
    """Dos posturas son comparables si solo difieren en controles defensivos."""
    return a.comparable_fingerprint == b.comparable_fingerprint


def comparison_blockers(baseline: TargetPosture, defended: TargetPosture) -> list[str]:
    """Razones por las que NO puede publicarse un delta causal entre dos posturas.

    Devolver una lista vacía es la única forma de autorizar ARR/RRR o una reducción de
    efecto. Cualquier otra cosa se informa como no comparable, no como cero mejora.
    """
    razones: list[str] = []
    if baseline.is_pedagogical or defended.is_pedagogical:
        razones.append(
            "un endpoint pedagógico no es contrafactual del proxy: cambia prompt, "
            "contexto y tools además de las defensas"
        )
    if not comparable(baseline, defended):
        diferencias = sorted(
            key for key in set(baseline.invariants) | set(defended.invariants)
            if baseline.invariants.get(key) != defended.invariants.get(key)
        )
        razones.append(f"factores no defensivos distintos: {diferencias}")
    if not baseline.is_causal_baseline:
        activos = sorted(name for name, on in baseline.controls.items() if on and name != "shadow")
        razones.append(f"la línea base no es pura: controles activos {activos}")
    if baseline.divergences():
        razones.append(f"postura solicitada≠efectiva en baseline: {baseline.divergences()}")
    if defended.divergences():
        razones.append(f"postura solicitada≠efectiva en defended: {defended.divergences()}")
    return razones
