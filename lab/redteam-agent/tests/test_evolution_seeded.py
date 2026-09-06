"""Tests de SeededEngine — envoltorio que conecta una Fuente de semillas (sources/)
con cualquier motor de evolución existente sin modificarlos. Ver plan-fusion-redteam.md."""

from __future__ import annotations

from evolution import SeededEngine, get_engine


class _MotorFalso:
    name = "falso"

    def __init__(self):
        self.llamado = False

    def abrir_intento(self, *, tecnica, historial, brain):
        self.llamado = True
        return "payload generado por el motor"


class _FuenteFalsa:
    name = "fuente-falsa"

    def __init__(self, semillas):
        self._semillas = list(semillas)

    def siguiente(self, tecnica):
        if not self._semillas:
            return None
        return self._semillas.pop(0)


def test_usa_semilla_en_primer_intento_si_hay_disponible():
    inner = _MotorFalso()
    engine = SeededEngine(inner, _FuenteFalsa(["semilla externa"]))
    payload = engine.abrir_intento(tecnica={"id": "directa"}, historial=[], brain=None)
    assert payload == "semilla externa"
    assert inner.llamado is False
    assert engine.ultima_fuente == "fuente-falsa"


def test_delega_en_el_motor_si_la_fuente_no_tiene_semilla():
    inner = _MotorFalso()
    engine = SeededEngine(inner, _FuenteFalsa([]))
    payload = engine.abrir_intento(tecnica={"id": "directa"}, historial=[], brain=None)
    assert payload == "payload generado por el motor"
    assert inner.llamado is True
    assert engine.ultima_fuente == "propio"


def test_no_usa_semilla_si_ya_hay_historial_en_el_ejercicio():
    """Las semillas externas solo abren el Ejercicio — la escalada dentro de él sigue
    siendo responsabilidad exclusiva del motor de evolución configurado, igual que hoy."""
    inner = _MotorFalso()
    engine = SeededEngine(inner, _FuenteFalsa(["semilla que no debería usarse"]))
    historial_previo = [object()]  # basta con que no esté vacío
    payload = engine.abrir_intento(tecnica={"id": "directa"}, historial=historial_previo, brain=None)
    assert payload == "payload generado por el motor"
    assert engine.ultima_fuente == "propio"


def test_get_engine_sin_seed_source_no_envuelve():
    engine = get_engine("autorreflexivo")
    assert engine.name == "autorreflexivo"


def test_get_engine_con_seed_source_envuelve_y_compone_nombre():
    engine = get_engine("autorreflexivo", seed_source=_FuenteFalsa(["x"]))
    assert isinstance(engine, SeededEngine)
    assert engine.name == "autorreflexivo+fuente-falsa"
