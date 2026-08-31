"""Tests del Tool Gatekeeper — Fase 2, ataque #7 (defensa complementaria, "las 5 tools completas").

Verifica que cada tool bancaria verifica la propiedad del recurso solicitado contra el
`user_id` autenticado (`RunContext[Deps].deps.user_id`), no contra lo que el LLM decida pedir.
No usa un `RunContext` real de pydantic_ai (requiere muchos campos internos) — las tools solo
leen `ctx.deps.user_id`, así que un doble ligero con esa forma es suficiente y más legible.

usr_001 = María García López, cuenta ES9121000418450200051332, tarjeta CARD-usr001-4521.
usr_003 = Ana Fernández Ruiz, cuenta ES3421000418450200051334 — la "víctima" del ataque #7.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.agents.tools import Deps, abrir_reclamacion, bloquear_tarjeta, consulta_saldo, transferencia_nacional

OWN_ACCOUNT = "ES9121000418450200051332"  # usr_001
OTHER_ACCOUNT = "ES3421000418450200051334"  # usr_003 (Ana Fernández Ruiz — objetivo del ataque #7)
OWN_CARD = "CARD-USR001-4521"
OTHER_CARD = "CARD-USR003-1198"


@dataclass
class _FakeRunContext:
    """Doble ligero de RunContext[Deps] — las tools solo usan `.deps.user_id`."""
    deps: Deps


def _ctx(user_id: str) -> _FakeRunContext:
    return _FakeRunContext(deps=Deps(user_id=user_id))


# --- consulta_saldo ---

def test_consulta_saldo_cuenta_propia_permitida():
    result = json.loads(consulta_saldo(_ctx("usr_001"), OWN_ACCOUNT))
    assert result["status"] == "ok"
    assert result["account_id"] == OWN_ACCOUNT


def test_consulta_saldo_cuenta_ajena_denegada():
    """El caso exacto del ataque #7: usr_001 intentando consultar la cuenta de usr_003."""
    result = json.loads(consulta_saldo(_ctx("usr_001"), OTHER_ACCOUNT))
    assert result["status"] == "denied"


def test_consulta_saldo_sin_account_id_usa_la_cuenta_propia():
    """Mejora Fase 2.7: si el LLM omite account_id (p. ej. "¿cuál es mi saldo?"), se resuelve la
    cuenta propia desde ctx.deps.user_id — el LLM no necesita transcribir su IBAN. Elimina el
    falso positivo detectado en la verificación manual (IBAN mal transcrito -> denegación
    indebida al titular real, 2/7 intentos sobre documentos sanos)."""
    result = json.loads(consulta_saldo(_ctx("usr_001")))
    assert result["status"] == "ok"
    assert result["account_id"] == OWN_ACCOUNT


# --- transferencia_nacional ---

def test_transferencia_desde_cuenta_propia_permitida():
    result = json.loads(
        transferencia_nacional(_ctx("usr_001"), from_account=OWN_ACCOUNT, to_account=OTHER_ACCOUNT, amount=50.0)
    )
    assert result["status"] == "pending_confirmation"


def test_transferencia_desde_cuenta_ajena_denegada():
    """usr_001 no puede iniciar una transferencia con origen en la cuenta de usr_003."""
    result = json.loads(
        transferencia_nacional(_ctx("usr_001"), from_account=OTHER_ACCOUNT, to_account=OWN_ACCOUNT, amount=50.0)
    )
    assert result["status"] == "denied"


def test_transferencia_a_cuenta_ajena_es_valida_ese_es_el_proposito():
    """El destino SÍ puede ser de un tercero — es lo que hace una transferencia."""
    result = json.loads(
        transferencia_nacional(_ctx("usr_001"), from_account=OWN_ACCOUNT, to_account=OTHER_ACCOUNT, amount=50.0)
    )
    assert result["status"] == "pending_confirmation"
    assert result["to_account"] == OTHER_ACCOUNT


def test_transferencia_sin_from_account_usa_la_cuenta_propia():
    """Mejora Fase 2.7: si el LLM omite from_account (p. ej. "transfiere desde mi cuenta"), se
    resuelve la cuenta propia sin que el LLM tenga que transcribir el IBAN — elimina la fuente de
    falsos positivos detectada en la verificación manual (IBAN mal transcrito -> denegación
    indebida al titular real)."""
    result = json.loads(
        transferencia_nacional(_ctx("usr_001"), to_account=OTHER_ACCOUNT, amount=50.0)
    )
    assert result["status"] == "pending_confirmation"
    assert result["resolved"]["from_account"] == OWN_ACCOUNT


# --- bloquear_tarjeta ---

def test_bloquear_tarjeta_propia_permitido():
    result = json.loads(bloquear_tarjeta(_ctx("usr_001"), OWN_CARD))
    assert result["status"] == "completed"
    assert result["card_status"] == "blocked"


def test_bloquear_tarjeta_ajena_denegado():
    result = json.loads(bloquear_tarjeta(_ctx("usr_001"), OTHER_CARD))
    assert result["status"] == "denied"


def test_bloquear_tarjeta_propia_en_minusculas_tambien_permitido():
    """Regresión: un bug inicial (mock con mayúsculas/minúsculas mezcladas en MOCK_CARDS vs.
    normalización a mayúsculas en _owns_card) hacía que incluso la tarjeta propia se denegara."""
    result = json.loads(bloquear_tarjeta(_ctx("usr_001"), OWN_CARD.lower()))
    assert result["status"] == "completed"
    assert result["card_status"] == "blocked"


def test_bloquear_tarjeta_sin_card_id_usa_la_tarjeta_propia():
    """Mejora Fase 2.7: si el LLM omite card_id (p. ej. "bloquea mi tarjeta"), se resuelve la
    tarjeta propia desde ctx.deps.user_id en vez de exigir que el LLM transcriba el identificador."""
    result = json.loads(bloquear_tarjeta(_ctx("usr_001")))
    assert result["status"] == "completed"
    assert result["card_status"] == "blocked"
    assert result["card_id"] == OWN_CARD


# --- abrir_reclamacion ---

def test_abrir_reclamacion_usa_el_user_id_autenticado_no_el_del_llm():
    """Antes del Gatekeeper, `user_id` era un parámetro que el LLM podía rellenar libremente
    (Confused Deputy: registrar una reclamación a nombre de otro cliente). Ahora la función ni
    siquiera acepta ese parámetro — solo puede venir de ctx.deps."""
    result = json.loads(
        abrir_reclamacion(_ctx("usr_003"), "Cargo duplicado", "Descripción de prueba")
    )
    assert result["user_id"] == "usr_003"
