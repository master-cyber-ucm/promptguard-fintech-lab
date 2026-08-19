"""Tests de A1 del plan LLM10 — Budget Guard (#9, Denial of Wallet).

Unitarios sobre `core/budget_guard.py` directamente.
"""

from __future__ import annotations

from src.core.budget_guard import BudgetGuard


def test_hay_presupuesto_al_empezar():
    bg = BudgetGuard(token_budget=1000, window_seconds=3600)
    hay, consumidos = bg.hay_presupuesto("usr_001")
    assert hay is True
    assert consumidos == 0


def test_registrar_consumo_descuenta_del_presupuesto():
    bg = BudgetGuard(token_budget=1000, window_seconds=3600)
    bg.registrar_consumo("usr_001", 400)
    hay, consumidos = bg.hay_presupuesto("usr_001")
    assert hay is True
    assert consumidos == 400


def test_agotar_presupuesto_deniega():
    bg = BudgetGuard(token_budget=1000, window_seconds=3600)
    bg.registrar_consumo("usr_001", 1000)
    hay, consumidos = bg.hay_presupuesto("usr_001")
    assert hay is False
    assert consumidos == 1000


def test_usuarios_distintos_no_comparten_presupuesto():
    bg = BudgetGuard(token_budget=500, window_seconds=3600)
    bg.registrar_consumo("usr_001", 500)
    hay_001, _ = bg.hay_presupuesto("usr_001")
    hay_002, _ = bg.hay_presupuesto("usr_002")
    assert hay_001 is False
    assert hay_002 is True


def test_ventana_se_reinicia_con_el_tiempo(monkeypatch):
    import time as _time
    ahora = [1000.0]
    monkeypatch.setattr(_time, "time", lambda: ahora[0])

    bg = BudgetGuard(token_budget=500, window_seconds=3600)
    bg.registrar_consumo("usr_001", 500)
    hay, _ = bg.hay_presupuesto("usr_001")
    assert hay is False

    ahora[0] += 3601  # supera la ventana de 1h
    hay, consumidos = bg.hay_presupuesto("usr_001")
    assert hay is True
    assert consumidos == 0


def test_restante_calcula_correctamente():
    bg = BudgetGuard(token_budget=1000, window_seconds=3600)
    bg.registrar_consumo("usr_001", 300)
    assert bg.restante("usr_001") == 700


def test_restante_nunca_es_negativo():
    bg = BudgetGuard(token_budget=100, window_seconds=3600)
    bg.registrar_consumo("usr_001", 500)  # consumo real puede superar el presupuesto
    assert bg.restante("usr_001") == 0


def test_reset_vacia_todas_las_cuentas():
    bg = BudgetGuard(token_budget=100, window_seconds=3600)
    bg.registrar_consumo("usr_001", 100)
    bg.reset()
    hay, consumidos = bg.hay_presupuesto("usr_001")
    assert hay is True
    assert consumidos == 0
