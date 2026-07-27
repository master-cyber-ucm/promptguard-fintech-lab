"""Tools bancarias MOCK para Clara.

Tool Gatekeeper (Fase 2, ataque #7 — defensa complementaria de "las 5 tools bancarias
completas", a petición explícita del usuario): cada tool que opera sobre un recurso
identificable (cuenta, tarjeta) verifica que ese recurso pertenezca al `user_id` AUTENTICADO
—recibido vía `RunContext[Deps].deps.user_id`, un canal que el LLM no controla— antes de
ejecutar la acción. Esto es ortogonal a las 3 capas de defensa del canal documental
(`document_sanitizer`, `document_structural_detector`, separación semántica): aquellas intentan
evitar que el LLM sea engañado; esta verifica la autorización aunque el LLM SÍ haya sido
engañado y decida invocar la tool igualmente. Ver henri-tfm/02-defensa/README.md.

Antes de esta defensa, el estado era: todas las tools aceptaban cualquier parámetro sin
verificar permisos, propiedad de cuenta, ni límites — habilitando Excessive Agency (#1),
Confused Deputy (#4) y Cross-Context Leakage (#3) del catálogo de ataques.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic_ai import RunContext

from ..models.banking import (
    MOCK_ACCOUNTS,
    MOCK_CARDS,
    MOCK_USERS,
    AccountInfo,
    Transaction,
)


@dataclass
class Deps:
    """Dependencias inyectadas por sesión — el `user_id` viene del backend (autenticación de la
    petición HTTP), NUNCA de un parámetro que el LLM pueda rellenar. Es la pieza que hace que el
    Tool Gatekeeper sea determinista y no dependa del comportamiento del modelo.

    `enforce_gatekeeper`: interruptor experimental (Fase 2, estudio de ablación) para poder medir
    el efecto AISLADO del Tool Gatekeeper — `False` reproduce el comportamiento vulnerable
    original de las tools, sin verificación de propiedad. Por defecto `True` (seguro por
    defecto); solo se desactiva explícitamente desde el endpoint cuando se pide comparar
    defensas. No expuesto al LLM — el propio `Deps` no es un parámetro de tool.
    """
    user_id: str
    enforce_gatekeeper: bool = True


def _get_account(account_id: str) -> Optional[AccountInfo]:
    """Busca una cuenta por IBAN. No verifica permisos — la verificación vive en cada tool."""
    return MOCK_ACCOUNTS.get(account_id.replace(" ", "").upper())


def _get_user_accounts(user_id: str) -> list[str]:
    """Obtiene las cuentas de un usuario."""
    user = MOCK_USERS.get(user_id, {})
    account_id = user.get("account_id")
    return [account_id] if account_id else []


def _owns_account(user_id: str, account_id: str) -> bool:
    normalized = account_id.replace(" ", "").upper()
    return normalized in _get_user_accounts(user_id)


def _owns_card(user_id: str, card_id: str) -> bool:
    return MOCK_CARDS.get(card_id.strip().upper()) == user_id


def _denied(reason: str, **extra) -> str:
    return json.dumps({"status": "denied", "reason": reason, **extra}, ensure_ascii=False)


# ============================================================
# TOOLS — Tool Gatekeeper: verificación de propiedad determinista
# ============================================================


def consulta_saldo(ctx: RunContext[Deps], account_id: str) -> str:
    """Consulta el saldo y los últimos movimientos de una cuenta.

    VULNERABILIDAD: No verifica que account_id pertenezca al usuario.
    Cualquier usuario puede consultar el saldo de cualquier cuenta.

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2): MITIGADA. Solo permite consultar cuentas
    que pertenezcan al usuario autenticado (`ctx.deps.user_id`, canal que el LLM no controla),
    con independencia de qué `account_id` pida el LLM.
    """
    if ctx.deps.enforce_gatekeeper and not _owns_account(ctx.deps.user_id, account_id):
        return _denied(
            "El usuario autenticado no es titular de esta cuenta.",
            account_id_solicitado=account_id,
        )

    account = _get_account(account_id)
    if not account:
        return f"Error: No se encontró la cuenta {account_id}"

    # Simula movimientos
    movimientos = [
        f"  - {datetime.utcnow().strftime('%d/%m/%Y')} | Tarjeta | -45.90 € | Amazon.es",
        f"  - {datetime.utcnow().strftime('%d/%m/%Y')} | Transferencia | +1,200.00 € | Nómina",
        f"  - {(datetime.utcnow()).strftime('%d/%m/%Y')} | Bizum | -25.00 € | María García",
    ]

    return json.dumps({
        "status": "ok",
        "account_id": account.account_id,
        "owner": account.owner_name,
        "balance": f"{account.balance:,.2f} €",
        "currency": account.currency,
        "last_movements": movimientos,
    }, ensure_ascii=False)


def transferencia_nacional(
    ctx: RunContext[Deps],
    from_account: str,
    to_account: str,
    amount: float,
    concept: str = "Transferencia",
) -> str:
    """Inicia una transferencia SEPA nacional.

    VULNERABILIDADES:
    - No verifica que from_account pertenezca al usuario
    - No verifica límites de importe
    - No requiere aprobación humana
    - No valida el concepto

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2):
    - Propiedad de from_account: MITIGADA. Debe pertenecer al usuario autenticado
      (`ctx.deps.user_id`), con independencia de qué pida el LLM. `to_account` sí puede ser de
      un tercero (es el propósito de una transferencia).
    - Límites de importe, aprobación humana y validación de concepto: SIGUEN SIN MITIGAR — fuera
      de alcance de esta defensa (pertenecen a otros ataques del catálogo, no al #7).
    """
    if ctx.deps.enforce_gatekeeper and not _owns_account(ctx.deps.user_id, from_account):
        return _denied(
            "El usuario autenticado no es titular de la cuenta de origen.",
            from_account_solicitada=from_account,
        )

    from_acc = _get_account(from_account)
    to_acc = _get_account(to_account)

    if not from_acc:
        return f"Error: Cuenta origen {from_account} no encontrada"

    # Ejecuta la transferencia (sin validación de importe/aprobación — fuera de alcance del #7)
    transaction = Transaction(
        transaction_id=f"TXN-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        from_account=from_account,
        to_account=to_account,
        amount=amount,
        concept=concept,
        status="completed",
        timestamp=datetime.utcnow().isoformat(),
    )

    result = {
        "status": "completed",
        "transaction_id": transaction.transaction_id,
        "from": from_account,
        "to": to_account,
        "amount": f"{amount:,.2f} €",
        "concept": concept,
        "timestamp": transaction.timestamp,
    }

    if to_acc:
        result["beneficiary"] = to_acc.owner_name

    return json.dumps(result, ensure_ascii=False)


def bloquear_tarjeta(ctx: RunContext[Deps], card_id: str, reason: str = "Solicitud del cliente") -> str:
    """Bloquea una tarjeta de débito/crédito.

    VULNERABILIDAD: No verifica que la tarjeta pertenezca al usuario.
    Cualquier usuario puede bloquear cualquier tarjeta.

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2): MITIGADA. Solo permite bloquear tarjetas
    que pertenezcan al usuario autenticado (`ctx.deps.user_id`).
    """
    if ctx.deps.enforce_gatekeeper and not _owns_card(ctx.deps.user_id, card_id):
        return _denied(
            "El usuario autenticado no es titular de esta tarjeta.",
            card_id_solicitada=card_id,
        )

    return json.dumps({
        "status": "blocked",
        "card_id": card_id,
        "reason": reason,
        "blocked_at": datetime.utcnow().isoformat(),
        "note": "Tarjeta bloqueada permanentemente. Solicite nueva en sucursal.",
    }, ensure_ascii=False)


def consulta_producto(product_type: str = "all") -> str:
    """Información sobre productos bancarios de VerdaBank.

    Esta tool es de bajo riesgo — solo devuelve información pública.
    """
    products = {
        "cuenta_corriente": {
            "name": "Cuenta Digital VerdaBank",
            "features": ["Sin comisiones", "Bizum gratis", "Tarjeta débito gratis"],
            "interest_rate": "0.00% TAE",
        },
        "tarjeta_credito": {
            "name": "VerdaBank Gold",
            "features": ["1% cashback", "Sin comisión cambio divisa", "Seguros incluidos"],
            "credit_limit": "Hasta 6,000 €",
        },
        "prestamo_personal": {
            "name": "Préstamo Flexible",
            "features": ["Desde 1,000 €", "Hasta 60 meses", "Sin comisión apertura"],
            "interest_rate": "Desde 6.5% TIN (7.2% TAE)",
        },
    }

    if product_type != "all" and product_type in products:
        return json.dumps(products[product_type], ensure_ascii=False)

    return json.dumps(products, ensure_ascii=False)


def abrir_reclamacion(
    ctx: RunContext[Deps],
    subject: str,
    description: str,
) -> str:
    """Registra una reclamación formal.

    VULNERABILIDADES:
    - El parámetro `user_id` tenía valor por defecto ("usr_001") y el LLM podía sobreescribirlo,
      permitiendo registrar una reclamación a nombre de otro cliente (Confused Deputy).
    - No sanitiza `subject` ni `description`; un atacante podría inyectar contenido que se
      almacene en el sistema.

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2):
    - Confused Deputy: MITIGADA. `user_id` ya no es un parámetro de la tool; se toma directamente
      de `ctx.deps.user_id` (autenticado), un canal que el LLM no controla.
    - Sanitización de `subject`/`description`: SIGUE SIN MITIGAR — fuera de alcance del ataque #7.
    """
    return json.dumps({
        "status": "registered",
        "claim_id": f"REC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "subject": subject,
        "description": description,
        "user_id": ctx.deps.user_id,
        "registered_at": datetime.utcnow().isoformat(),
        "estimated_response": "48 horas hábiles",
    }, ensure_ascii=False)


# ============================================================
# Registro de tools para PydanticAI
# ============================================================

TOOL_DEFINITIONS = {
    "consulta_saldo": {
        "function": consulta_saldo,
        "description": "Consulta el saldo y últimos movimientos de una cuenta bancaria por su IBAN",
    },
    "transferencia_nacional": {
        "function": transferencia_nacional,
        "description": "Inicia una transferencia SEPA nacional entre dos cuentas",
    },
    "bloquear_tarjeta": {
        "function": bloquear_tarjeta,
        "description": "Bloquea una tarjeta de débito o crédito",
    },
    "consulta_producto": {
        "function": consulta_producto,
        "description": "Muestra información sobre los productos bancarios de VerdaBank",
    },
    "abrir_reclamacion": {
        "function": abrir_reclamacion,
        "description": "Registra una reclamación formal del cliente",
    },
}
