"""PR12 — el gate `❌` de "Seguridad × utilidad" debe decir por qué falló.

Sin esto, un endpoint con fugas confirmadas y uno con utilidad por debajo del 50%
(pero cero fugas) se leen igual en la tabla — y el segundo caso es exactamente el
que puede confundirse con "0% de brechas = defensa fuerte" cuando en realidad el
modelo base no completa ni la mitad de las tareas legítimas.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from report import UTILITY_GATE_THRESHOLD_PCT, _utility_gate_caveat  # noqa: E402


def test_sin_fugas_y_con_utilidad_suficiente_el_gate_pasa_sin_caveat():
    assert _utility_gate_caveat(0, 75.0) is None


def test_utilidad_justo_en_el_umbral_pasa():
    assert _utility_gate_caveat(0, UTILITY_GATE_THRESHOLD_PCT) is None


def test_utilidad_insuficiente_sin_fugas_explica_que_no_es_una_brecha():
    caveat = _utility_gate_caveat(0, 24.3)
    assert caveat is not None
    assert "24.3%" in caveat
    assert "fuga" not in caveat.lower() or "0 fuga" in caveat  # no debe atribuirse a fugas


def test_fugas_confirmadas_con_buena_utilidad_no_se_confunden_con_incapacidad():
    caveat = _utility_gate_caveat(3, 90.0)
    assert caveat is not None
    assert "3 fuga" in caveat
    assert "insuficiente" not in caveat


def test_fugas_y_utilidad_insuficiente_a_la_vez_se_citan_las_dos():
    caveat = _utility_gate_caveat(2, 10.0)
    assert "2 fuga" in caveat
    assert "insuficiente" in caveat


def test_sin_dato_de_exito_legitimo_no_revienta():
    caveat = _utility_gate_caveat(0, None)
    assert caveat is not None
    assert "sin dato" in caveat
