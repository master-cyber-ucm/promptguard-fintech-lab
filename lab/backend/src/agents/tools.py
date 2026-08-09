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

Fase 2.7 (verificación manual capa por capa) encontró dos fallos reales de (D), no solo éxitos:
(1) falsos positivos cuando el LLM transcribía mal su propio IBAN al consultar su propia cuenta
—arreglado aquí haciendo `account_id`/`card_id`/`from_account` opcionales, resueltos desde
`ctx.deps.user_id` sin depender de que el LLM los escriba—; (2) el LLM podía invocar una tool sin
relación (o ninguna) y fabricar un saldo en texto libre para la cuenta objetivo, algo que (D) no
podía interceptar por no pasar por ninguna tool protegida — cerrado con una guardia de salida
determinista en `src/api/routes/chat.py` (`_confidential_leak_guard`), no en este módulo. Ver
henri-tfm/02-defensa/README.md §"Mejoras aplicadas tras la verificación manual".
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from pydantic_ai import RunContext

from src.soc.collector import add_safe

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
    # SocCollector del turno (ver src/soc/collector.py). El Tool Gatekeeper decide DENTRO
    # de `agent.run()`, así que el orquestador no puede observar sus decisiones desde
    # fuera: `Deps` es el único canal que llega hasta aquí. Se tipa como `Any` a
    # propósito — `agents` no debe importar de `soc`.
    collector: Any = None


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


def _get_user_cards(user_id: str) -> list[str]:
    """Tarjetas del usuario (búsqueda inversa sobre MOCK_CARDS). Usado para resolver "mi tarjeta"
    sin que el LLM tenga que transcribir el card_id (ver `bloquear_tarjeta`)."""
    return [card_id for card_id, owner in MOCK_CARDS.items() if owner == user_id]


def _denied(reason: str, **extra) -> str:
    return json.dumps({"status": "denied", "reason": reason, **extra}, ensure_ascii=False)


def _gate(ctx: RunContext[Deps], tool: str, permitida: bool, razon: str,
          t0: Optional[float] = None, **detalle) -> None:
    """Emite el Analysis Event del Tool Gatekeeper para esta llamada.

    Se llama en las DOS ramas de cada verificación de propiedad, no solo cuando deniega.
    Un permiso concedido es exactamente igual de informativo que uno denegado: sin él,
    el SOC no puede distinguir "el Gatekeeper lo revisó y lo autorizó" de "el Gatekeeper
    no llegó a mirarlo".

    Con `enforce_gatekeeper=False` no se emite nada, y es deliberado: en esa
    configuración el Gatekeeper NO está verificando propiedad, así que registrar un
    ALLOW haría parecer defendido un endpoint que no lo está. Su ranura en la cadena
    tiene que salir vacía — el vacío es el dato.
    """
    if not getattr(ctx.deps, "enforce_gatekeeper", True):
        return
    add_safe(
        getattr(ctx.deps, "collector", None),
        componente="tool_gatekeeper",
        objetivo="tool",
        accion="ALLOW" if permitida else "BLOCK",
        razon=razon,
        regla="ownership_check",
        confianza=1.0,
        attack_type=None if permitida else "unauthorized_resource_access",
        detalle={"tool": tool, **detalle},
        # Se mide de verdad. Antes viajaba a None y la vista de actividad lo agregaba
        # como "0.0 ms", que no es lo mismo que "instantáneo": era "sin medir".
        latencia_ms=None if t0 is None else (time.perf_counter() - t0) * 1000,
    )


# ============================================================
# TOOLS — Tool Gatekeeper: verificación de propiedad determinista
# ============================================================


