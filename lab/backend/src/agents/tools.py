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
determinista en `src/core/leak_guard.py` (`confidential_leak_guard`), no en este módulo. Ver
henri-tfm/02-defensa/README.md §"Mejoras aplicadas tras la verificación manual".
"""

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic_ai import RunContext

from src.core import tool_permissions
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
    """Recupera el saldo disponible, la moneda y los últimos movimientos de una cuenta.

    Es una consulta de lectura: devuelve datos y no modifica ningún producto bancario. Sin
    `account_id`, recupera el resumen de la cuenta principal del cliente autenticado. Con
    `account_id`, recupera el resumen de la cuenta identificada. La respuesta incluye el saldo,
    la divisa, el titular y una lista de movimientos recientes.
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
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Tarjeta | -45.90 € | Amazon.es",
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Transferencia | +1,200.00 € | Nómina",
        f"  - {datetime.now(timezone.utc).strftime('%d/%m/%Y')} | Bizum | -25.00 € | María García",
    ]

    return json.dumps({
        "status": "ok",
        "account_id": account.account_id,
        "owner": account.owner_name,
        "balance": f"{account.balance:,.2f} €",
        "currency": account.currency,
        "last_movements": movimientos,
    }, ensure_ascii=False)


def _ejecutar_transferencia(from_account: str, to_account: str, amount: float, concept: str) -> dict:
    """Efecto real de la transferencia — separado de `transferencia_nacional` para que la
    rama de confirmación fuera de banda (`tool_permissions.confirmar`) pueda invocarlo de
    forma perezosa, exactamente igual que la rama directa."""
    to_acc = _get_account(to_account)
    transaction = Transaction(
        transaction_id=f"TXN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        from_account=from_account, to_account=to_account, amount=amount,
        concept=concept, status="completed", timestamp=datetime.now(timezone.utc).isoformat(),
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
    return result


def transferencia_nacional(
    ctx: RunContext[Deps],
    to_account: str,
    amount: float,
    from_account: Optional[str] = None,
    concept: str = "Transferencia",
) -> str:
    """Inicia una transferencia SEPA nacional y genera una operación financiera.

    Requiere el IBAN de destino (`to_account`) y el importe (`amount`); el concepto es opcional.
    `from_account` identifica la cuenta de origen y, si se omite, se utiliza la cuenta principal
    del cliente autenticado. La operación debita el importe de origen y lo acredita en el destino.
    Devuelve el estado, los identificadores de la transacción y el detalle de importe, cuentas y
    concepto. Para importes sujetos a aprobación, devuelve una operación pendiente con su
    identificador en lugar de una transacción completada.
    """
    _t0 = time.perf_counter()

    # `forbidden_params` del YAML (`override_limit`, `bypass_approval`, `admin_mode`) se
    # cumplen de forma ESTRUCTURAL: ninguno es un parámetro de esta función, así que
    # pydantic-ai nunca genera un schema de tool que permita al LLM enviarlos — no hay
    # branch en runtime que revalidar. `tool_permissions.forbidden_presentes()` queda
    # disponible como utilidad (testeada en aislado) para tools futuras que sí acepten
    # kwargs abiertos; no aplica aquí. Ver plan de excelencia §A1.

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
    if not from_acc:
        return f"Error: Cuenta origen {from_account} no encontrada"

    # Límites e aprobación fuera de banda — `tool_permissions.yaml`. Fail-closed: si la tool
    # no está declarada en el YAML, `limite_para` devuelve None y no se aplica ningún límite
    # (comportamiento previo) — declarar la tool en el YAML es lo que activa el control.
    role = MOCK_USERS.get(ctx.deps.user_id, {}).get("role", "customer")
    limite = tool_permissions.limite_para("transferencia_nacional", role)
    if ctx.deps.enforce_gatekeeper and limite:
        max_amount = limite.get("max_amount")
        if max_amount is not None and amount > max_amount:
            add_safe(
                getattr(ctx.deps, "collector", None), componente="tool_gatekeeper", objetivo="tool",
                accion="BLOCK", razon=f"Importe {amount} supera el máximo permitido para el rol ({max_amount}).",
                regla="limits.max_amount", confianza=1.0, attack_type="limit_exceeded",
                detalle={"tool": "transferencia_nacional", "amount": amount, "max_amount": max_amount},
                latencia_ms=(time.perf_counter() - _t0) * 1000,
            )
            return _denied(
                "Importe supera el límite permitido para tu rol.",
                amount=amount, max_amount=max_amount,
            )

        umbral = limite.get("requires_approval_above")
        if umbral is not None and amount > umbral:
            operation_id, token = tool_permissions.crear_pendiente(
                tool="transferencia_nacional", user_id=ctx.deps.user_id,
                detalle={"from_account": from_account, "to_account": to_account, "amount": amount, "concept": concept},
                ejecutar=lambda: _ejecutar_transferencia(from_account, to_account, amount, concept),
            )
            add_safe(
                getattr(ctx.deps, "collector", None), componente="tool_gatekeeper", objetivo="tool",
                accion="SUSPICIOUS",
                razon=f"Importe {amount} supera el umbral de confirmación ({umbral}) — operación pendiente, no ejecutada.",
                regla="limits.requires_approval_above", confianza=1.0, attack_type=None,
                detalle={"tool": "transferencia_nacional", "amount": amount, "operation_id": operation_id},
                latencia_ms=(time.perf_counter() - _t0) * 1000,
            )
            return json.dumps({
                "status": "pending_confirmation",
                "operation_id": operation_id,
                # Lab: el token viaja en la misma respuesta para poder probar el flujo
                # end-to-end sin canal push real. En producción viaja por push/SMS — un
                # canal que el propio ataque conversacional no puede tocar (ver README de
                # la categoría, "confirmación humana cómo se hace bien").
                "confirm_token": token,
                "amount": amount, "to_account": to_account, "ttl_seconds": tool_permissions.TTL_SEGUNDOS,
                "message": (
                    "Esta operación supera el umbral de confirmación y NO se ha ejecutado. "
                    f"Confirme vía POST /api/v1/confirm/{operation_id} con el token recibido."
                ),
            }, ensure_ascii=False)

    return json.dumps(_ejecutar_transferencia(from_account, to_account, amount, concept), ensure_ascii=False)


def bloquear_tarjeta(
    ctx: RunContext[Deps],
    card_id: Optional[str] = None,
    reason: str = "Solicitud del cliente",
) -> str:
    """Bloquea una tarjeta de débito o crédito y cambia su estado a bloqueado.

    Sin `card_id`, actúa sobre la tarjeta principal del cliente autenticado. Con `card_id`, actúa
    sobre la tarjeta identificada. `reason` registra el motivo asociado al bloqueo. La respuesta
    incluye el estado final, la tarjeta afectada, el motivo y la marca temporal del bloqueo.
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
        "blocked_at": datetime.now(timezone.utc).isoformat(),
        "note": "Tarjeta bloqueada permanentemente. Solicite nueva en sucursal.",
    }, ensure_ascii=False)


def consulta_producto(product_type: str = "all") -> str:
    """Recupera información de los productos bancarios de VerdaBank.

    Es una consulta de lectura sin cambios de estado. Con `product_type="all"` devuelve el
    catálogo disponible; con un tipo concreto devuelve sus características, condiciones y datos
    comerciales asociados.
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
    """Registra una reclamación formal para el cliente autenticado.

    `subject` identifica el asunto y `description` recoge los hechos comunicados por el cliente.
    La operación crea un expediente de reclamación y devuelve su identificador, estado inicial,
    fecha de registro y plazo estimado de respuesta.
    """
    return json.dumps({
        "status": "registered",
        "claim_id": f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        "subject": subject,
        "description": description,
        "user_id": ctx.deps.user_id,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "estimated_response": "48 horas hábiles",
    }, ensure_ascii=False)


# ============================================================
# Registro de tools para PydanticAI
# ============================================================

TOOL_DEFINITIONS = {
    "consulta_saldo": {
        "function": consulta_saldo,
        "description": "Recupera el saldo, la divisa y los últimos movimientos de una cuenta sin modificar datos.",
    },
    "transferencia_nacional": {
        "function": transferencia_nacional,
        "description": "Inicia una transferencia SEPA nacional: debita la cuenta de origen y acredita la de destino.",
    },
    "bloquear_tarjeta": {
        "function": bloquear_tarjeta,
        "description": "Bloquea una tarjeta de débito o crédito y deja su estado como bloqueado.",
    },
    "consulta_producto": {
        "function": consulta_producto,
        "description": "Recupera características y condiciones de los productos bancarios sin modificar datos.",
    },
    "abrir_reclamacion": {
        "function": abrir_reclamacion,
        "description": "Crea un expediente de reclamación con asunto, descripción, identificador y plazo de respuesta.",
    },
}
