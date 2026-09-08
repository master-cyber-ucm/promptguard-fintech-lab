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


def test_sigue_usando_semillas_aunque_ya_haya_historial():
    """Fix del 2026-09-08: con --max-attempts 20, restringir las semillas al primer
    Intento dejaba la fuente externa en ~1,7% de los payloads reales de una Campaña
    (2/120, campaña del 2026-09-07) — se agotan las semillas antes de pasar a
    generación propia, con independencia del historial del Ejercicio."""
    inner = _MotorFalso()
    engine = SeededEngine(inner, _FuenteFalsa(["semilla 1", "semilla 2"]))
    historial_previo = [object()]  # ya hay un intento fallido en el Ejercicio
    payload = engine.abrir_intento(tecnica={"id": "directa"}, historial=historial_previo, brain=None)
    assert payload == "semilla 1"
    assert inner.llamado is False
    assert engine.ultima_fuente == "fuente-falsa"


def test_agota_semillas_antes_de_pasar_a_generacion_propia():
    inner = _MotorFalso()
    engine = SeededEngine(inner, _FuenteFalsa(["semilla 1", "semilla 2"]))
    p1 = engine.abrir_intento(tecnica={"id": "directa"}, historial=[], brain=None)
    p2 = engine.abrir_intento(tecnica={"id": "directa"}, historial=[object()], brain=None)
    p3 = engine.abrir_intento(tecnica={"id": "directa"}, historial=[object(), object()], brain=None)
    assert [p1, p2, p3] == ["semilla 1", "semilla 2", "payload generado por el motor"]
    assert inner.llamado is True
    assert engine.ultima_fuente == "propio"


def test_get_engine_sin_seed_source_no_envuelve():
    engine = get_engine("autorreflexivo")
    assert engine.name == "autorreflexivo"


def test_get_engine_con_seed_source_envuelve_y_compone_nombre():
    engine = get_engine("autorreflexivo", seed_source=_FuenteFalsa(["x"]))
    assert isinstance(engine, SeededEngine)
    assert engine.name == "autorreflexivo+fuente-falsa"