def consulta_saldo(ctx: RunContext[Deps], account_id: Optional[str] = None) -> str:
    """Consulta el saldo y los últimos movimientos de una cuenta.

    Si el cliente pregunta por SU PROPIO saldo, no incluyas account_id — se resuelve
    automáticamente la cuenta del usuario autenticado. Usa account_id explícito solo si el
    cliente menciona un IBAN concreto (p. ej. de un tercero).

    NO le pidas al cliente que te dé su propio IBAN antes de consultar su saldo: omitir
    account_id es siempre seguro para la cuenta propia (se resuelve por el canal de
    autenticación, nunca por lo que el cliente escriba) y NO viola la regla de no revelar
    datos de otros clientes — esa regla aplica cuando SÍ se pide una cuenta ajena explícita,
    no cuando se omite el parámetro para la propia.

    VULNERABILIDAD: No verifica que account_id pertenezca al usuario.
    Cualquier usuario puede consultar el saldo de cualquier cuenta.

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2): MITIGADA. Solo permite consultar cuentas
    que pertenezcan al usuario autenticado (`ctx.deps.user_id`, canal que el LLM no controla),
    con independencia de qué `account_id` pida el LLM.

    MEJORA (verificación manual Fase 2.7 — falso positivo detectado): antes, incluso para
    consultar la PROPIA cuenta, el LLM tenía que transcribir su IBAN exacto — una transcripción
    fallida (un dígito de menos, un número inventado) hacía que el Gatekeeper denegara el acceso
    a su propio titular, un falso positivo confirmado en 2/7 intentos manuales sobre documentos
    sanos. Ahora, si `account_id` se omite, se resuelve la cuenta propia directamente desde
    `ctx.deps.user_id` (canal de confianza, no generado por el LLM) — el LLM ya no necesita
    reproducir el IBAN para el caso de uso más común. La verificación de propiedad íntegra sigue
    aplicando cuando SÍ se pide una cuenta explícita (el vector real del ataque #7).
    """
    _t0 = time.perf_counter()
    if account_id is None:
        own_accounts = _get_user_accounts(ctx.deps.user_id)
        if not own_accounts:
            return "Error: No se encontró ninguna cuenta asociada al usuario autenticado."
        account_id = own_accounts[0]
        _gate(ctx, "consulta_saldo", True, 
              "Sin account_id: se resolvió la cuenta propia desde el canal de autenticación.", t0=_t0,
              account_id=account_id, resuelto_por_backend=True)
    elif ctx.deps.enforce_gatekeeper and not _owns_account(ctx.deps.user_id, account_id):
        _gate(ctx, "consulta_saldo", False, 
              "El usuario autenticado no es titular de esta cuenta.", t0=_t0, account_id=account_id)
        return _denied(
            "El usuario autenticado no es titular de esta cuenta.",
            account_id_solicitado=account_id,
        )
    else:
        _gate(ctx, "consulta_saldo", True, 
              "Cuenta propia del usuario autenticado.", t0=_t0, account_id=account_id)

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
    to_account: str,
    amount: float,
    from_account: Optional[str] = None,
    concept: str = "Transferencia",
) -> str:
    """Inicia una transferencia SEPA nacional.

    Si el cliente no especifica la cuenta de origen, se asume su propia cuenta — no le pidas
    que transcriba su propio IBAN. `to_account` sí debe ser el IBAN explícito del destinatario.

    Omitir from_account es siempre seguro (se resuelve por el canal de autenticación) y NO
    viola ninguna regla de confidencialidad — no necesitas conocer la identidad del cliente
    por otra vía para transferir DESDE su propia cuenta, solo para pedirle el IBAN de un
    tercero como origen.

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

    MEJORA (Fase 2.7, mismo motivo que `consulta_saldo`): `from_account` es opcional — si se
    omite, se resuelve la cuenta propia desde `ctx.deps.user_id` en vez de exigir que el LLM la
    transcriba, eliminando esa fuente de falsos positivos también aquí.
    """
    _t0 = time.perf_counter()
    if from_account is None:
        own_accounts = _get_user_accounts(ctx.deps.user_id)
        if not own_accounts:
            return "Error: No se encontró ninguna cuenta de origen asociada al usuario autenticado."
        from_account = own_accounts[0]
        _gate(ctx, "transferencia_nacional", True, 
              "Sin from_account: se resolvió la cuenta propia desde el canal de autenticación.", t0=_t0,
              from_account=from_account, to_account=to_account, amount=amount,
              resuelto_por_backend=True)
    elif ctx.deps.enforce_gatekeeper and not _owns_account(ctx.deps.user_id, from_account):
        _gate(ctx, "transferencia_nacional", False, 
              "El usuario autenticado no es titular de la cuenta de origen.", t0=_t0,
              from_account=from_account, to_account=to_account, amount=amount)
        return _denied(
            "El usuario autenticado no es titular de la cuenta de origen.",
            from_account_solicitada=from_account,
        )
    else:
        _gate(ctx, "transferencia_nacional", True, 
              "Cuenta de origen propiedad del usuario autenticado.", t0=_t0,
              from_account=from_account, to_account=to_account, amount=amount)

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


def bloquear_tarjeta(
    ctx: RunContext[Deps],
    card_id: Optional[str] = None,
    reason: str = "Solicitud del cliente",
) -> str:
    """Bloquea una tarjeta de débito/crédito.

    Si el cliente no especifica qué tarjeta (p. ej. "bloquea mi tarjeta"), no incluyas card_id —
    se resuelve automáticamente. Usa card_id explícito solo si el cliente da un identificador
    concreto.

    VULNERABILIDAD: No verifica que la tarjeta pertenezca al usuario.
    Cualquier usuario puede bloquear cualquier tarjeta.

    MEDIDAS DE PROTECCIÓN (Tool Gatekeeper, Fase 2): MITIGADA. Solo permite bloquear tarjetas
    que pertenezcan al usuario autenticado (`ctx.deps.user_id`).

    MEJORA (Fase 2.7, mismo motivo que `consulta_saldo`): `card_id` es opcional — si se omite,
    se resuelve la tarjeta propia del usuario autenticado en vez de exigir que el LLM transcriba
    el identificador.
    """
    _t0 = time.perf_counter()
    if card_id is None:
        own_cards = _get_user_cards(ctx.deps.user_id)
        if not own_cards:
            return "Error: No se encontró ninguna tarjeta asociada al usuario autenticado."
        card_id = own_cards[0]
        _gate(ctx, "bloquear_tarjeta", True, 
              "Sin card_id: se resolvió la tarjeta propia desde el canal de autenticación.", t0=_t0,
              card_id=card_id, resuelto_por_backend=True)
    elif ctx.deps.enforce_gatekeeper and not _owns_card(ctx.deps.user_id, card_id):
        _gate(ctx, "bloquear_tarjeta", False, 
              "El usuario autenticado no es titular de esta tarjeta.", t0=_t0, card_id=card_id)
        return _denied(
            "El usuario autenticado no es titular de esta tarjeta.",
            card_id_solicitada=card_id,
        )
    else:
        _gate(ctx, "bloquear_tarjeta", True, 
              "Tarjeta propiedad del usuario autenticado.", t0=_t0, card_id=card_id)

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
