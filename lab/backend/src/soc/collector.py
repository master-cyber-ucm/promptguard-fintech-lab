"""SocCollector — recoge los Analysis Events de un turno y los vuelca una sola vez.

Viaja en los dos portadores que el pipeline ya crea por turno: `StageContext` (llega a
las stages) y `Deps` (llega a todas las tools, y por tanto al Tool Gatekeeper). Cada
componente llama a `add()`; el orquestador llama a `flush()` al cerrar el turno.

Se eligió un collector en vez de llamadas sueltas en cada sitio porque la regla "emitir
siempre, también en ALLOW" tiene que ser estructura y no convención: el bug que existía
antes en `chat.py` era exactamente el de una convención que se olvidó.

**El SOC nunca tumba el chat.** `flush()` traga cualquier excepción y sigue. Un fallo de
observabilidad no puede convertirse en un fallo de servicio.
"""

from __future__ import annotations

import logging
import time
from pathlib import PurePosixPath
from typing import Any, Optional

from . import store
from .knowledge import severidad_de, taxonomia_de_fixture

logger = logging.getLogger(__name__)

COMPONENTES = (
    "input_sanitizer",
    "pii_shield",
    "document_sanitizer",
    "tool_gatekeeper",
    "output_auditor",
    "leak_guard",
)

OBJETIVOS = ("prompt", "documento", "tool", "respuesta")


def run_id_desde_audit_subdir(audit_subdir: Optional[str]) -> Optional[str]:
    """Extrae el identificador de corrida de la ruta que envía `run_attack_suite.py`.

    El runner manda `/app/audit/runs/{run}/{endpoint}`; nos quedamos con `{run}`. Si la
    ruta no tiene esa forma (sesión manual con subdirectorio propio), se usa el nombre
    del directorio padre, que es lo más parecido a una corrida que hay.
    """
    if not audit_subdir:
        return None
    partes = PurePosixPath(audit_subdir.replace("\\", "/")).parts
    if "runs" in partes:
        i = partes.index("runs")
        if i + 1 < len(partes):
            return partes[i + 1]
    return PurePosixPath(audit_subdir).parent.name or None


def origen_desde_run_id(run_id: Optional[str]) -> str:
    """Deriva el Origen del Turn a partir del nombre de la carpeta de corrida.

    Tres valores posibles (ver CONTEXT.md § Origen): sin `run_id` es una sesión manual
    (`interactivo`); con `run_id` es o bien un Suite Run de `run_attack_suite.py`
    (`suite`) o una Campaña del Agente de red-team (`redteam-agent`), distinguibles por
    el sufijo `_redteam-agent` que el orquestador del agente añade al nombre de la
    carpeta (`lab/audit/runs/{timestamp}_redteam-agent/`).
    """
    if not run_id:
        return "interactivo"
    if run_id.endswith("_redteam-agent"):
        return "redteam-agent"
    return "suite"


