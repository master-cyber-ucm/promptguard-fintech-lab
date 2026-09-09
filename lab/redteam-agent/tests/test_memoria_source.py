"""Tests de la memoria persistente entre Campañas (--seed-source memoria).
Ver sources/memoria_source.py y sources/README.md § memoria."""

from __future__ import annotations

import json

from models import Campania, Ejercicio, Intento, Turno
from sources import get_source
from sources.memoria_source import MemoriaSource, registrar_campania


def _campania(run_folder_name: str, ejercicios: list[Ejercicio]) -> Campania:
    return Campania(
        run_folder_name=run_folder_name,
        config={"attacker_model": "qwen3.5:9b"},
        ejercicios=ejercicios,
    )


def _intento(numero: int, veredicto: str, payload: str) -> Intento:
    return Intento(
        numero=numero,
        turnos=[Turno(mensaje=payload, respuesta="respuesta de Clara", session_id="s1")],
        veredicto=veredicto,
        razonamiento="razón de prueba",
    )


def test_get_source_memoria_devuelve_memoriasource():
    fuente = get_source("memoria")
    assert isinstance(fuente, MemoriaSource)
    assert fuente.name == "memoria"


def test_memoria_source_sin_fichero_no_bloquea(tmp_path):
    fuente = MemoriaSource(data_path=tmp_path / "no_existe.json")
    assert fuente.siguiente({"id": "directa"}) is None


def test_registrar_solo_guarda_success_y_continue(tmp_path):
    path = tmp_path / "memoria.json"
    ejercicio = Ejercicio(tecnica_id="directa", nombre="Directa", objetivo="obj", intentos=[
        _intento(1, "FAILED", "payload que no funcionó"),
        _intento(2, "CONTINUE", "payload que sigue abierto"),
        _intento(3, "SUCCESS", "payload que superó la salvaguarda"),
        _intento(4, "ERROR", "payload con error técnico"),
    ])
    nuevos = registrar_campania(_campania("run1", [ejercicio]), data_path=path)
    assert nuevos == 2
    data = json.loads(path.read_text(encoding="utf-8"))
    payloads = {e["payload"] for e in data["directa"]}
    assert payloads == {"payload que sigue abierto", "payload que superó la salvaguarda"}


def test_registrar_dedupe_por_payload_exacto(tmp_path):
    path = tmp_path / "memoria.json"
    ejercicio = Ejercicio(tecnica_id="directa", nombre="Directa", objetivo="obj",
                           intentos=[_intento(1, "SUCCESS", "mismo payload")])
    n1 = registrar_campania(_campania("run1", [ejercicio]), data_path=path)
    n2 = registrar_campania(_campania("run2", [ejercicio]), data_path=path)
    assert n1 == 1
    assert n2 == 0  # ya estaba, no se duplica
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["directa"]) == 1


def test_registrar_acumula_entre_campanias_distintas(tmp_path):
    path = tmp_path / "memoria.json"
    e1 = Ejercicio(tecnica_id="directa", nombre="Directa", objetivo="obj",
                    intentos=[_intento(1, "SUCCESS", "payload A")])
    e2 = Ejercicio(tecnica_id="directa", nombre="Directa", objetivo="obj",
                    intentos=[_intento(1, "SUCCESS", "payload B")])
    registrar_campania(_campania("run1", [e1]), data_path=path)
    registrar_campania(_campania("run2", [e2]), data_path=path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {e["payload"] for e in data["directa"]} == {"payload A", "payload B"}


def test_registrar_sin_nada_aprendible_no_escribe_fichero(tmp_path):
    path = tmp_path / "memoria.json"
    ejercicio = Ejercicio(tecnica_id="directa", nombre="Directa", objetivo="obj",
                           intentos=[_intento(1, "FAILED", "payload sin tracción")])
    nuevos = registrar_campania(_campania("run1", [ejercicio]), data_path=path)
    assert nuevos == 0
    assert not path.exists()


def test_memoria_source_cicla_y_prioriza_success_sobre_continue(tmp_path):
    path = tmp_path / "memoria.json"
    path.write_text(json.dumps({
        "directa": [
            {"payload": "un continue", "veredicto": "CONTINUE"},
            {"payload": "un success", "veredicto": "SUCCESS"},
        ]
    }), encoding="utf-8")
    fuente = MemoriaSource(data_path=path)
    tecnica = {"id": "directa"}
    assert fuente.siguiente(tecnica) == "un success"   # SUCCESS primero, aunque llegó después
    assert fuente.siguiente(tecnica) == "un continue"
    assert fuente.siguiente(tecnica) is None


def test_registrar_y_luego_leer_round_trip(tmp_path):
    path = tmp_path / "memoria.json"
    ejercicio = Ejercicio(tecnica_id="pii-harvesting", nombre="PII", objetivo="obj",
                           intentos=[_intento(1, "SUCCESS", "payload real que funcionó")])
    registrar_campania(_campania("run1", [ejercicio]), data_path=path)
    fuente = MemoriaSource(data_path=path)
    assert fuente.siguiente({"id": "pii-harvesting"}) == "payload real que funcionó"
    assert fuente.siguiente({"id": "acciones-no-autorizadas"}) is None  # sin nada aprendido aquí
