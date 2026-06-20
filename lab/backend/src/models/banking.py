"""Modelos bancarios para PromptGuard FinTech.

Entidades financieras detectables por el sistema: IBAN, tarjetas,
SWIFT, saldos, y datos de cuenta.
"""

import re
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class BankingEntityType(str, Enum):
    IBAN = "IBAN"
    CREDIT_CARD = "CREDIT_CARD"
    SWIFT = "SWIFT"
    BALANCE = "BALANCE"
    PHONE = "PHONE"
    EMAIL = "EMAIL"
    DNI = "DNI"


class PIIEntity(BaseModel):
    """Entidad PII detectada en un mensaje."""
    type: BankingEntityType
    value_original: str = Field(..., description="Valor original detectado")
    value_tokenized: str = Field(..., description="Valor tokenizado/anonimizado")
    position_start: int = Field(..., description="Posición inicio en el texto")
    position_end: int = Field(..., description="Posición fin en el texto")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AccountInfo(BaseModel):
    """Información de cuenta bancaria del usuario autenticado."""
    account_id: str = Field(..., description="IBAN de la cuenta")
    owner_name: str = Field(..., description="Nombre del titular")
    balance: float = Field(default=0.0, description="Saldo actual")
    currency: str = Field(default="EUR")
    status: str = Field(default="active")

    @field_validator("account_id")
    @classmethod
    def validate_iban(cls, v: str) -> str:
        """Valida formato básico de IBAN español."""
        iban_clean = v.replace(" ", "").upper()
        if not re.match(r"^ES\d{22}$", iban_clean):
            raise ValueError(f"IBAN inválido: {v}")
        return iban_clean


class Transaction(BaseModel):
    """Transacción bancaria simulada."""
    transaction_id: str
    from_account: str
    to_account: str
    amount: float = Field(..., gt=0)
    currency: str = Field(default="EUR")
    concept: str = Field(default="")
    status: str = Field(default="pending")
    timestamp: str = ""


class BankingToolCall(BaseModel):
    """Llamada a tool bancaria generada por el agente."""
    tool: str = Field(..., description="Nombre de la tool")
    parameters: dict = Field(default_factory=dict)
    requires_human_approval: bool = Field(default=False)
    risk_level: str = Field(default="low")


# --- Datos mock de cuentas para el lab ---

MOCK_ACCOUNTS: dict[str, AccountInfo] = {
    "ES9121000418450200051332": AccountInfo(
        account_id="ES9121000418450200051332",
        owner_name="María García López",
        balance=15420.50,
        currency="EUR",
        status="active",
    ),
    "ES7621000418450200051333": AccountInfo(
        account_id="ES7621000418450200051333",
        owner_name="Carlos Rodríguez Martín",
        balance=8750.25,
        currency="EUR",
        status="active",
    ),
    "ES3421000418450200051334": AccountInfo(
        account_id="ES3421000418450200051334",
        owner_name="Ana Fernández Ruiz",
        balance=231500.00,
        currency="EUR",
        status="active",
    ),
    "ES5821000418450200051335": AccountInfo(
        account_id="ES5821000418450200051335",
        owner_name="Admin Banco",
        balance=999999.99,
        currency="EUR",
        status="active",
    ),
}

# Usuarios mock del sistema
MOCK_USERS: dict[str, dict] = {
    "usr_001": {
        "user_id": "usr_001",
        "name": "María García López",
        "role": "customer",
        "account_id": "ES9121000418450200051332",
    },
    "usr_002": {
        "user_id": "usr_002",
        "name": "Carlos Rodríguez Martín",
        "role": "customer",
        "account_id": "ES7621000418450200051333",
    },
    "usr_003": {
        "user_id": "usr_003",
        "name": "Ana Fernández Ruiz",
        "role": "customer",
        "account_id": "ES3421000418450200051334",
    },
    "usr_admin": {
        "user_id": "usr_admin",
        "name": "Admin Banco",
        "role": "admin",
        "account_id": "ES5821000418450200051335",
    },
}


# --- Transacciones mock por usuario ---

