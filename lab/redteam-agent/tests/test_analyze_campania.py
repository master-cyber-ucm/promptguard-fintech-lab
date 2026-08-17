"""Tests de B1 (plan de excelencia) — parsing del Analyze Pass offline.

No invoca al juez (eso requiere Ollama vivo) — cubre lo determinista: parsear un
fichero B7 real y el fallback a run.json cuando B7 no existe.
"""

from __future__ import annotations

import json

from analyze_campania import _parsear_b7, _parsear_run_json_fallback, cargar_intentos
from ejercicio_writer import EjercicioWriter


def test_parsear_b7_recupera_intentos_y_turnos(tmp_path, monkeypatch):
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("directa", "20260817_000000_redteam-agent")
    writer.abrir_ejercicio("Prompt Injection Directa", "Objetivo", "autorreflexivo", "caja-negra")
    writer.abrir_intento(1)
    writer.append_turno(1, "payload 1", "respuesta 1")
    writer.cerrar_intento("FAILED", "no funcionó")
    writer.abrir_intento(2)
    writer.append_turno(1, "payload 2a", "respuesta 2a")
    writer.append_turno(2, "payload 2b", "respuesta 2b")
    writer.cerrar_intento("SUCCESS", "sí funcionó")

    intentos = _parsear_b7(writer.path)
    assert len(intentos) == 2
    assert intentos[0]["numero"] == 1
    assert intentos[0]["veredicto_original"] == "FAILED"
    assert len(intentos[0]["turnos"]) == 1
    assert intentos[1]["numero"] == 2
    assert intentos[1]["veredicto_original"] == "SUCCESS"
    assert len(intentos[1]["turnos"]) == 2  # multi-turno: 2 turnos en el mismo Intento
    assert intentos[1]["turnos"][0]["mensaje"] == "payload 2a"
    assert intentos[1]["turnos"][1]["respuesta"] == "respuesta 2b"


def test_fallback_run_json_cuando_no_hay_b7(tmp_path, monkeypatch):
    run_folder = tmp_path / "20260101_000000_redteam-agent"
    run_folder.mkdir()
    (run_folder / "run.json").write_text(json.dumps({
        "ejercicios": [{
            "tecnica_id": "directa",
            "intentos": [
                {"numero": 1, "veredicto": "FAILED", "razonamiento": "r1",
                 "payload_inicial": "p1", "respuesta_final": "resp1"},
            ],
        }],
    }), encoding="utf-8")
    monkeypatch.setattr("analyze_campania.RUNS_DIR", tmp_path)
    monkeypatch.setattr("analyze_campania.EJERCICIOS_DIR", tmp_path / "sin_b7")  # no existe

    intentos, fuente = cargar_intentos("20260101_000000_redteam-agent", "directa")
    assert fuente == "run.json"
    assert len(intentos) == 1
    assert intentos[0]["turnos"] == [{"mensaje": "p1", "respuesta": "resp1"}]


def test_b7_tiene_prioridad_sobre_run_json(tmp_path, monkeypatch):
    ejercicios_dir = tmp_path / "ejercicios"
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", ejercicios_dir)
    monkeypatch.setattr("analyze_campania.EJERCICIOS_DIR", ejercicios_dir)
    monkeypatch.setattr("analyze_campania.RUNS_DIR", tmp_path / "runs")

    writer = EjercicioWriter("directa", "run_x")
    writer.abrir_ejercicio("Directa", "Objetivo", "autorreflexivo", "caja-negra")
    writer.abrir_intento(1)
    writer.append_turno(1, "del B7", "resp B7")
    writer.cerrar_intento("FAILED", "razon B7")

    intentos, fuente = cargar_intentos("run_x", "directa")
    assert fuente == "b7"
    assert intentos[0]["turnos"][0]["mensaje"] == "del B7"


def test_no_hay_datos_devuelve_vacio(tmp_path, monkeypatch):
    monkeypatch.setattr("analyze_campania.EJERCICIOS_DIR", tmp_path / "sin_ejercicios")
    monkeypatch.setattr("analyze_campania.RUNS_DIR", tmp_path / "sin_runs")
    intentos, fuente = cargar_intentos("run_inexistente", "directa")
    assert intentos == []
