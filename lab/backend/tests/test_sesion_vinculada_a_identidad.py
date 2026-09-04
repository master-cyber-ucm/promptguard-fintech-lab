"""P17 — un `session_id` filtrado no da acceso a la conversación de otro.

El store indexaba por `session_id` y `chat.py` cargaba el historial en cuanto el
cliente aportaba ese ID. Una defensa de salida que actúa al final no cierra ese vector:
el historial ajeno ya influyó en el prompt y en las tool calls.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient
from pydantic_ai.messages import ModelRequest, UserPromptPart

import src.agents.session_store as session_store
import src.api.routes.chat as chat_route
from src.api.auth import Principal, issue_token
from src.main import app

MARIA = Principal(subject="usr_001")
CARLOS = Principal(subject="usr_002")
OTRO_BANCO = Principal(subject="usr_001", tenant_id="otro-banco")


def _mensaje(texto: str):
    return ModelRequest(parts=[UserPromptPart(content=texto)])


@pytest.fixture(autouse=True)
def _almacen_limpio():
    session_store.clear_all()
    yield
    session_store.clear_all()


# ── Aislamiento entre identidades ────────────────────────────────────────────

def test_dos_usuarios_con_el_mismo_handle_no_comparten_historial():
    session_store.store_history(MARIA, "S1", [_mensaje("mi saldo secreto")])
    session_store.store_history(CARLOS, "S1", [_mensaje("otra cosa")])

    assert len(session_store.get_history(MARIA, "S1")) == 1
    historial_carlos = session_store.get_history(CARLOS, "S1")
    assert len(historial_carlos) == 1
    assert historial_carlos != session_store.get_history(MARIA, "S1")


def test_un_session_id_robado_no_devuelve_ni_un_mensaje():
    """El caso: `S1` aparece en un log y otro cliente lo envía con su propia identidad."""
    session_store.store_history(MARIA, "S1", [_mensaje("historial de María")])
    assert session_store.get_history(CARLOS, "S1") == []
    assert session_store.get_owned(CARLOS, "S1") is None


def test_un_intento_cruzado_deja_señal():
    session_store.store_history(MARIA, "S1", [_mensaje("x")])
    session_store.get_history(CARLOS, "S1")
    intentos = session_store.cross_access_attempts()
    assert intentos and intentos[0]["session_id"] == "S1"
    assert intentos[0]["requested_by"] == "usr_002"


def test_el_tenant_tambien_aisla():
    session_store.store_history(MARIA, "S1", [_mensaje("x")])
    assert session_store.get_history(OTRO_BANCO, "S1") == []


# ── Reclamar una sesión ──────────────────────────────────────────────────────

def test_un_identificador_libre_se_adopta_bajo_el_principal():
    """El Playground y el runner eligen su propio ID; eso no es una violación."""
    session_id, historial = session_store.claim_session(MARIA, "mi-sesion")
    assert session_id == "mi-sesion"
    assert historial == []


def test_una_sesion_propia_se_continua():
    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    session_id, historial = session_store.claim_session(MARIA, "S1")
    assert session_id == "S1"
    assert len(historial) == 1


def test_una_sesion_ajena_no_se_reutiliza_ni_confirma_su_existencia():
    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    session_id, historial = session_store.claim_session(CARLOS, "S1")
    assert session_id != "S1"
    assert historial == []


def test_sin_session_id_se_abre_una_nueva():
    session_id, historial = session_store.claim_session(MARIA, None)
    assert session_id.startswith("ses_")
    assert historial == []


# ── Ciclo de vida ────────────────────────────────────────────────────────────

def test_revocar_borra_historial_y_estado_de_riesgo_a_la_vez():
    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    session_store.update_security_state(MARIA, "S1", riesgo="alto")
    assert session_store.revoke(MARIA, "S1") is True
    assert session_store.get_owned(MARIA, "S1") is None
    assert session_store.get_history(MARIA, "S1") == []


def test_no_se_puede_revocar_la_sesion_de_otro():
    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    assert session_store.revoke(CARLOS, "S1") is False
    assert session_store.get_owned(MARIA, "S1") is not None


def test_expirar_limpia_historial_y_riesgo(monkeypatch):
    ahora = [1000.0]
    monkeypatch.setattr(time, "time", lambda: ahora[0])
    monkeypatch.setattr(session_store, "SESSION_TTL_SECONDS", 60)

    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    session_store.update_security_state(MARIA, "S1", riesgo="alto")
    ahora[0] += 61
    assert session_store.get_history(MARIA, "S1") == []
    assert session_store.session_count() == 0


def test_el_estado_de_riesgo_vive_en_el_mismo_boundary_que_el_historial():
    session_store.store_history(MARIA, "S1", [_mensaje("hola")])
    record = session_store.update_security_state(MARIA, "S1", riesgo="alto")
    assert record.security_state == {"riesgo": "alto"}
    # Otro sujeto no puede mutarlo aunque conozca el identificador.
    assert session_store.update_security_state(CARLOS, "S1", riesgo="bajo") is None
    assert session_store.get_owned(MARIA, "S1").security_state == {"riesgo": "alto"}


# ── Concurrencia ─────────────────────────────────────────────────────────────

def test_cada_escritura_incrementa_la_version():
    # El record es mutable y compartido: lo que se compara es el valor, no el objeto.
    primera = session_store.store_history(MARIA, "S1", [_mensaje("uno")]).version
    segunda = session_store.store_history(MARIA, "S1", [_mensaje("dos")]).version
    assert segunda > primera
    assert session_store.get_owned(MARIA, "S1").owner_subject == "usr_001"


def test_una_escritura_no_puede_cambiar_el_dueño():
    session_store.store_history(MARIA, "S1", [_mensaje("uno")])
    session_store.store_history(CARLOS, "S1", [_mensaje("dos")])
    assert session_store.get_owned(MARIA, "S1").owner_subject == "usr_001"
    assert session_store.get_owned(CARLOS, "S1").owner_subject == "usr_002"


def test_los_identificadores_tienen_entropia_suficiente():
    ids = {session_store.new_session_id() for _ in range(200)}
    assert len(ids) == 200
    # 24 hex ≈ 96 bits: adivinarlo deja de ser una vía.
    assert len(ids.pop().split("_")[1]) == 24


# ── Extremo a extremo por el endpoint ────────────────────────────────────────

class _FakeResult:
    def __init__(self, output, mensajes):
        self.output = output
        self._mensajes = mensajes

    def all_messages(self):
        return self._mensajes


class _FakeModel:
    model_name = "fake-model"


class _FakeAgent:
    def __init__(self):
        self._system_prompts = ["sp"]
        self.model = _FakeModel()
        self.historial_recibido = None

    async def run(self, message, message_history=None, deps=None, model_settings=None):
        self.historial_recibido = message_history
        return _FakeResult("ok", [_mensaje(str(message))])


@pytest.fixture
def agente(monkeypatch):
    doble = _FakeAgent()
    monkeypatch.setattr(chat_route, "get_clara_agent_complex", lambda: doble)
    monkeypatch.setattr(chat_route, "reset_clara_agent_complex", lambda: None)
    return doble


def test_el_endpoint_no_carga_la_conversacion_de_otro(agente, tmp_path):
    client = TestClient(app)
    cuerpo = {"message": "primer turno", "session_id": "S-compartida",
              "audit_subdir": str(tmp_path / "audit")}

    primera = client.post(
        "/api/v1/chat/complex-with-context", json=cuerpo,
        headers={"Authorization": f"Bearer {issue_token('usr_001')}"},
    ).json()
    assert primera["session_id"] == "S-compartida"

    # Carlos envía el MISMO session_id con su propia credencial.
    segunda = client.post(
        "/api/v1/chat/complex-with-context",
        json={**cuerpo, "message": "¿de qué hablábamos?"},
        headers={"Authorization": f"Bearer {issue_token('usr_002')}"},
    ).json()

    assert segunda["session_id"] != "S-compartida"
    assert agente.historial_recibido is None, "no se cargó ni un mensaje ajeno"


def test_el_endpoint_si_continua_la_conversacion_propia(agente, tmp_path):
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {issue_token('usr_001')}"}
    cuerpo = {"session_id": "S-propia", "audit_subdir": str(tmp_path / "audit")}

    client.post("/api/v1/chat/complex-with-context",
                json={**cuerpo, "message": "primer turno"}, headers=headers)
    client.post("/api/v1/chat/complex-with-context",
                json={**cuerpo, "message": "segundo turno"}, headers=headers)

    assert agente.historial_recibido, "la conversación propia sí continúa"
