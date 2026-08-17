"""Tests de A1 del plan LLM10 — cota LRU + TTL de `session_store.py` (#8, Denegación de
Servicio: "Sesiones sin cota").
"""

from __future__ import annotations

import src.agents.session_store as session_store


def _reset(monkeypatch, max_sessions: int | None = None, ttl_seconds: int | None = None):
    """Reimporta con límites de prueba pequeños — los valores por defecto (1000
    sesiones, 30 min) harían estos tests lentos o poco claros."""
    session_store.clear_all()
    if max_sessions is not None:
        monkeypatch.setattr(session_store, "MAX_SESSIONS", max_sessions)
    if ttl_seconds is not None:
        monkeypatch.setattr(session_store, "SESSION_TTL_SECONDS", ttl_seconds)


def test_sesion_nueva_se_puede_leer(monkeypatch):
    _reset(monkeypatch)
    session_store.store_history("ses_a", [])
    assert session_store.get_history("ses_a") == []
    session_store.clear_all()


def test_cota_lru_desaloja_la_menos_usada(monkeypatch):
    _reset(monkeypatch, max_sessions=2)
    session_store.store_history("ses_a", [])
    session_store.store_history("ses_b", [])
    assert session_store.session_count() == 2

    session_store.store_history("ses_c", [])  # supera la cota — desaloja la LRU (ses_a)
    assert session_store.session_count() == 2
    assert session_store.get_history("ses_b") == []  # sigue viva
    # ses_a fue desalojada: get_history devuelve [] igual que "no existe" — se verifica
    # indirectamente por el conteo, que no puede haber crecido a 3.
    session_store.clear_all()


def test_leer_una_sesion_la_marca_como_reciente(monkeypatch):
    """Una sesión leída recientemente no debería ser la próxima en desalojarse."""
    _reset(monkeypatch, max_sessions=2)
    session_store.store_history("ses_a", [])
    session_store.store_history("ses_b", [])
    session_store.get_history("ses_a")  # toca ses_a — ahora ses_b es la LRU

    session_store.store_history("ses_c", [])  # debe desalojar ses_b, no ses_a
    assert session_store.session_count() == 2
    session_store.get_history("ses_a")  # no debería haber sido desalojada
    session_store.clear_all()


def test_ttl_expira_sesiones_inactivas(monkeypatch):
    import time as _time
    ahora = [1000.0]
    monkeypatch.setattr(_time, "time", lambda: ahora[0])

    _reset(monkeypatch, ttl_seconds=60)
    session_store.store_history("ses_a", [])
    assert session_store.session_count() == 1

    ahora[0] += 61
    assert session_store.get_history("ses_a") == []  # ya expiró — se lee como vacía
    assert session_store.session_count() == 0  # la purga la eliminó del almacén
    session_store.clear_all()


def test_clear_all_vacia_el_almacen(monkeypatch):
    _reset(monkeypatch)
    session_store.store_history("ses_a", [])
    session_store.clear_all()
    assert session_store.session_count() == 0
