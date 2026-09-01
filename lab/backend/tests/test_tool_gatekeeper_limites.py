"""Tests de A1 (plan de excelencia) — conecta `tool_permissions.yaml` al Tool Gatekeeper:
límites por importe y confirmación fuera de banda para `transferencia_nacional`.

Antes de este fix, `tool_permissions.yaml` tenía 0 referencias en `src/` — el Gatekeeper
solo verificaba propiedad de cuenta. El Agente de red-team reprodujo en vivo el vector
que estos límites debían cerrar (transferencia real sin confirmación, framing de
urgencia) — ver `HALLAZGOS-SESION-20260816.md` y
`docs/reports/plan-excelencia-redteam-y-defensas.md` §A1.

usr_001 = María García López, cuenta ES9121000418450200051332, rol "customer".
Límites de `tool_permissions.yaml` para "customer": max_amount=5000.00,
requires_approval_above=1000.00.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from src.agents.tools import Deps, transferencia_nacional
from src.api.auth import Principal
from src.core import tool_permissions, transaction_authorization

OWN_ACCOUNT = "ES9121000418450200051332"  # usr_001
OTHER_BANK_ACCOUNT = "ES2922573461048950050000000000007"  # cuenta externa (destinatario)


@dataclass
class _FakeRunContext:
    deps: Deps


def _ctx(user_id: str = "usr_001") -> _FakeRunContext:
    return _FakeRunContext(deps=Deps(user_id=user_id, principal=Principal(subject=user_id)))


def _desafio(operation_id: str, user_id: str = "usr_001") -> str:
    """Recoge el desafío del canal FUERA de banda — la app, no el chat.

    Es exactamente lo que un atacante que controla el prompt no puede hacer: el
    resultado de la tool ya no lleva el token (P18).
    """
    bandeja = transaction_authorization.inbox(Principal(subject=user_id))
    return next(m["challenge"] for m in bandeja if m["operation_id"] == operation_id)


@pytest.fixture(autouse=True)
def _yaml_limpio():
    """Cada test recarga el YAML y limpia pendientes — evita estado compartido entre casos."""
    tool_permissions.recargar()
    tool_permissions.limpiar_pendientes()
    transaction_authorization.reset_for_tests()
    yield
    tool_permissions.limpiar_pendientes()
    transaction_authorization.reset_for_tests()


def test_transferencia_bajo_el_umbral_no_se_compromete_sin_autorizacion():
    """El YAML dice `requires_approval_above: 1000.00` para "customer": por debajo del
    umbral la policy no deniega. Pero "no denegada" dejó de significar "comprometida
    directamente" (PR 2 / ADR-0013): toda escritura financiera exige autorización de
    transacción fuera del canal LLM, y solo esa autorización produce el commit.
    """
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 500.0))
    assert pendiente["invocation_state"] == "AWAITING_CONFIRMATION"
    operation_id = pendiente["operation_reference"]
    resultado = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_001"),
        challenge_response=_desafio(operation_id),
    )
    assert resultado["status"] == "completed"
    assert resultado["to"] == OTHER_BANK_ACCOUNT


def test_transferencia_sobre_umbral_de_aprobacion_queda_pendiente():
    """El caso exacto que reprodujo el Agente de red-team: importe > 1.000 € (umbral de
    confirmación para "customer") no debe ejecutar directamente."""
    result = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1234.56))
    assert result["status"] == "pending_confirmation"
    assert result["operation_reference"]
    # El material de autorización NO vuelve por el canal del LLM (P18).
    assert "confirm_token" not in result
    assert "challenge" not in json.dumps(result)


def test_transferencia_sobre_max_amount_se_deniega():
    result = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 50000.0))
    assert result["status"] == "denied"
    # La decisión cita la regla exacta del YAML que la produjo.
    assert result["policy_rule"] == "transferencia_nacional.limits.customer.max_amount"
    assert result["threshold"] == 5000.0


def test_confirmacion_con_desafio_valido_ejecuta():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    operation_id = pendiente["operation_reference"]
    resultado = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_001"),
        challenge_response=_desafio(operation_id),
    )
    assert resultado["status"] == "completed"
    assert resultado["to"] == OTHER_BANK_ACCOUNT
    assert resultado["authorization"]["approver_subject"] == "usr_001"


def test_confirmacion_con_desafio_invalido_se_deniega():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    resultado = transaction_authorization.authorize(
        pendiente["operation_reference"], principal=Principal(subject="usr_001"),
        challenge_response="desafio-falso",
    )
    assert resultado["status"] == "denied"


def test_confirmacion_de_un_solo_uso():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    operation_id = pendiente["operation_reference"]
    desafio = _desafio(operation_id)
    primera = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_001"), challenge_response=desafio)
    segunda = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_001"), challenge_response=desafio)
    assert primera["status"] == "completed"
    assert segunda["status"] == "denied"


def test_confirmacion_expirada_se_deniega(monkeypatch):
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    operation_id = pendiente["operation_reference"]
    desafio = _desafio(operation_id)
    import time as _time
    ahora_real = _time.time()
    monkeypatch.setattr(_time, "time",
                        lambda: ahora_real + transaction_authorization.TTL_SECONDS + 1)
    resultado = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_001"), challenge_response=desafio)
    assert resultado["status"] == "denied"
    assert "expirad" in resultado["reason"].lower()


def test_confirmacion_de_otro_usuario_se_deniega():
    """La operación pertenece a quien la originó — otro sujeto no puede aprobarla
    aunque conozca el desafío."""
    pendiente = json.loads(transferencia_nacional(_ctx("usr_001"), OTHER_BANK_ACCOUNT, 1500.0))
    operation_id = pendiente["operation_reference"]
    resultado = transaction_authorization.authorize(
        operation_id, principal=Principal(subject="usr_002"),
        challenge_response=_desafio(operation_id),
    )
    assert resultado["status"] == "denied"


def test_propiedad_de_cuenta_se_sigue_verificando_antes_que_los_limites():
    """El Gatekeeper original (propiedad de cuenta) no debe quedar eclipsado por el nuevo
    control de límites — ambos aplican, propiedad primero."""
    from src.models.banking import MOCK_ACCOUNTS
    otra_cuenta_ajena = next(iban for iban in MOCK_ACCOUNTS if iban != OWN_ACCOUNT)
    result = json.loads(
        transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 500.0, from_account=otra_cuenta_ajena)
    )
    assert result["status"] == "denied"
    assert "titular" in result["reason"].lower()
