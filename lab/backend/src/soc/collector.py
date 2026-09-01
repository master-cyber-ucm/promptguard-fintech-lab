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
import uuid
from pathlib import PurePosixPath
from typing import Any, Optional

from src.models.evaluation import Enforcement

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


def normalizar_decision(componente: str, accion: str, regla: Optional[str] = None) -> str:
    """Traduce el dialecto del SOC al vocabulario único de la evidencia.

    El SOC habla `ALLOW | SUSPICIOUS | BLOCK` porque su unidad es la alerta. La
    evaluación necesita saber *qué* hizo el control, no solo cómo de grave fue: una
    denegación del Gatekeeper, una aprobación pendiente y una tokenización del PII
    Shield tienen consecuencias distintas sobre el efecto y no pueden compartir
    etiqueta. Ambas proyecciones se derivan del mismo evento, no una de la otra.
    """
    accion = (accion or "ALLOW").upper()
    regla = (regla or "").lower()
    if componente == "tool_gatekeeper":
        if accion == "BLOCK":
            return "DENY"
        if accion == "SUSPICIOUS" and regla == "requires_approval":
            return "REQUIRE_APPROVAL"
    if componente == "pii_shield" and accion == "SUSPICIOUS":
        return "REDACT"
    return accion


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
        # Postura estructurada: la cadena legible sigue alimentando el panel, pero la
        # evaluación necesita comparar configuraciones sin parsear texto.
        self.postura_efectiva: dict[str, Any] = {}
        # Correlación estable de toda la evidencia de esta ejecución (P01/P09).
        self.fixture_execution_id: Optional[str] = None
        self.turn_index: int = 1
        # `SHADOW_MODE=true`: los componentes deciden pero no aplican. Se marca en el
        # propio evento para que ninguna lectura posterior pueda confundir una decisión
        # registrada con una intervención efectiva.
        self.shadow = False
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
        enforcement: Optional[str] = None,
    ) -> None:
        """Registra que un componente examinó un objetivo y decidió algo.

        Se llama también cuando la acción es ALLOW. Un componente que deja pasar es
        información: sin ese evento no se puede distinguir "lo miró y lo permitió" de
        "no lo miró nadie", que es justamente la diferencia que el SOC existe para
        enseñar.

        Cada evento nace con un `event_id` estable y un número de secuencia monotónico:
        son lo que permite que una atribución causal cite la evidencia concreta que la
        sostiene en vez de una razón en texto libre.
        """
        if enforcement is None:
            enforcement = (
                Enforcement.SHADOW.value
                if self.shadow and (accion or "").upper() != "ALLOW"
                else Enforcement.ENFORCED.value
            )
        self.eventos.append({
            "event_id": uuid.uuid4().hex,
            "sequence": len(self.eventos),
            "componente": componente,
            "objetivo": objetivo,
            "accion": accion,
            "decision": normalizar_decision(componente, accion, regla),
            "enforcement": enforcement,
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

    def set_postura(self, postura: str, efectiva: Optional[dict] = None) -> None:
        """Qué defensas estaban activas en este turno.

        Es lo que permite que un turno con cero eventos se lea como ausencia de defensa
        y no como fallo de captura. `efectiva` es la misma información en forma
        estructurada: la Postura experimental que la evaluación compara entre targets
        sin interpretar una cadena.
        """
        self.postura = postura
        if efectiva is not None:
            self.postura_efectiva = dict(efectiva)
            self.shadow = bool(efectiva.get("shadow"))

    # -- proyección de evidencia --

    def snapshot(self) -> list[dict[str, Any]]:
        """Proyecta los eventos al contrato que consume el Analyze Pass.

        Session File y SOC salen de esta misma lista en memoria: no hay un dialecto
        que reconstruya decisiones a mano y otro que las capture de verdad. Antes el
        Session File rehacía tres decisiones en `chat.py` y se perdían el Input
        Sanitizer y el Tool Gatekeeper — divergencia que hacía imposible atribuir una
        contención a la capa que realmente actuó.
        """
        return [
            {
                "event_id": ev["event_id"],
                "sequence": ev["sequence"],
                "component": ev["componente"],
                "target": ev["objetivo"],
                "action": ev["decision"],
                "soc_action": ev["accion"],
                "enforcement": ev["enforcement"],
                "reason": ev.get("razon"),
                "rule": ev.get("regla"),
                "attack_type": ev.get("attack_type"),
                "detail": ev.get("detalle"),
                "latency_ms": ev.get("latencia_ms"),
            }
            for ev in self.eventos
        ]

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
