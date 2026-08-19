"""Tests de B7 (plan de excelencia) — rastro de auditoría por Ejercicio/ataque.

Verifica que el fichero existe DURANTE la ejecución (append inmediato, no solo al
cierre — sobrevive un crash a mitad de campaña) y que el contenido final separa los
Intentos con divisores legibles.
"""

from __future__ import annotations

from ejercicio_writer import EjercicioWriter


def test_fichero_existe_tras_abrir_ejercicio(tmp_path, monkeypatch):
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("directa", "20260817_000000_redteam-agent")
    writer.abrir_ejercicio("Prompt Injection Directa", "Objetivo de prueba", "autorreflexivo", "caja-negra")
    assert writer.path.exists()
    assert "Objetivo de prueba" in writer.path.read_text(encoding="utf-8")


def test_append_inmediato_sobrevive_a_mitad_de_intento(tmp_path, monkeypatch):
    """El fichero debe reflejar el turno ANTES de que el Intento se cierre — así un
    crash a mitad de campaña no pierde lo que ya pasó."""
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("directa", "20260817_000000_redteam-agent")
    writer.abrir_ejercicio("Prompt Injection Directa", "Objetivo", "autorreflexivo", "caja-negra")
    writer.abrir_intento(1)
    writer.append_turno(1, "payload de prueba", "respuesta de prueba")

    contenido_a_mitad = writer.path.read_text(encoding="utf-8")
    assert "payload de prueba" in contenido_a_mitad
    assert "respuesta de prueba" in contenido_a_mitad
    assert "Veredicto" not in contenido_a_mitad  # el Intento aún no se ha cerrado


def test_dos_intentos_quedan_separados_por_divisores(tmp_path, monkeypatch):
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("directa", "20260817_000000_redteam-agent")
    writer.abrir_ejercicio("Prompt Injection Directa", "Objetivo", "autorreflexivo", "caja-negra")

    writer.abrir_intento(1)
    writer.append_turno(1, "payload 1", "respuesta 1")
    writer.cerrar_intento("FAILED", "no funcionó")

    writer.abrir_intento(2)
    writer.append_turno(1, "payload 2", "respuesta 2")
    writer.cerrar_intento("SUCCESS", "sí funcionó")

    contenido = writer.path.read_text(encoding="utf-8")
    assert contenido.count("## Intento") == 2
    assert "## Intento 1" in contenido
    assert "## Intento 2" in contenido
    assert contenido.index("## Intento 1") < contenido.index("payload 1") < contenido.index("## Intento 2")
    assert "`FAILED`" in contenido
    assert "`SUCCESS`" in contenido


def test_turno_sin_respuesta_muestra_el_error(tmp_path, monkeypatch):
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("directa", "20260817_000000_redteam-agent")
    writer.abrir_ejercicio("Prompt Injection Directa", "Objetivo", "autorreflexivo", "caja-negra")
    writer.abrir_intento(1)
    writer.append_turno(1, "payload", "", error="timeout de red")
    contenido = writer.path.read_text(encoding="utf-8")
    assert "[BLOQUEADO/ERROR] timeout de red" in contenido


def test_nombre_de_fichero_es_el_run_folder_name(tmp_path, monkeypatch):
    monkeypatch.setattr("ejercicio_writer.EJERCICIOS_DIR", tmp_path)
    writer = EjercicioWriter("cross-context-leakage", "20260817_113000_redteam-agent")
    assert writer.path.parent.name == "cross-context-leakage"
    assert writer.path.name == "20260817_113000_redteam-agent.md"