MOCK_TRANSACTIONS: dict[str, list[dict]] = {
    "usr_001": [
        {"date": "12/06/2026", "desc": "Nomina junio", "amount": 3200.00, "type": "Transferencia"},
        {"date": "12/06/2026", "desc": "Amazon.es", "amount": -45.90, "type": "Tarjeta"},
        {"date": "11/06/2026", "desc": "Bizum a Carlos R.", "amount": -25.00, "type": "Bizum"},
        {"date": "10/06/2026", "desc": "Netflix", "amount": -12.99, "type": "Suscripcion"},
        {"date": "09/06/2026", "desc": "Supermercado Dia", "amount": -67.34, "type": "Tarjeta"},
        {"date": "08/06/2026", "desc": "Transferencia de Ana F.", "amount": 150.00, "type": "Transferencia"},
        {"date": "07/06/2026", "desc": "Spotify", "amount": -9.99, "type": "Suscripcion"},
        {"date": "05/06/2026", "desc": "Farmacia Garcia", "amount": -23.45, "type": "Tarjeta"},
        {"date": "03/06/2026", "desc": "Nomina junio (adelanto)", "amount": 500.00, "type": "Transferencia"},
        {"date": "01/06/2026", "desc": "Recibo luz", "amount": -62.30, "type": "Recibo"},
    ],
    "usr_002": [
        {"date": "12/06/2026", "desc": "Nomina", "amount": 2100.00, "type": "Transferencia"},
        {"date": "11/06/2026", "desc": "Alquiler junio", "amount": -850.00, "type": "Recibo"},
        {"date": "10/06/2026", "desc": "Carrefour", "amount": -92.15, "type": "Tarjeta"},
        {"date": "09/06/2026", "desc": "Bizum de Maria G.", "amount": 25.00, "type": "Bizum"},
        {"date": "08/06/2026", "desc": "Gimnasio FitLife", "amount": -39.90, "type": "Suscripcion"},
        {"date": "06/06/2026", "desc": "Gasolinera Repsol", "amount": -55.00, "type": "Tarjeta"},
        {"date": "04/06/2026", "desc": "Transferencia a Ana F.", "amount": -200.00, "type": "Transferencia"},
        {"date": "02/06/2026", "desc": "Recibo internet", "amount": -35.00, "type": "Recibo"},
        {"date": "01/06/2026", "desc": "Zara", "amount": -48.99, "type": "Tarjeta"},
        {"date": "30/05/2026", "desc": "Reembolso IRPF", "amount": 430.00, "type": "Transferencia"},
    ],
    "usr_003": [
        {"date": "12/06/2026", "desc": "Dividendo invertido", "amount": 1850.00, "type": "Inversion"},
        {"date": "11/06/2026", "desc": "Transferencia a Maria G.", "amount": -150.00, "type": "Transferencia"},
        {"date": "10/06/2026", "desc": "Iberia (vuelo)", "amount": -245.00, "type": "Tarjeta"},
        {"date": "09/06/2026", "desc": "El Corte Ingles", "amount": -178.50, "type": "Tarjeta"},
        {"date": "08/06/2026", "desc": "Recibo comunidad", "amount": -120.00, "type": "Recibo"},
        {"date": "07/06/2026", "desc": "Reembolso seguro", "amount": 340.00, "type": "Transferencia"},
        {"date": "05/06/2026", "desc": "Bizum a Carlos R.", "amount": 200.00, "type": "Bizum"},
        {"date": "03/06/2026", "desc": "Aportacion plan pensiones", "amount": -500.00, "type": "Inversion"},
        {"date": "01/06/2026", "desc": "Nomina asesoramiento", "amount": 4500.00, "type": "Transferencia"},
        {"date": "28/05/2026", "desc": "Apple Store", "amount": -1299.00, "type": "Tarjeta"},
    ],
    "usr_admin": [
        {"date": "12/06/2026", "desc": "Transferencia interna", "amount": 50000.00, "type": "Transferencia"},
        {"date": "11/06/2026", "desc": "Pago proveedor Cloud", "amount": -2400.00, "type": "Transferencia"},
        {"date": "10/06/2026", "desc": "Nomina directivos", "amount": -12500.00, "type": "Nomina"},
        {"date": "09/06/2026", "desc": "Ingreso capital", "amount": 100000.00, "type": "Transferencia"},
        {"date": "08/06/2026", "desc": "Licencia software", "amount": -3200.00, "type": "Recibo"},
        {"date": "07/06/2026", "desc": "Auditora Deloitte", "amount": -8500.00, "type": "Transferencia"},
        {"date": "05/06/2026", "desc": "Reserva regulatoria", "amount": -50000.00, "type": "Reserva"},
        {"date": "03/06/2026", "desc": "Custodia valores", "amount": 15000.00, "type": "Inversion"},
        {"date": "01/06/2026", "desc": "Alquiler oficinas", "amount": -4800.00, "type": "Recibo"},
        {"date": "28/05/2026", "desc": "Reembolso prestamo", "amount": 25000.00, "type": "Transferencia"},
    ],
}
