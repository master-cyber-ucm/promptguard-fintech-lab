"""Servicio de dominio bancario — el único que puede acreditar un efecto.

Quien ejecuta una operación es quien puede probar que ocurrió. Antes,
`agents/tools.py` construía un diccionario con `status: "completed"` y esa cadena era
toda la evidencia disponible: una llamada inválida, una pendiente de confirmación y una
transferencia real acababan indistinguibles para el Analyze Pass.

Aquí cada operación devuelve un `EffectReceipt` con su `operation_id`, los recursos
afectados, el sujeto autorizado y el momento del commit. Las lecturas también lo emiten
(`DATA_RETURNED`): saber qué datos salieron y hacia quién es tan necesario como saber
qué dinero se movió.
"""

from __future__ import annotations

from datetime import datetime, timezone

from src.models.banking import MOCK_ACCOUNTS, MOCK_CARDS, AccountInfo, Transaction
from src.models.tool_invocation import EffectClass, EffectReceipt, new_receipt

DOMAIN_VERSION = "banking.v1"

#: Estado mutable del lab. Vive aquí, no en las tools: el dominio es el dueño del
#: estado y por tanto el único que puede decir que cambió.
_CARD_STATUS: dict[str, str] = {}
_COMMITTED_TRANSFERS: dict[str, dict] = {}


def reset_for_tests() -> None:
    _CARD_STATUS.clear()
    _COMMITTED_TRANSFERS.clear()


def get_account(account_id: str) -> AccountInfo | None:
    return MOCK_ACCOUNTS.get(account_id.replace(" ", "").upper())


def card_status(card_id: str) -> str:
    return _CARD_STATUS.get(card_id.strip().upper(), "active")


# ── Lecturas ─────────────────────────────────────────────────────────────────

def read_account(
    *, invocation_id: str, actor_subject: str, account_id: str
) -> tuple[dict, EffectReceipt] | None:
    """Devuelve el resumen de una cuenta y el recibo de los datos entregados."""
    account = get_account(account_id)
    if account is None:
        return None
    movimientos = [
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Tarjeta | -45.90 € | Amazon.es",
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Transferencia | +1,200.00 € | Nómina",
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Bizum | -25.00 € | María García",
    ]
    payload = {
        "account_id": account.account_id,
        "owner": account.owner_name,
        "balance": f"{account.balance:,.2f} €",
        "currency": account.currency,
        "last_movements": movimientos,
    }
    receipt = new_receipt(
        invocation_id=invocation_id,
        effect_class=EffectClass.DATA_RETURNED,
        actor_subject=actor_subject,
        resource_refs=(f"account:{account.account_id}",),
        verification=f"as_of={datetime.now(timezone.utc).isoformat()}",
    )
    return payload, receipt


def read_account_summary(
    *, invocation_id: str, actor_subject: str, account_id: str
) -> tuple[dict, EffectReceipt] | None:
    account = get_account(account_id)
    if account is None:
        return None
    payload = {
        "account_id": account.account_id,
        "account_id_masked": f"{account.account_id[:4]}····{account.account_id[-4:]}",
        "available_balance": f"{account.balance:,.2f} €",
        "currency": account.currency,
        "account_status": account.status,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }
    receipt = new_receipt(
        invocation_id=invocation_id,
        effect_class=EffectClass.DATA_RETURNED,
        actor_subject=actor_subject,
        resource_refs=(f"account:{account.account_id}",),
    )
    return payload, receipt


# ── Escrituras ───────────────────────────────────────────────────────────────

def commit_transfer(
    *,
    invocation_id: str,
    actor_subject: str,
    from_account: str,
    to_account: str,
    amount: float,
    concept: str,
) -> tuple[dict, EffectReceipt]:
    """Consuma una transferencia y emite el comprobante del movimiento."""
    transaction = Transaction(
        transaction_id=f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        from_account=from_account, to_account=to_account, amount=amount,
        concept=concept, status="completed",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    payload = {
        "transaction_id": transaction.transaction_id,
        "from": from_account,
        "to": to_account,
        "amount": f"{amount:,.2f} €",
        "concept": concept,
        "timestamp": transaction.timestamp,
        # `resolved` distingue el Atributo resuelto por el backend del Argumento
        # solicitado por el modelo.
        "resolved": {"from_account": from_account},
    }
    beneficiario = get_account(to_account)
    if beneficiario:
        payload["beneficiary"] = beneficiario.owner_name

    _COMMITTED_TRANSFERS[transaction.transaction_id] = payload
    receipt = new_receipt(
        invocation_id=invocation_id,
        effect_class=EffectClass.STATE_COMMITTED,
        actor_subject=actor_subject,
        resource_refs=(f"account:{from_account}", f"account:{to_account}"),
        operation_id=transaction.transaction_id,
        # Verificación posterior: el movimiento es consultable después del commit, no
        # solo afirmado en la respuesta de la propia operación.
        verification=f"transfer_lookup:{transaction.transaction_id}",
    )
    return payload, receipt


def transfer_exists(transaction_id: str) -> bool:
    """Lectura posterior que verifica un commit — no la afirmación del wrapper."""
    return transaction_id in _COMMITTED_TRANSFERS


def commit_card_block(
    *, invocation_id: str, actor_subject: str, card_id: str, reason: str
) -> tuple[dict, EffectReceipt]:
    normalized = card_id.strip().upper()
    _CARD_STATUS[normalized] = "blocked"
    payload = {
        "card_id": card_id,
        "card_status": "blocked",
        "reason": reason,
        "blocked_at": datetime.now(timezone.utc).isoformat(),
        "note": "Tarjeta bloqueada permanentemente. Solicite nueva en sucursal.",
    }
    receipt = new_receipt(
        invocation_id=invocation_id,
        effect_class=EffectClass.STATE_COMMITTED,
        actor_subject=actor_subject,
        resource_refs=(f"card:{normalized}",),
        operation_id=f"CARDBLOCK-{normalized}",
        verification=f"card_status:{normalized}",
    )
    return payload, receipt


def commit_claim(
    *, invocation_id: str, actor_subject: str, subject: str, description: str
) -> tuple[dict, EffectReceipt]:
    claim_id = f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    payload = {
        "claim_status": "registered",
        "claim_id": claim_id,
        "subject": subject,
        "description": description,
        "user_id": actor_subject,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "estimated_response": "48 horas hábiles",
    }
    receipt = new_receipt(
        invocation_id=invocation_id,
        effect_class=EffectClass.STATE_COMMITTED,
        actor_subject=actor_subject,
        resource_refs=(f"claim:{claim_id}",),
        operation_id=claim_id,
    )
    return payload, receipt


def owns_card(user_id: str, card_id: str) -> bool:
    return MOCK_CARDS.get(card_id.strip().upper()) == user_id
