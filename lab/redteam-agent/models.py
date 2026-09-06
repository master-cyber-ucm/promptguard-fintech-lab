"""Tipos compartidos del Agente de red-team — ver CONTEXT.md § Agente de red-team."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Turno:
    """Un turn dentro de un Intento (los Intentos multi-turn tienen varios)."""
    mensaje: str
    respuesta: str
    session_id: str
    error: str | None = None
    latency_ms: float = 0.0
    tools_used: list = field(default_factory=list)


@dataclass
class Intento:
    numero: int
    turnos: list[Turno]
    veredicto: str  # SUCCESS | FAILED | ERROR
    razonamiento: str
    soc_eventos: list[dict] = field(default_factory=list)  # solo en Modo caja gris
    fuente: str = "propio"  # "propio" | nombre de la Fuente de semillas (ver sources/), solo si --seed-source

    @property
    def payload_inicial(self) -> str:
        return self.turnos[0].mensaje if self.turnos else ""

    @property
    def respuesta_final(self) -> str:
        if not self.turnos:
            return ""
        ultimo = self.turnos[-1]
        if ultimo.respuesta:
            return ultimo.respuesta
        return f"[BLOQUEADO/ERROR] {ultimo.error}" if ultimo.error else "[sin respuesta]"

    @property
    def session_id(self) -> str:
        return self.turnos[-1].session_id if self.turnos else ""


@dataclass
class Ejercicio:
    tecnica_id: str
    nombre: str
    objetivo: str
    intentos: list[Intento] = field(default_factory=list)
    exito: bool = False
    detenido_por: str = ""  # "bypass" | "presupuesto_agotado"

    @property
    def n_intentos(self) -> int:
        return len(self.intentos)


@dataclass
class Campania:
    run_folder_name: str
    config: dict
    ejercicios: list[Ejercicio] = field(default_factory=list)
    inicio: str = ""
    fin: str = ""
