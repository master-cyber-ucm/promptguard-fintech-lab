"""Tools bancarias MOCK para Clara — SIN PERMISOS, SIN VALIDACIÓN.

Este es el estado VULNERABLE de VerdaBank antes de PromptGuard.
Todas las tools aceptan cualquier parámetro sin verificar permisos,
propiedad de cuenta, ni límites. Esto es intencional para el lab.

Ataques habilitados:
- Excessive Agency: cualquier usuario puede usar cualquier tool
- Confused Deputy: consultar datos de terceros con tu sesión
- Cross-Context Leakage: el LLM filtra datos de otras cuentas
"""

import json
from datetime import datetime
from typing import Optional

from pydantic_ai import RunContext

from ..models.banking import (
    MOCK_ACCOUNTS,
    MOCK_USERS,
    AccountInfo,
    Transaction,
)


def _get_account(account_id: str) -> Optional[AccountInfo]:
    """Busca una cuenta por IBAN. No verifica permisos."""
    return MOCK_ACCOUNTS.get(account_id.replace(" ", "").upper())


def _get_user_accounts(user_id: str) -> list[str]:
    """Obtiene las cuentas de un usuario."""
    user = MOCK_USERS.get(user_id, {})
    account_id = user.get("account_id")
    return [account_id] if account_id else []


# ============================================================
# TOOLS — Todas son vulnerables por diseño
# ============================================================


def consulta_saldo(account_id: str) -> str:
    """Consulta el saldo y los últimos movimientos de una cuenta.

    VULNERABILIDAD: No verifica que account_id pertenezca al usuario.
    Cualquier usuario puede consultar el saldo de cualquier cuenta.
    """
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
    """
    from_acc = _get_account(from_account)
    to_acc = _get_account(to_account)

    if not from_acc:
        return f"Error: Cuenta origen {from_account} no encontrada"

    # Ejecuta la transferencia sin validación
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


def bloquear_tarjeta(card_id: str, reason: str = "Solicitud del cliente") -> str:
    """Bloquea una tarjeta de débito/crédito.

    VULNERABILIDAD: No verifica que la tarjeta pertenezca al usuario.
    Cualquier usuario puede bloquear cualquier tarjeta.
    """
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
    subject: str,
    description: str,
    user_id: str = "usr_001",
) -> str:
    """Registra una reclamación formal.

    VULNERABILIDAD: No sanitiza el subject ni description.
    Un atacante podría inyectar contenido que se almacene en el sistema.
    """
    return json.dumps({
        "status": "registered",
        "claim_id": f"REC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        "subject": subject,
        "description": description,
        "user_id": user_id,
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
