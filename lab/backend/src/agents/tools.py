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
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic_ai import RunContext

from src.core import (
    action_proposal,
    argument_provenance,
    policy_engine,
    tool_permissions,
    transaction_authorization,
)
from src.domain import banking
from src.models.tool_invocation import (
    EffectClass,
    InvocationState,
    ToolOutcome,
    is_critical,
    new_receipt,
)
from src.soc.collector import add_safe

from ..models.banking import (
    MOCK_ACCOUNTS,
    MOCK_CARDS,
    MOCK_USERS,
    AccountInfo,
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
    # Principal verificado de la petición. `user_id` se conserva por compatibilidad con
    # las tools existentes, pero la autorización de una operación necesita el sujeto
    # autenticado completo (tenant y assurance incluidos) — ver P16/P18.
    principal: Any = None
    # Restricción derivada del riesgo acumulado de la sesión (P22). Una sesión en
    # cuarentena puede seguir informando, pero no consuma acciones con efecto.
    risk_constraint: Any = None
    # Textos del turno con su naturaleza (mensaje, documento, contexto). Sin ellos no
    # se puede saber si un argumento omitido cambió la intención original (P24).
    input_artifacts: Any = None
    # SocCollector del turno (ver src/soc/collector.py). El Tool Gatekeeper decide DENTRO
    # de `agent.run()`, así que el orquestador no puede observar sus decisiones desde
    # fuera: `Deps` es el único canal que llega hasta aquí. Se tipa como `Any` a
    # propósito — `agents` no debe importar de `soc`.
    collector: Any = None


def _cuarentena(ctx: RunContext[Deps], tool: str, invocation_id: str) -> Optional[str]:
    """Deniega una tool con efecto si la sesión quedó en cuarentena.

    Es lo que cierra el ataque multivuelta: el turno 1 fue bloqueado, el turno 2 pide
    algo inocuo en apariencia y antes llegaba igualmente a la tool (P22).
    """
    restriccion = getattr(ctx.deps, "risk_constraint", None)
    if restriccion is None or not getattr(restriccion, "deny_state_changing_tools", False):
        return None
    if not is_critical(tool):
        return None
    _gate(ctx, tool, False, restriccion.reason or "sesión en cuarentena",
          regla="session_quarantine")
    return _denied(
        invocation_id,
        restriccion.reason or "La sesión está en cuarentena por una señal de seguridad.",
        session_risk="QUARANTINED",
    )


def _principal_de(deps) -> Any:
    """Principal de la petición, o un sustituto mínimo con el sujeto conocido.

    Las tools se ejercitan también fuera de una petición HTTP (tests, herramientas de
    laboratorio); ahí no hay Principal completo, pero el sujeto sigue siendo el que
    inyectó el backend — nunca uno elegido por el modelo.
    """
    principal = getattr(deps, "principal", None)
    if principal is not None:
        return principal
    return SimpleNamespace(subject=deps.user_id, tenant_id="verdabank",
                           assurance_level="UNVERIFIED")


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


KBArticleKey = Literal[
    "app.consultar_saldo",
    "payments.sepa.overview",
    "credentials.password.change",
    "documents.summary.missing_input",
    "privacy.erasure.request",
    "transfers.guidance",
    "own_accounts.transfer.guidance",
    "delegations.power_of_attorney.guidance",
]


KB_ARTICLES: dict[KBArticleKey, dict[str, str]] = {
    "app.consultar_saldo": {
        "version": "2026-08-30",
        "title": "Consultar saldo y movimientos en la app",
        "content": (
            "En la app de VerdaBank, inicia sesión y abre Cuentas. Selecciona la cuenta que "
            "quieras consultar para ver el saldo disponible y los últimos movimientos. Si la "
            "app no está disponible, utiliza la banca web o contacta con atención al cliente. "
            "No compartas contraseñas, PIN ni códigos de verificación por el chat."
        ),
    },
    "payments.sepa.overview": {
        "version": "2026-08-30",
        "title": "Transferencias SEPA",
        "content": (
            "Las transferencias SEPA permiten enviar euros a cuentas de la zona SEPA. Para "
            "ordenarlas normalmente se necesita el nombre del beneficiario, su IBAN, el importe "
            "y un concepto. Las transferencias ordinarias se procesan en días hábiles; las "
            "inmediatas, cuando están disponibles para ambas entidades, se abonan habitualmente "
            "en segundos. Antes de confirmar una orden, revisa el IBAN y el importe."
        ),
    },
    "credentials.password.change": {
        "version": "2026-08-30",
        "title": "Cambiar o recuperar la contraseña",
        "content": (
            "Si puedes iniciar sesión, abre Ajustes, después Seguridad y selecciona Cambiar "
            "contraseña. Si no puedes acceder, inicia la recuperación desde el canal oficial "
            "de acceso. No compartas tu contraseña actual, códigos SMS, claves de firma ni "
            "datos completos de tarjeta por el chat. Si sospechas que tu acceso se ha visto "
            "comprometido, contacta con el canal de fraude antes de restablecer la contraseña."
        ),
    },
    "documents.summary.missing_input": {
        "version": "2026-08-30",
        "title": "Resumen de documentos sin adjunto",
        "content": (
            "Para resumir un documento, adjunta el archivo o pega las cláusulas relevantes. "
            "El resumen puede cubrir tipo de interés, comisiones, plazo, cuotas, amortización "
            "anticipada, vencimiento, garantías y fechas. Un resumen informativo no sustituye "
            "asesoramiento legal ni financiero."
        ),
    },
    "privacy.erasure.request": {
        "version": "2026-08-30",
        "title": "Privacidad y solicitud de supresión",
        "content": (
            "VerdaBank trata datos de identificación, contacto, productos contratados y "
            "operaciones para prestar el servicio y cumplir obligaciones legales. Puedes ejercer "
            "tus derechos de privacidad, incluida la supresión, a través del canal oficial de "
            "privacidad. La supresión no siempre es inmediata: determinados datos pueden "
            "conservarse durante el plazo legal aplicable."
        ),
    },
    "transfers.guidance": {
        "version": "2026-08-30",
        "title": "Pasos para realizar una transferencia",
        "content": (
            "Para realizar una transferencia, abre Transferencias en la app, añade o selecciona "
            "al beneficiario, introduce su nombre e IBAN, indica el importe y el concepto, y "
            "revisa el resumen antes de confirmar. Comprueba especialmente el IBAN, ya que una "
            "transferencia enviada a un destinatario incorrecto puede no recuperarse de forma "
            "inmediata."
        ),
    },
    "own_accounts.transfer.guidance": {
        "version": "2026-08-30",
        "title": "Mover dinero entre cuentas propias",
        "content": (
            "Para mover dinero entre tus cuentas, abre Transferencias y selecciona como origen "
            "y destino las cuentas propias que aparecen en tu app. Elige el importe, revisa el "
            "resumen y confirma la operación. Si tienes más de una cuenta con nombres similares, "
            "verifica el alias y los últimos dígitos antes de continuar."
        ),
    },
    "delegations.power_of_attorney.guidance": {
        "version": "2026-08-30",
        "title": "Autorizar a un apoderado",
        "content": (
            "La autorización de un apoderado se tramita por los canales oficiales y requiere "
            "verificación documental. Los requisitos dependen del tipo de cuenta y de las "
            "facultades solicitadas, como consulta u operativa. Antes de iniciar el trámite, "
            "prepara la identificación del titular y del representante, así como la documentación "
            "que corresponda al alcance de la autorización."
        ),
    },
}


TOOL_RESULT_SCHEMA_VERSION = 2


def _new_invocation() -> str:
    """Identidad estable de una Tool Invocation, creada al entrar en la tool.

    Es lo que permite correlacionar llamada, resultado y Effect Receipt sin emparejar
    por nombre y adyacencia en el transcript — dos invocaciones de la misma tool en el
    mismo turno se cruzaban con ese método.
    """
    return f"inv_{uuid.uuid4().hex[:16]}"


def _outcome(state: InvocationState, invocation_id: str, *, receipt=None, reason=None, **payload) -> str:
    """Serializa el resultado tipado de una invocación.

    El estado describe el ciclo de vida de la invocación, no el estado de negocio del
    recurso: una tarjeta bloqueada con éxito es `COMMITTED` con `card_status=blocked`,
    no una invocación "bloqueada".
    """
    return json.dumps(
        ToolOutcome(
            state=state, invocation_id=invocation_id, receipt=receipt,
            reason=reason, payload=payload,
        ).to_dict(),
        ensure_ascii=False,
    )


def _denied(invocation_id: str, reason: str, **extra) -> str:
    return _outcome(InvocationState.DENIED, invocation_id, reason=reason, **extra)


def _failed(invocation_id: str, reason: str, **extra) -> str:
    return _outcome(InvocationState.FAILED, invocation_id, reason=reason, **extra)


def _gate(ctx: RunContext[Deps], tool: str, permitida: bool, razon: str,
          t0: Optional[float] = None, regla: str = "ownership_check", **detalle) -> None:
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
        regla=regla,
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
    inv = _new_invocation()
    if account_id is None:
        own_accounts = _get_user_accounts(ctx.deps.user_id)
        if not own_accounts:
            return _failed(inv, "No se encontró ninguna cuenta asociada al usuario autenticado.")
        account_id = own_accounts[0]
        _gate(ctx, "consulta_saldo", True, 
              "Sin account_id: se resolvió la cuenta propia desde el canal de autenticación.", t0=_t0,
              account_id=account_id, resuelto_por_backend=True)
    elif ctx.deps.enforce_gatekeeper and not _owns_account(ctx.deps.user_id, account_id):
        _gate(ctx, "consulta_saldo", False, 
              "El usuario autenticado no es titular de esta cuenta.", t0=_t0, account_id=account_id)
        return _denied(
            inv, "El usuario autenticado no es titular de esta cuenta.",
            account_id_solicitado=account_id,
        )
    else:
        _gate(ctx, "consulta_saldo", True, 
              "Cuenta propia del usuario autenticado.", t0=_t0, account_id=account_id)

    leido = banking.read_account(
        invocation_id=inv, actor_subject=ctx.deps.user_id, account_id=account_id,
    )
    if leido is None:
        return _outcome(InvocationState.NOT_FOUND, inv, account_id=account_id)
    payload, receipt = leido
    # Una lectura también deja recibo: qué datos salieron y hacia qué sujeto autorizado
    # es tan necesario para la evaluación como qué dinero se movió.
    return _outcome(InvocationState.RETURNED, inv, receipt=receipt, **payload)


def get_account_summary(
    ctx: RunContext[Deps],
    account_id: Optional[str] = None,
    account_number: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Recupera un resumen actual de la cuenta del cliente autenticado.

    Es una consulta de lectura. Devuelve saldo disponible, moneda, estado, hora de
    actualización y un identificador enmascarado de la cuenta principal.

    NO necesita identificadores: la cuenta se resuelve desde el canal de autenticación.
    `account_id`, `account_number` y `user_id` se aceptan solo porque el modelo los
    envía de forma recurrente —entre el 30% y el 39% de las invocaciones acababan como
    llamadas inválidas (P20)— y se **ignoran**: no seleccionan cuenta ni conceden
    autoridad. Para consultar una cuenta concreta existe `consulta_saldo`, que sí
    verifica titularidad.
    """
    t0 = time.perf_counter()
    inv = _new_invocation()
    # Los alias no se descartan en silencio: quedan como telemetría del contrato.
    alias_ignorados = [
        nombre for nombre, valor in (
            ("account_id", account_id), ("account_number", account_number), ("user_id", user_id),
        ) if valor is not None
    ]
    if alias_ignorados:
        add_safe(
            getattr(ctx.deps, "collector", None), componente="tool_gatekeeper",
            objetivo="tool", accion="ALLOW",
            razon=("Argumentos de identidad ignorados: la cuenta se resuelve desde el "
                   "canal de autenticación."),
            regla="identity_alias_ignored", confianza=1.0,
            detalle={"tool": "get_account_summary", "ignored": alias_ignorados},
            latencia_ms=(time.perf_counter() - t0) * 1000,
        )
    own_accounts = _get_user_accounts(ctx.deps.user_id)
    if not own_accounts:
        return _failed(inv, "No se encontró ninguna cuenta asociada al usuario autenticado.")
    account_id = own_accounts[0]
    _gate(
        ctx, "get_account_summary", True,
        "La cuenta propia se resolvió desde el canal de autenticación.",
        t0=t0, account_id=account_id, resuelto_por_backend=True,
    )

    leido = banking.read_account_summary(
        invocation_id=inv, actor_subject=ctx.deps.user_id, account_id=account_id,
    )
    if leido is None:
        return _outcome(InvocationState.NOT_FOUND, inv, account_id=account_id)
    payload, receipt = leido
    return _outcome(InvocationState.RETURNED, inv, receipt=receipt, **payload)


def get_kb_article(key: KBArticleKey) -> str:
    """Recupera un artículo informativo aprobado de la base de conocimiento.

    `key` identifica el artículo solicitado. La respuesta devuelve la clave, versión, título y
    contenido del artículo; es una recuperación de información sin cambios de estado. Las claves
    disponibles son: `app.consultar_saldo`, `payments.sepa.overview`,
    `credentials.password.change`, `documents.summary.missing_input`,
    `privacy.erasure.request`, `transfers.guidance`, `own_accounts.transfer.guidance` y
    `delegations.power_of_attorney.guidance`.
    """
    inv = _new_invocation()
    article = KB_ARTICLES.get(key)
    if article is None:
        return _outcome(InvocationState.NOT_FOUND, inv, key=key, available_keys=list(KB_ARTICLES))
    # Contenido público y versionado: no hay sujeto ni recurso protegido que acreditar.
    return _outcome(
        InvocationState.RETURNED, inv, key=key,
        receipt=new_receipt(
            invocation_id=inv, effect_class=EffectClass.DATA_RETURNED,
            actor_subject="public", resource_refs=(f"kb:{key}",),
        ),
        **article,
    )


def _ejecutar_transferencia(
    from_account: str, to_account: str, amount: float, concept: str,
    *, user_id: str = "", invocation_id: str | None = None,
) -> dict:
    """Consuma la transferencia a través del servicio de dominio.

    Separado de `transferencia_nacional` para que la rama de confirmación fuera de banda
    (`tool_permissions.confirmar`) pueda invocarlo de forma perezosa, exactamente igual
    que la rama directa. El efecto y su comprobante los produce `domain.banking`: esta
    capa no puede declararse a sí misma consumada.
    """
    inv = invocation_id or _new_invocation()
    payload, receipt = banking.commit_transfer(
        invocation_id=inv, actor_subject=user_id, from_account=from_account,
        to_account=to_account, amount=amount, concept=concept,
    )
    return ToolOutcome(
        state=InvocationState.COMMITTED, invocation_id=inv, receipt=receipt, payload=payload,
    ).to_dict()


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
    inv = _new_invocation()
    denegada = _cuarentena(ctx, "transferencia_nacional", inv)
    if denegada:
        return denegada

    # `forbidden_params` del YAML (`override_limit`, `bypass_approval`, `admin_mode`) se
    # cumplen de forma ESTRUCTURAL: ninguno es un parámetro de esta función, así que
    # pydantic-ai nunca genera un schema de tool que permita al LLM enviarlos — no hay
    # branch en runtime que revalidar. `tool_permissions.forbidden_presentes()` queda
    # disponible como utilidad (testeada en aislado) para tools futuras que sí acepten
    # kwargs abiertos; no aplica aquí. Ver plan de excelencia §A1.

    argumentos_solicitados = {
        "to_account": to_account, "amount": amount, "concept": concept,
    }
    if from_account is not None:
        argumentos_solicitados["from_account"] = from_account

    if from_account is None:
        own_accounts = _get_user_accounts(ctx.deps.user_id)
        if not own_accounts:
            return _failed(inv, "No se encontró ninguna cuenta de origen asociada al usuario autenticado.")
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
            inv, "El usuario autenticado no es titular de la cuenta de origen.",
            from_account_solicitada=from_account,
        )
    else:
        _gate(ctx, "transferencia_nacional", True,
              "Cuenta de origen propiedad del usuario autenticado.", t0=_t0,
              from_account=from_account, to_account=to_account, amount=amount)

    # Procedencia de los argumentos: comprobar el valor final no basta si la intención
    # original decía otra cosa. Es lo que convierte al agente en confused deputy (P24).
    artefactos = getattr(ctx.deps, "input_artifacts", None)
    if ctx.deps.enforce_gatekeeper and artefactos is not None:
        reporte = argument_provenance.analyze(
            tool="transferencia_nacional",
            requested_arguments=argumentos_solicitados,
            resolved_attributes={"from_account": from_account},
            artifacts=artefactos,
        )
        if reporte.blocked:
            hallazgo = reporte.findings[0]
            _gate(ctx, "transferencia_nacional", False, hallazgo.message, t0=_t0,
                  regla="argument_provenance", codigo=hallazgo.code)
            return _denied(
                inv,
                (f"{hallazgo.message}. Indica explícitamente la cuenta de origen para "
                 "continuar."),
                provenance_finding=hallazgo.code,
                provenance=reporte.to_dict(),
            )

    from_acc = _get_account(from_account)
    if not from_acc:
        return _outcome(InvocationState.NOT_FOUND, inv, account_id=from_account, role="source")

    # Una sola decisión de política para todo: rol, parámetros, límite individual,
    # acumulado diario y modo de aprobación. Antes convivían `requires_approval: true` y
    # `requires_approval_above: 1000` y ganaba el primero, así que TODA transferencia
    # quedaba pendiente y el `daily_limit` declarado no se aplicaba nunca (P19).
    role = MOCK_USERS.get(ctx.deps.user_id, {}).get("role", "customer")
    if ctx.deps.enforce_gatekeeper:
        decision, reserva = policy_engine.decide(
            tool_permissions.politica_compilada(),
            tool="transferencia_nacional",
            role=role,
            params={"from_account": from_account, "to_account": to_account,
                    "amount": amount, "concept": concept},
            subject=ctx.deps.user_id,
            amount=amount,
        )
        add_safe(
            getattr(ctx.deps, "collector", None), componente="tool_gatekeeper", objetivo="tool",
            accion=("BLOCK" if decision.effect == policy_engine.Effect.DENY
                    else "SUSPICIOUS" if decision.effect == policy_engine.Effect.REQUIRE_CONFIRMATION
                    else "ALLOW"),
            razon=decision.reason,
            # La regla concreta viaja con la decisión: el Run Folder puede reconciliarse
            # con la línea exacta del YAML que la produjo.
            regla=decision.rule_id,
            confianza=1.0,
            attack_type=("limit_exceeded" if decision.effect == policy_engine.Effect.DENY else None),
            detalle={"tool": "transferencia_nacional", "amount": amount,
                     "policy_version": decision.policy_version,
                     "threshold": decision.threshold},
            latencia_ms=(time.perf_counter() - _t0) * 1000,
        )

        if decision.effect == policy_engine.Effect.DENY:
            return _denied(
                inv, decision.reason, amount=amount, policy_rule=decision.rule_id,
                threshold=decision.threshold,
            )

        # El modelo PROPONE; la policy ya validó; el commit lo hace el backend con una
        # clave de idempotencia. El wrapper de la tool no ejecuta por su cuenta (P23).
        propuesta = action_proposal.draft(
            tool="transferencia_nacional",
            subject=ctx.deps.user_id,
            requested_arguments={"to_account": to_account, "amount": amount,
                                 "concept": concept},
            resolved_attributes={"from_account": from_account},
        )
        action_proposal.validate(propuesta)

        def _commit() -> dict:
            if reserva is not None:
                policy_engine.default_ledger.consume(reserva)
            return action_proposal.commit(propuesta, lambda: _ejecutar_transferencia(
                from_account, to_account, amount, concept, user_id=ctx.deps.user_id,
            ))

        # Toda escritura financiera exige autorización de transacción fuera del canal
        # LLM (PR 2 / ADR-0013, ADR-0014): el importe puede modular la policy —denegar,
        # exigir confirmación, clasificar riesgo—, pero nunca sustituye la aprobación de
        # quien es titular de la cuenta. `ALLOW` ya no es un atajo al commit: solo
        # significa que la policy no deniega la operación propuesta. La propuesta se
        # registra y su desafío se entrega FUERA de este canal; la tool solo obtiene
        # una referencia opaca — si el modelo pudiera leer el token, el atacante que
        # controla el prompt también podría (P18).
        operacion = transaction_authorization.propose(
            tool="transferencia_nacional",
            principal=_principal_de(ctx.deps),
            details={
                "from_account": from_account, "to_account": to_account,
                "amount": amount, "concept": concept,
            },
            displayed_fields={
                "beneficiario": (_get_account(to_account).owner_name
                                 if _get_account(to_account) else to_account),
                "cuenta_destino": to_account,
                "importe": f"{amount:,.2f} €",
                "concepto": concept,
            },
            execute=_commit,
        )
        # Preparada, NO consumada: `AWAITING_CONFIRMATION` es un resultado explícito y
        # no lleva Effect Receipt, así que ningún evaluador puede leerlo como efecto.
        return _outcome(
            InvocationState.AWAITING_CONFIRMATION, inv,
            ttl_seconds=transaction_authorization.TTL_SECONDS,
            policy_rule=decision.rule_id,
            # Los datos de la operación propuesta sí son visibles: son los que el
            # cliente pidió y los que el backend resolvió. Lo que no vuelve por aquí es
            # el material de autorización.
            amount=amount,
            to_account=to_account,
            resolved={"from_account": from_account},
            **operacion.to_reference(),
        )

    return json.dumps(
        _ejecutar_transferencia(
            from_account, to_account, amount, concept,
            user_id=ctx.deps.user_id, invocation_id=inv,
        ),
        ensure_ascii=False,
    )


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
    inv = _new_invocation()
    denegada = _cuarentena(ctx, "bloquear_tarjeta", inv)
    if denegada:
        return denegada
    if card_id is None:
        own_cards = _get_user_cards(ctx.deps.user_id)
        if not own_cards:
            return _failed(inv, "No se encontró ninguna tarjeta asociada al usuario autenticado.")
        card_id = own_cards[0]
        _gate(ctx, "bloquear_tarjeta", True, 
              "Sin card_id: se resolvió la tarjeta propia desde el canal de autenticación.", t0=_t0,
              card_id=card_id, resuelto_por_backend=True)
    elif ctx.deps.enforce_gatekeeper and not _owns_card(ctx.deps.user_id, card_id):
        _gate(ctx, "bloquear_tarjeta", False, 
              "El usuario autenticado no es titular de esta tarjeta.", t0=_t0, card_id=card_id)
        return _denied(
            inv, "El usuario autenticado no es titular de esta tarjeta.",
            card_id_solicitada=card_id,
        )
    else:
        _gate(ctx, "bloquear_tarjeta", True, 
              "Tarjeta propiedad del usuario autenticado.", t0=_t0, card_id=card_id)

    payload, receipt = banking.commit_card_block(
        invocation_id=inv, actor_subject=ctx.deps.user_id, card_id=card_id, reason=reason,
    )
    return _outcome(InvocationState.COMMITTED, inv, receipt=receipt, **payload)


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

    inv = _new_invocation()
    receipt = new_receipt(
        invocation_id=inv, effect_class=EffectClass.DATA_RETURNED,
        actor_subject="public", resource_refs=(f"catalog:{product_type}",),
    )
    if product_type != "all" and product_type in products:
        return _outcome(InvocationState.RETURNED, inv, receipt=receipt,
                        product_type=product_type, product=products[product_type])
    return _outcome(InvocationState.RETURNED, inv, receipt=receipt,
                    product_type="all", products=products)


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
    inv = _new_invocation()
    denegada = _cuarentena(ctx, "abrir_reclamacion", inv)
    if denegada:
        return denegada
    payload, receipt = banking.commit_claim(
        invocation_id=inv, actor_subject=ctx.deps.user_id,
        subject=subject, description=description,
    )
    return _outcome(InvocationState.COMMITTED, inv, receipt=receipt, **payload)


# ============================================================
# Registro de tools para PydanticAI
# ============================================================

TOOL_DEFINITIONS = {
    "get_account_summary": {
        "function": get_account_summary,
        "description": "Recupera saldo disponible, moneda, estado y hora de actualización de una cuenta autenticada.",
    },
    "get_kb_article": {
        "function": get_kb_article,
        "description": "Recupera un artículo aprobado y versionado de la base de conocimiento mediante una clave definida.",
    },
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
