"""Tests de la exención de tráfico de suite para Rate Limiter / Budget Guard
(#8/#9, LLM10:2025).

Sin esto, `run_attack_suite.py` (108 fixtures, mismo `user_id` por defecto) agota el
Budget Guard tras unas pocas peticiones reales contra `/chat/proxy`, y las fixtures
restantes vuelven `BLOCKED_BY_BUDGET_GUARD` en vez de evaluar el ataque real —
`evaluations/deterministic.py` no distingue esa respuesta de un bloqueo genuino del
Tool Gatekeeper/PII Shield/Output Auditor, así que corrompería en silencio la
evidencia de los ataques #1-7. La exención se activa por `fixture_id` presente en el
`ChatRequest`, no por origen — ver el comentario largo en `_process_chat` (chat.py)
para por qué no basta con origen.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import src.api.routes.chat as chat_route
from src.core.budget_guard import default_guard
from src.core.rate_limiter import default_limiter
from src.main import app


class _FakeResult:
    def __init__(self, output: str):
        self.output = output

    def all_messages(self) -> list:
        return []

    def usage(self):
        raise AttributeError("doble de test sin uso real de tokens")


class _FakeModel:
    model_name = "fake-model"


class _FakeAgent:
    def __init__(self, respuesta: str = "Respuesta normal."):
        self._system_prompts = ["System prompt de prueba"]
        self.model = _FakeModel()
        self.respuesta = respuesta

    async def run(self, message, message_history=None, deps=None, model_settings=None):
        return _FakeResult(self.respuesta)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _agente_falso(monkeypatch):
    agente = _FakeAgent()
    monkeypatch.setattr(chat_route, "get_clara_agent_complex", lambda: agente)
    monkeypatch.setattr(chat_route, "reset_clara_agent_complex", lambda: None)


def _post_proxy(client, tmp_path, *, fixture_id: str | None = None, user_id: str = "usr_001"):
    body = {
        "user_id": user_id, "message": "¿Cuál es mi saldo?",
        "audit_subdir": str(tmp_path / "audit"),
    }
    if fixture_id:
        body["fixture_id"] = fixture_id
    return client.post("/api/v1/chat/proxy", json=body).json()


def test_sin_fixture_id_el_rate_limiter_protege_normalmente(client, tmp_path):
    """Caso base: sin fixture_id, agotar la cuota SÍ bloquea — la exención no debe
    volverse un agujero universal."""
    limiter_original = default_limiter.max_requests
    default_limiter.max_requests = 2
    try:
        _post_proxy(client, tmp_path, user_id="usr_001")
        _post_proxy(client, tmp_path, user_id="usr_001")
        resp = _post_proxy(client, tmp_path, user_id="usr_001")
        assert resp["error"] is not None
        assert "RATE_LIMITER" in resp["error"]
    finally:
        default_limiter.max_requests = limiter_original


def test_con_fixture_id_el_rate_limiter_no_bloquea(client, tmp_path):
    """El caso real que motiva la exención: una suite de fixtures no debe agotar la
    cuota compartida por user_id."""
    limiter_original = default_limiter.max_requests
    default_limiter.max_requests = 2
    try:
        for _ in range(5):  # muy por encima de la cuota de 2
            resp = _post_proxy(client, tmp_path, fixture_id="atk_001", user_id="usr_002")
            assert resp["error"] is None, "una petición de fixture no debería bloquearse nunca"
    finally:
        default_limiter.max_requests = limiter_original


def test_sin_fixture_id_el_budget_guard_protege_normalmente(client, tmp_path):
    default_guard.registrar_consumo("usr_003", default_guard.token_budget)  # agota el presupuesto
    resp = _post_proxy(client, tmp_path, user_id="usr_003")
    assert resp["error"] is not None
    assert "BUDGET_GUARD" in resp["error"]


def test_con_fixture_id_el_budget_guard_no_bloquea(client, tmp_path):
    default_guard.registrar_consumo("usr_admin", default_guard.token_budget)  # agota el presupuesto
    resp = _post_proxy(client, tmp_path, fixture_id="atk_002", user_id="usr_admin")
    assert resp["error"] is None, "una petición de fixture no debería bloquearse nunca"


def test_la_exencion_no_registra_consumo_de_presupuesto(client, tmp_path):
    """Si una petición de fixture SÍ apuntara al presupuesto (aunque no la bloquee a
    ELLA), una sesión interactiva real posterior con el mismo user_id mock heredaría
    ese consumo — el bug se colaría por la puerta de atrás. Ver comentario en chat.py."""
    antes = default_guard.restante("usr_001")
    for _ in range(10):
        _post_proxy(client, tmp_path, fixture_id="atk_003", user_id="usr_001")
    despues = default_guard.restante("usr_001")
    assert despues == antes, "el tráfico de fixtures no debe consumir presupuesto del user_id"
