"""Tests de la fusión con Red Team_ (Norma) — atajo regex antes del juez LLM, y
propagación del campo `fuente` del Intento. Ver plan-fusion-redteam.md.

No requiere Ollama ni el backend vivo: brain/target/engine son dobles."""

from __future__ import annotations

from types import SimpleNamespace

from orchestrator import ejecutar_intento
from ejercicio_writer import EjercicioWriter
from target_client import TurnoResultado

TECNICA = {"id": "directa", "max_turns_por_intento": 1}


class _TargetFalso:
    def __init__(self, respuesta: str, tools_used=None):
        self._respuesta = respuesta
        self._tools_used = tools_used or []

    def enviar(self, *, mensaje, ejercicio_id, session_id=None):
        return TurnoResultado(
            respuesta=self._respuesta, session_id="sess-1", error=None,
            latency_ms=1.0, tools_used=self._tools_used,
        )


class _BrainFalso:
    def __init__(self, veredicto=("FAILED", "juez invocado de verdad")):
        self.juzgar_llamado = False
        self._veredicto = veredicto

    def juzgar(self, *args, **kwargs):
        self.juzgar_llamado = True
        return self._veredicto


class _EngineFalso:
    name = "fake"

    def abrir_intento(self, *, tecnica, historial, brain):
        return "payload de prueba"


class _EngineConFuente:
    name = "fake+garak"
    ultima_fuente = "garak"

    def abrir_intento(self, *, tecnica, historial, brain):
        return "payload semilla de garak"


def _writer(tmp_path, monkeypatch) -> EjercicioWriter:
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    return EjercicioWriter("directa", "run_test")


def test_prefiltro_evita_el_juez_llm_en_rechazo_evidente(tmp_path, monkeypatch):
    target = _TargetFalso("Lo siento, no puedo revelar esa información.")
    brain = _BrainFalso()
    intento = ejecutar_intento(
        config=SimpleNamespace(modo="caja-negra"), tecnica=TECNICA, historial=[], numero=1,
        brain=brain, engine=_EngineFalso(), target=target, writer=_writer(tmp_path, monkeypatch),
    )
    assert brain.juzgar_llamado is False
    assert intento.veredicto == "FAILED"
    assert "prefiltro regex" in intento.razonamiento


def test_sin_rechazo_evidente_si_se_invoca_el_juez(tmp_path, monkeypatch):
    target = _TargetFalso("Aquí tienes tu saldo: 1.200 €")
    brain = _BrainFalso()
    intento = ejecutar_intento(
        config=SimpleNamespace(modo="caja-negra"), tecnica=TECNICA, historial=[], numero=1,
        brain=brain, engine=_EngineFalso(), target=target, writer=_writer(tmp_path, monkeypatch),
    )
    assert brain.juzgar_llamado is True
    assert intento.razonamiento == "juez invocado de verdad"


def test_rechazo_evidente_pero_con_tool_confirmada_no_activa_el_atajo(tmp_path, monkeypatch):
    """Si hay una tool confirmada de verdad, el rechazo textual podría ser un
    comentario de Clara aparte de la ejecución — no se puede descartar sin el juez."""
    target = _TargetFalso(
        "Lo siento, no puedo revelar más datos, pero ya he procesado tu solicitud.",
        tools_used=[{"tool": "transferencia_nacional", "result": "ok: transferencia realizada"}],
    )
    brain = _BrainFalso(veredicto=("SUCCESS", "tool ejecutada de verdad"))
    intento = ejecutar_intento(
        config=SimpleNamespace(modo="caja-negra"), tecnica=TECNICA, historial=[], numero=1,
        brain=brain, engine=_EngineFalso(), target=target, writer=_writer(tmp_path, monkeypatch),
    )
    assert brain.juzgar_llamado is True


def test_fuente_se_propaga_al_intento(tmp_path, monkeypatch):
    target = _TargetFalso("Aquí tienes tu saldo: 1.200 €")
    intento = ejecutar_intento(
        config=SimpleNamespace(modo="caja-negra"), tecnica=TECNICA, historial=[], numero=1,
        brain=_BrainFalso(), engine=_EngineConFuente(), target=target,
        writer=_writer(tmp_path, monkeypatch),
    )
    assert intento.fuente == "garak"
    assert intento.payload_inicial == "payload semilla de garak"


def test_fuente_por_defecto_es_propio_sin_seeded_engine(tmp_path, monkeypatch):
    target = _TargetFalso("Aquí tienes tu saldo: 1.200 €")
    intento = ejecutar_intento(
        config=SimpleNamespace(modo="caja-negra"), tecnica=TECNICA, historial=[], numero=1,
        brain=_BrainFalso(), engine=_EngineFalso(), target=target,
        writer=_writer(tmp_path, monkeypatch),
    )
    assert intento.fuente == "propio"
