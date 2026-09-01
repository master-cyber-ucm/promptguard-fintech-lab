"""P18 — el segundo factor no puede viajar por el primer canal.

La tool devolvía `confirm_token` y `operation_id` en su resultado, y el endpoint de
confirmación aceptaba token y `user_id` del cuerpo. Un prompt comprometido podía pedir
al modelo que mostrara el token y después confirmarlo: todas las piezas de la
"aprobación humana independiente" estaban dentro del canal atacado.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from src.agents.tools import Deps, transferencia_nacional
from src.api.auth import Principal, issue_token
from src.core import transaction_authorization
from src.core.transaction_authorization import authorize, canonical_digest, inbox, propose
from src.main import app

MARIA = Principal(subject="usr_001")
CARLOS = Principal(subject="usr_002")
CUENTA_DESTINO = "ES3421000418450200051334"


@dataclass
class _Ctx:
    deps: Deps


def _ctx(user_id="usr_001"):
    return _Ctx(deps=Deps(user_id=user_id, principal=Principal(subject=user_id)))


@pytest.fixture(autouse=True)
def _limpio():
    transaction_authorization.reset_for_tests()
    yield
    transaction_authorization.reset_for_tests()


def _proponer(amount=1500.0, user_id="usr_001"):
    resultado = json.loads(transferencia_nacional(_ctx(user_id), CUENTA_DESTINO, amount))
    return resultado, resultado["operation_reference"]


def _desafio(operation_id, principal=MARIA):
    return next(m["challenge"] for m in inbox(principal) if m["operation_id"] == operation_id)


# ── El canal del LLM no ve el desafío ────────────────────────────────────────

def test_el_resultado_de_la_tool_no_lleva_el_desafio():
    resultado, operation_id = _proponer()
    serializado = json.dumps(resultado)
    assert "challenge" not in serializado
    assert "confirm_token" not in serializado
    assert _desafio(operation_id) not in serializado


def test_el_resultado_de_la_tool_solo_lleva_una_referencia_opaca():
    resultado, operation_id = _proponer()
    assert resultado["operation_reference"] == operation_id
    assert resultado["requires"] == "out_of_band_approval"
    assert "app" in resultado["message"].lower()


def test_el_resumen_visible_no_contiene_material_de_autorizacion():
    resultado, _ = _proponer()
    resumen = resultado["summary"]
    assert resumen["cuenta_destino"] == CUENTA_DESTINO
    assert "challenge" not in resumen and "digest" not in resumen


def test_el_desafio_llega_a_la_bandeja_fuera_de_banda():
    _, operation_id = _proponer()
    bandeja = inbox(MARIA)
    assert len(bandeja) == 1
    assert bandeja[0]["operation_id"] == operation_id
    assert bandeja[0]["challenge"]
    # La app muestra el detalle real: es lo que la persona confirma.
    assert bandeja[0]["displayed_fields"]["importe"] == "1,500.00 €"


def test_la_bandeja_de_otro_sujeto_esta_vacia():
    _proponer()
    assert inbox(CARLOS) == []


# ── Solo el Principal correcto aprueba ───────────────────────────────────────

def test_otro_sujeto_no_puede_aprobar_aunque_conozca_el_desafio():
    _, operation_id = _proponer()
    resultado = authorize(operation_id, principal=CARLOS,
                          challenge_response=_desafio(operation_id))
    assert resultado["status"] == "denied"
    assert "principal" in resultado["reason"]


def test_otro_tenant_no_puede_aprobar():
    _, operation_id = _proponer()
    otro_tenant = Principal(subject="usr_001", tenant_id="otro-banco")
    resultado = authorize(operation_id, principal=otro_tenant,
                          challenge_response=_desafio(operation_id))
    assert resultado["status"] == "denied"


def test_un_desafio_invalido_no_aprueba():
    _, operation_id = _proponer()
    resultado = authorize(operation_id, principal=MARIA, challenge_response="inventado")
    assert resultado["status"] == "denied"


def test_la_aprobacion_correcta_consuma_la_operacion():
    _, operation_id = _proponer()
    resultado = authorize(operation_id, principal=MARIA,
                          challenge_response=_desafio(operation_id))
    assert resultado["status"] == "completed"
    assert resultado["authorization"]["approver_subject"] == "usr_001"
    assert resultado["authorization"]["proposal_digest"]


# ── Como máximo un commit ────────────────────────────────────────────────────

def test_un_replay_no_produce_un_segundo_commit():
    _, operation_id = _proponer()
    desafio = _desafio(operation_id)
    primera = authorize(operation_id, principal=MARIA, challenge_response=desafio)
    segunda = authorize(operation_id, principal=MARIA, challenge_response=desafio)
    assert primera["status"] == "completed"
    assert segunda["status"] == "denied"


def test_dos_aprobadores_concurrentes_producen_como_maximo_un_commit():
    import threading  # noqa: PLC0415

    _, operation_id = _proponer()
    desafio = _desafio(operation_id)
    resultados = []

    def _aprobar():
        resultados.append(
            authorize(operation_id, principal=MARIA, challenge_response=desafio)
        )

    hilos = [threading.Thread(target=_aprobar) for _ in range(8)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    commits = [r for r in resultados if r.get("status") == "completed"]
    assert len(commits) == 1


def test_una_operacion_expirada_no_se_aprueba(monkeypatch):
    _, operation_id = _proponer()
    desafio = _desafio(operation_id)
    ahora = time.time()
    monkeypatch.setattr(time, "time",
                        lambda: ahora + transaction_authorization.TTL_SECONDS + 1)
    resultado = authorize(operation_id, principal=MARIA, challenge_response=desafio)
    assert resultado["status"] == "denied"
    assert "expirad" in resultado["reason"]


# ── El digest ata los detalles exactos ───────────────────────────────────────

def test_alterar_un_campo_tras_proponer_invalida_la_aprobacion():
    operacion = propose(
        tool="transferencia_nacional", principal=MARIA,
        details={"to_account": CUENTA_DESTINO, "amount": 100.0},
        displayed_fields={"importe": "100,00 €"},
        execute=lambda: {"status": "completed"},
    )
    # Alguien cambia el importe después de que la propuesta se registrara.
    operacion.details["amount"] = 9999.0
    resultado = authorize(operacion.operation_id, principal=MARIA,
                          challenge_response=operacion.challenge)
    assert resultado["status"] == "denied"
    assert "no coinciden" in resultado["reason"]


def test_el_digest_cubre_todos_los_campos_no_solo_el_id():
    base = {"to_account": CUENTA_DESTINO, "amount": 100.0, "concept": "x"}
    assert canonical_digest(base) != canonical_digest({**base, "amount": 101.0})
    assert canonical_digest(base) != canonical_digest({**base, "to_account": "ES99"})
    assert canonical_digest(base) == canonical_digest(dict(reversed(list(base.items()))))


def test_rechazar_no_ejecuta_nada():
    _, operation_id = _proponer()
    resultado = authorize(operation_id, principal=MARIA,
                          challenge_response=_desafio(operation_id), decision="reject")
    assert resultado["status"] == "rejected"
    # Y ya no puede aprobarse después.
    assert authorize(operation_id, principal=MARIA,
                     challenge_response="lo que sea")["status"] == "denied"


# ── El endpoint no acepta sustitutos ─────────────────────────────────────────

def test_el_endpoint_deriva_la_identidad_del_principal():
    client = TestClient(app)
    _, operation_id = _proponer()
    respuesta = client.post(
        f"/api/v1/confirm/{operation_id}",
        json={"challenge_response": _desafio(operation_id)},
        headers={"Authorization": f"Bearer {issue_token('usr_001')}"},
    )
    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "completed"


def test_el_endpoint_rechaza_a_otro_principal():
    client = TestClient(app)
    _, operation_id = _proponer()
    respuesta = client.post(
        f"/api/v1/confirm/{operation_id}",
        json={"challenge_response": _desafio(operation_id)},
        headers={"Authorization": f"Bearer {issue_token('usr_002')}"},
    )
    assert respuesta.json()["status"] == "denied"


def test_el_endpoint_no_acepta_importes_ni_beneficiarios_sustitutos():
    """Los detalles se recargan del store: lo que llega en el cuerpo no los cambia."""
    client = TestClient(app)
    _, operation_id = _proponer(amount=1500.0)
    respuesta = client.post(
        f"/api/v1/confirm/{operation_id}",
        json={"challenge_response": _desafio(operation_id),
              "amount": 999999, "to_account": "ES00CUENTA-DEL-ATACANTE"},
        headers={"Authorization": f"Bearer {issue_token('usr_001')}"},
    ).json()
    assert respuesta["status"] == "completed"
    assert respuesta["to"] == CUENTA_DESTINO
    assert respuesta["amount"] == "1,500.00 €"


def test_la_bandeja_del_endpoint_solo_muestra_lo_propio():
    client = TestClient(app)
    _proponer()
    ajena = client.get(
        "/api/v1/authorizations",
        headers={"Authorization": f"Bearer {issue_token('usr_002')}"},
    ).json()
    assert ajena["operations"] == []


def test_el_detalle_de_una_operacion_ajena_no_se_revela():
    client = TestClient(app)
    _, operation_id = _proponer()
    respuesta = client.get(
        f"/api/v1/authorizations/{operation_id}",
        headers={"Authorization": f"Bearer {issue_token('usr_002')}"},
    )
    assert respuesta.status_code == 404
    assert operation_id not in respuesta.text
