"""Endpoints de info — datos mock para testing.

Expone las cuentas y usuarios mock para facilitar los tests
de ataque. En un sistema real esto no existiría, pero en el
lab necesitamos saber qué datos hay para poder atacarlos.
"""

from fastapi import APIRouter

from src.models.banking import MOCK_ACCOUNTS, MOCK_USERS, MOCK_TRANSACTIONS

router = APIRouter(tags=["info"])


@router.get("/health")
async def health():
    """Health check del proceso; la postura se decide por endpoint y petición."""
    return {
        "status": "ok",
        "posture": "endpoint-selected",
        "message": "La defensa depende del endpoint llamado y del campo vulnerable de la petición.",
    }


@router.get("/accounts")
async def list_accounts():
    """Lista todas las cuentas mock del sistema.

    Expuesto intencionalmente para el lab — permite ver qué datos
    existen para planificar ataques (PII harvesting, confused deputy, etc.)
    """
    return {
        "total": len(MOCK_ACCOUNTS),
        "accounts": [
            {
                "iban": acc.account_id,
                "owner": acc.owner_name,
                "balance": acc.balance,
                "currency": acc.currency,
                "status": acc.status,
            }
            for acc in MOCK_ACCOUNTS.values()
        ],
    }


@router.get("/users")
async def list_users():
    """Lista todos los usuarios mock del sistema."""
    return {
        "total": len(MOCK_USERS),
        "users": list(MOCK_USERS.values()),
    }


@router.get("/transactions/{user_id}")
async def get_transactions(user_id: str):
    """Devuelve las transacciones mock de un usuario."""
    txs = MOCK_TRANSACTIONS.get(user_id, [])
    return {"user_id": user_id, "total": len(txs), "transactions": txs}
