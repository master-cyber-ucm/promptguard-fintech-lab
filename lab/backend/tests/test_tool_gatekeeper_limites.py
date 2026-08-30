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
from src.core import tool_permissions

OWN_ACCOUNT = "ES9121000418450200051332"  # usr_001
OTHER_BANK_ACCOUNT = "ES2922573461048950050000000000007"  # cuenta externa (destinatario)


@dataclass
class _FakeRunContext:
    deps: Deps


def _ctx(user_id: str = "usr_001") -> _FakeRunContext:
    return _FakeRunContext(deps=Deps(user_id=user_id))


@pytest.fixture(autouse=True)
def _yaml_limpio():
    """Cada test recarga el YAML y limpia pendientes — evita estado compartido entre casos."""
    tool_permissions.recargar()
    tool_permissions.limpiar_pendientes()
    yield
    tool_permissions.limpiar_pendientes()


def test_transferencia_bajo_el_umbral_tambien_queda_pendiente():
    result = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 500.0))
    assert result["status"] == "pending_confirmation"


def test_transferencia_sobre_umbral_de_aprobacion_queda_pendiente():
    """El caso exacto que reprodujo el Agente de red-team: importe > 1.000 € (umbral de
    confirmación para "customer") no debe ejecutar directamente."""
    result = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1234.56))
    assert result["status"] == "pending_confirmation"
    assert "operation_id" in result
    assert "confirm_token" in result


def test_transferencia_sobre_max_amount_se_deniega():
    result = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 50000.0))
    assert result["status"] == "denied"
    assert result.get("max_amount") == 5000.0


def test_confirmacion_con_token_valido_ejecuta():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    resultado = tool_permissions.confirmar(
        pendiente["operation_id"], pendiente["confirm_token"], "usr_001",
    )
    assert resultado["status"] == "completed"
    assert resultado["to"] == OTHER_BANK_ACCOUNT


def test_confirmacion_con_token_invalido_se_deniega():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    resultado = tool_permissions.confirmar(pendiente["operation_id"], "token-falso", "usr_001")
    assert resultado["status"] == "denied"


def test_confirmacion_de_un_solo_uso():
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    primera = tool_permissions.confirmar(pendiente["operation_id"], pendiente["confirm_token"], "usr_001")
    segunda = tool_permissions.confirmar(pendiente["operation_id"], pendiente["confirm_token"], "usr_001")
    assert primera["status"] == "completed"
    assert segunda["status"] == "denied"


def test_confirmacion_expirada_se_deniega(monkeypatch):
    pendiente = json.loads(transferencia_nacional(_ctx(), OTHER_BANK_ACCOUNT, 1500.0))
    import time as _time
    ahora_real = _time.time()
    monkeypatch.setattr(_time, "time", lambda: ahora_real + tool_permissions.TTL_SEGUNDOS + 1)
    resultado = tool_permissions.confirmar(pendiente["operation_id"], pendiente["confirm_token"], "usr_001")
    assert resultado["status"] == "denied"
    assert "expirad" in resultado["reason"].lower()


def test_confirmacion_de_otro_usuario_se_deniega():
    """La operación pendiente pertenece a quien la originó — otro user_id no puede confirmarla."""
    pendiente = json.loads(transferencia_nacional(_ctx("usr_001"), OTHER_BANK_ACCOUNT, 1500.0))
    resultado = tool_permissions.confirmar(pendiente["operation_id"], pendiente["confirm_token"], "usr_002")
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
