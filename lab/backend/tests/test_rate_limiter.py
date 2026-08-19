"""Tests de A1 del plan LLM10 — Rate Limiter (#8, Denegación de Servicio).

Unitarios sobre `core/rate_limiter.py` directamente — sin pasar por HTTP, mismo
patrón que `test_tool_gatekeeper.py` (doble ligero en vez de servidor real).
"""

from __future__ import annotations

from src.core.rate_limiter import RateLimiter


def test_dentro_de_la_cuota_permite():
    rl = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        permitido, _ = rl.permitir("usr_001")
        assert permitido is True


def test_supera_la_cuota_deniega():
    rl = RateLimiter(max_requests=5, window_seconds=60)
    for _ in range(5):
        rl.permitir("usr_001")
    permitido, retry_after = rl.permitir("usr_001")
    assert permitido is False
    assert retry_after > 0


def test_usuarios_distintos_no_comparten_cuota():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    rl.permitir("usr_001")
    rl.permitir("usr_001")
    permitido_001, _ = rl.permitir("usr_001")
    permitido_002, _ = rl.permitir("usr_002")
    assert permitido_001 is False
    assert permitido_002 is True


def test_ventana_deslizante_libera_cuota_con_el_tiempo(monkeypatch):
    import time as _time
    ahora = [1000.0]
    monkeypatch.setattr(_time, "time", lambda: ahora[0])

    rl = RateLimiter(max_requests=2, window_seconds=10)
    rl.permitir("usr_001")
    rl.permitir("usr_001")
    permitido, _ = rl.permitir("usr_001")
    assert permitido is False

    ahora[0] += 11  # supera la ventana de 10s
    permitido, _ = rl.permitir("usr_001")
    assert permitido is True


def test_reset_vacia_todos_los_buckets():
    rl = RateLimiter(max_requests=1, window_seconds=60)
    rl.permitir("usr_001")
    permitido, _ = rl.permitir("usr_001")
    assert permitido is False
    rl.reset()
    permitido, _ = rl.permitir("usr_001")
    assert permitido is True