class SocCollector:
    """Acumulador de un turno. Barato de crear: uno por petición."""

    def __init__(
        self,
        *,
        session_id: str,
        user_id: str,
        endpoint: str,
        audit_subdir: Optional[str] = None,
        fixture_id: Optional[str] = None,
        fixture_kind: Optional[str] = None,
        fixture_expected_result: Optional[str] = None,
        vulnerable: bool = False,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.endpoint = endpoint
        self.run_id = run_id_desde_audit_subdir(audit_subdir)
        self.origen = origen_desde_run_id(self.run_id)
        self.fixture_id = fixture_id
        self.fixture_kind = fixture_kind
        self.fixture_expected_result = fixture_expected_result
        self.vulnerable = vulnerable
        self.postura = ""
        self.eventos: list[dict[str, Any]] = []
        self._t0 = time.time()
        self._volcado = False

    # -- captura --

    def add(
        self,
        *,
        componente: str,
        objetivo: str,
        accion: str,
        razon: Optional[str] = None,
        regla: Optional[str] = None,
        confianza: Optional[float] = None,
        attack_type: Optional[str] = None,
        detalle: Optional[dict] = None,
        latencia_ms: Optional[float] = None,
    ) -> None:
        """Registra que un componente examinó un objetivo y decidió algo.

        Se llama también cuando la acción es ALLOW. Un componente que deja pasar es
        información: sin ese evento no se puede distinguir "lo miró y lo permitió" de
        "no lo miró nadie", que es justamente la diferencia que el SOC existe para
        enseñar.
        """
        self.eventos.append({
            "componente": componente,
            "objetivo": objetivo,
            "accion": accion,
            "razon": razon,
            "regla": regla,
            "confianza": confianza,
            "attack_type": attack_type,
            "detalle": detalle,
            "latencia_ms": latencia_ms,
        })

    def add_decision(self, componente: str, objetivo: str, decision, **extra) -> None:
        """Atajo para componentes que ya devuelven un `PromptDecision`."""
        self.add(
            componente=componente,
            objetivo=objetivo,
            accion=getattr(decision, "action", "ALLOW"),
            razon=getattr(decision, "reason", None),
            regla=getattr(decision, "matched_rule", None),
            confianza=getattr(decision, "confidence", None),
            attack_type=getattr(decision, "attack_type", None),
            **extra,
        )

    def set_postura(self, postura: str) -> None:
        """Qué defensas estaban activas en este turno.

        Es lo que permite que un turno con cero eventos se lea como ausencia de defensa
        y no como fallo de captura.
        """
        self.postura = postura

    # -- volcado --

    def flush(
        self,
        *,
        prompt: str,
        respuesta: Optional[str] = None,
        modelo: Optional[str] = None,
        latencia_total_ms: Optional[float] = None,
        audit_file: Optional[str] = None,
    ) -> Optional[int]:
        """Escribe el turno y sus eventos. Devuelve el id, o `None` si algo falló.

        Nunca propaga una excepción: si el SOC no puede escribir, el turno del cliente
        ya se ha servido igualmente y eso es lo que importa.
        """
        if self._volcado:
            return None
        self._volcado = True
        try:
            categoria, subcategoria = taxonomia_de_fixture(self.fixture_id)
            turn_id = store.record_turn(
                turno={
                    "session_id": self.session_id,
                    "user_id": self.user_id,
                    "endpoint": self.endpoint,
                    "origen": self.origen,
                    "run_id": self.run_id,
                    "postura": self.postura,
                    "vulnerable": self.vulnerable,
                    "prompt": prompt,
                    "respuesta": respuesta,
                    "modelo": modelo,
                    "latencia_total_ms": (
                        latencia_total_ms
                        if latencia_total_ms is not None
                        else (time.time() - self._t0) * 1000
                    ),
                    "fixture_id": self.fixture_id,
                    "fixture_kind": self.fixture_kind,
                    "fixture_expected_result": self.fixture_expected_result,
                    "categoria": categoria,
                    "subcategoria": subcategoria,
                    "audit_file": audit_file,
                },
                eventos=self.eventos,
            )
            severidad, origen_sev = severidad_de(
                self.fixture_id, categoria, self._primer_attack_type()
            )
            store.raise_alerts(turn_id, severidad, origen_sev)
            return turn_id
        except Exception:  # noqa: BLE001 — deliberado: el SOC no puede tumbar el chat
            logger.exception("[soc] no se pudo registrar el turno (el chat no se ve afectado)")
            return None

    def _primer_attack_type(self) -> Optional[str]:
        for ev in self.eventos:
            if ev.get("attack_type"):
                return ev["attack_type"]
        return None


def add_safe(collector: Optional[SocCollector], **kwargs) -> None:
    """Emite un evento si hay collector, y nunca falla.

    Los componentes la usan en lugar de `collector.add(...)` para no tener que
    comprobar `if collector is not None` en cada punto de decisión ni arriesgarse a
    que un fallo de observabilidad rompa una defensa.
    """
    if collector is None:
        return
    try:
        collector.add(**kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("[soc] evento descartado")
