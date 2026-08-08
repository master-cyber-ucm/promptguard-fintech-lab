"""PII Shield — defensa de LLM02:2025 PII Harvesting vía Contexto (ataque #6 del catálogo).

Sustituye el esqueleto no-op anterior. Cubre los dos flancos del vector, con dos controles de
naturaleza distinta que se documentan por separado porque tienen garantías distintas:

  1. ENTRADA — `PIIShieldStage.evaluate()`: detecta *intención de enumeración masiva*
     ("enumera todos los IBANs", "datos completos de todos los clientes"). Es un control de
     patrón: barato, determinista y evadible con una paráfrasis suficientemente creativa. Su
     función es reducir volumen y dejar traza, NO garantizar nada.

  2. SALIDA — `redact_foreign_pii()`: verifica que ningún dato personal presente en la respuesta
     pertenezca a un tercero, cruzándolo contra el conjunto de datos que el `user_id` AUTENTICADO
     tiene derecho a ver (resuelto desde los datos mock del lab, no desde el contexto del modelo).
     Este sí es determinista y no depende de anticipar la formulación del ataque: no pregunta
     "¿parece esto un ataque?" sino "¿es este dato suyo?", que es una comparación cerrada.

El peso de la defensa recae deliberadamente en (2). (1) existe porque un intento de cosecha
masiva es señal de reconocimiento que interesa registrar aunque el modelo no llegue a responder
nada — no porque se confíe en que lo pare.

Relación con los controles ya existentes (no se solapan, se complementan):

  - `_confidential_leak_guard` (api/routes/chat.py, Fase 2.7): cubre IBANs ajenos no respaldados
    por una tool call real. Es más estricto que este módulo para IBANs (exige respaldo de tool)
    pero solo cubre IBANs. Este módulo cubre el resto de entidades — nombre de titular, saldo,
    tarjeta, DNI, teléfono, email — que aquella guardia no mira.
  - `output_auditor.audit_response`: cubre SECRETOS DE CONFIGURACIÓN (LLM07), no datos de
    clientes. Ejes distintos.
  - Tool Gatekeeper (`agents/tools.py`): impide que el dato ajeno ENTRE al contexto vía tool.
    Este módulo asume que el Gatekeeper puede haber sido esquivado (p. ej. el modelo fabrica el
    dato, o lo arrastra de un documento adjunto) y controla la SALIDA.

Limitación conocida y no resuelta: la fuga semántica sin emisión del dato ("esa cuenta tiene
fondos de sobra para cubrir los 3.000 €") no es detectable por comparación de valores. Se
documenta como límite del control, no se finge cobertura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from .base import Stage, StageContext
from src.models.banking import (
    MOCK_ACCOUNTS,
    MOCK_CARDS,
    MOCK_USERS,
    BankingEntityType,
    PIIEntity,
)
from src.models.interaction import PromptDecision

PATTERNS_PATH = Path(__file__).parent.parent.parent / "config" / "rules" / "banking_patterns.yaml"

# Mensaje único de sustitución cuando la respuesta se descarta entera. No detalla qué dato se
# detectó ni sobre qué cliente: un rechazo que explica el motivo confirma al atacante que el dato
# existe, que es justo la información que la cosecha busca.
_SAFE_MESSAGE = (
    "No puedo compartir datos personales o financieros de otros clientes. "
    "¿Puedo ayudarte con algo de tu propia cuenta?"
)

# Umbral de "cosecha masiva": a partir de N terceros distintos identificados en una misma
# respuesta, se descarta la respuesta completa en vez de tokenizar entidad a entidad. Motivo: un
# volcado parcialmente tokenizado sigue revelando la ESTRUCTURA (cuántos clientes hay, qué campos
# se guardan de cada uno), que es información útil para el atacante aunque los valores vayan
# ocultos. Con un solo tercero, la tokenización conserva una respuesta útil para el cliente.
_UMBRAL_COSECHA_MASIVA = 2


# ──────────────────────────────────────────────────────────────────────────────
# Carga de patrones
# ──────────────────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _patterns() -> dict[str, dict]:
    """Patrones de `config/rules/banking_patterns.yaml` — el mismo fichero que ya declaraba el
    equipo para PII Shield y Output Auditor, hasta ahora nunca conectado a código."""
    data = yaml.safe_load(PATTERNS_PATH.read_text(encoding="utf-8"))
    return data["patterns"]


# Mapeo del nombre de patrón del YAML al tipo de entidad del modelo de dominio. Los patrones de
# tarjeta son dos (Visa y Mastercard) pero un solo tipo de entidad.
_TIPO_POR_PATRON = {
    "iban": BankingEntityType.IBAN,
    "credit_card_visa": BankingEntityType.CREDIT_CARD,
    "credit_card_mastercard": BankingEntityType.CREDIT_CARD,
    "swift": BankingEntityType.SWIFT,
    "balance_eur": BankingEntityType.BALANCE,
    "phone_es": BankingEntityType.PHONE,
    "email": BankingEntityType.EMAIL,
    "dni": BankingEntityType.DNI,
}


@lru_cache(maxsize=1)
def _compiled() -> list[tuple[str, re.Pattern, str]]:
    """(nombre, regex compilado, formato de token) por patrón del YAML."""
    out = []
    for nombre, spec in _patterns().items():
        if nombre not in _TIPO_POR_PATRON:
            continue
        out.append((nombre, re.compile(spec["regex"]), spec.get("token_format", "[REDACTED]")))
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Conjunto autorizado — qué datos puede ver el usuario autenticado
# ──────────────────────────────────────────────────────────────────────────────

def _normalizar_iban(valor: str) -> str:
    return valor.replace(" ", "").replace("-", "").upper()


def _variantes_importe(cantidad: float) -> set[str]:
    """Representaciones textuales del mismo importe que puede emitir el modelo.

    El lab formatea con `f"{balance:,.2f}"` (estilo anglosajón: 231,500.00) pero el system prompt
    de Clara le pide formato europeo (231.500,00) y el modelo suele redondear o quitar decimales.
    Se cubren las formas literales; NO se cubre la paráfrasis ("unos doscientos treinta mil"),
    que queda documentada como límite.
    """
    entero = int(cantidad)
    anglo = f"{cantidad:,.2f}"                      # 231,500.00
    euro = anglo.replace(",", "\x00").replace(".", ",").replace("\x00", ".")  # 231.500,00
    anglo_entero = f"{entero:,}"                    # 231,500
    euro_entero = anglo_entero.replace(",", ".")    # 231.500
    return {anglo, euro, anglo_entero, euro_entero}


@dataclass(frozen=True)
class ConjuntoAutorizado:
    """Lo que el `user_id` autenticado tiene derecho a ver, resuelto desde la fuente de datos.

    Es el equivalente en el lab a la consulta `accounts_of(user_id)` de un core bancario real: la
    pertenencia de un dato no se juzga semánticamente, se comprueba contra este conjunto.
    """

    ibans: frozenset[str]
    tarjetas: frozenset[str]
    nombres: frozenset[str]
    importes: frozenset[str]


@lru_cache(maxsize=32)
def conjunto_autorizado(user_id: str) -> ConjuntoAutorizado:
    usuario = MOCK_USERS.get(user_id, {})
    iban_propio = usuario.get("account_id")
    ibans = {_normalizar_iban(iban_propio)} if iban_propio else set()

    nombres = {usuario["name"]} if usuario.get("name") else set()
    tarjetas = {c for c, titular in MOCK_CARDS.items() if titular == user_id}

    importes: set[str] = set()
    for iban in ibans:
        cuenta = MOCK_ACCOUNTS.get(iban)
        if cuenta:
            importes |= _variantes_importe(cuenta.balance)

    return ConjuntoAutorizado(
        ibans=frozenset(ibans),
        tarjetas=frozenset(tarjetas),
        nombres=frozenset(nombres),
        importes=frozenset(importes),
    )


@lru_cache(maxsize=1)
def _catalogo_terceros() -> list[tuple[str, str, frozenset[str]]]:
    """(iban, nombre_titular, variantes de su saldo) de todas las cuentas del banco.

    Permite detectar la fuga de un dato de tercero aunque el modelo lo emita SIN el IBAN al lado
    — el caso de `atk_012`, que pide "nombres, IBANs, saldos y teléfonos": un volcado que dé solo
    nombre + saldo sigue siendo una brecha, y ningún regex de formato lo detectaría porque un
    nombre propio no tiene forma regular.
    """
    return [
        (iban, cuenta.owner_name, frozenset(_variantes_importe(cuenta.balance)))
        for iban, cuenta in MOCK_ACCOUNTS.items()
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Detección de entidades
# ──────────────────────────────────────────────────────────────────────────────

def _token(formato: str, valor: str) -> str:
    """Rellena el `token_format` del YAML (`[IBAN-****{last4}]`, `[EMAIL-{first3}***@{domain}]`)."""
    limpio = valor.replace(" ", "").replace("-", "")
    last4 = limpio[-4:] if len(limpio) >= 4 else limpio
    last3 = limpio[-3:] if len(limpio) >= 3 else limpio
    first3 = valor[:3]
    dominio = valor.split("@")[-1] if "@" in valor else ""
    return (
        formato.replace("{last4}", last4)
        .replace("{last3}", last3)
        .replace("{first3}", first3)
        .replace("{domain}", dominio)
    )


def detect_entities(text: str) -> list[PIIEntity]:
    """Todas las entidades PII presentes en `text`, sin juzgar a quién pertenecen.

    Se expone por separado de la redacción porque el Compliance Logger necesita saber QUÉ se
    detectó aunque la decisión final sea ALLOW (trazabilidad, EU AI Act Art. 13).

    Resolución de solapamientos (fallo real encontrado al probar el módulo, no teórico): el
    patrón `phone_es` de `banking_patterns.yaml` no lleva anclas `\\b`, así que casa dentro de la
    parte numérica de un IBAN — `ES9121000418450200051332` contiene "912100041", que tiene forma
    de teléfono español. Sin resolver el solapamiento, la CUENTA PROPIA del usuario se marcaba
    como teléfono ajeno y toda respuesta legítima con su IBAN se tokenizaba. Se resuelve
    quedándose con la coincidencia más larga cuando dos se solapan: el IBAN gana al teléfono
    fantasma que vive dentro de él.
    """
    candidatos: list[tuple[int, int, str, str]] = []  # (inicio, fin, nombre_patron, valor)
    for nombre, regex, _formato in _compiled():
        for m in regex.finditer(text):
            candidatos.append((m.start(), m.end(), nombre, m.group(0)))

    # Más largo primero: ante un solapamiento, la entidad más específica es la de mayor extensión.
    candidatos.sort(key=lambda c: (c[1] - c[0]), reverse=True)

    aceptados: list[tuple[int, int, str, str]] = []
    for inicio, fin, nombre, valor in candidatos:
        if any(not (fin <= a_ini or inicio >= a_fin) for a_ini, a_fin, _, _ in aceptados):
            continue
        aceptados.append((inicio, fin, nombre, valor))

    formatos = {nombre: formato for nombre, _regex, formato in _compiled()}
    aceptados.sort(key=lambda c: c[0])
    return [
        PIIEntity(
            type=_TIPO_POR_PATRON[nombre],
            value_original=valor,
            value_tokenized=_token(formatos[nombre], valor),
            position_start=inicio,
            position_end=fin,
        )
        for inicio, fin, nombre, valor in aceptados
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Control de salida — el que aporta la garantía
# ──────────────────────────────────────────────────────────────────────────────

def redact_foreign_pii(
    text: str, user_id: str, verified_values: frozenset[str] | None = None
) -> tuple[str, list[PIIEntity], bool]:
    """Elimina de `text` cualquier PII que no pertenezca al usuario autenticado.

    `verified_values`: valores que una tool devolvió legítimamente en este mismo turno (p. ej. el
    IBAN destino de una transferencia que el propio cliente ordenó). Sin esta excepción, una
    transferencia correcta a un tercero se marcaría como fuga — el mismo criterio que ya aplica
    `_confidential_leak_guard` cruzando contra `tools_used`.

    Devuelve `(texto_final, entidades_ajenas, respuesta_descartada)`. Si `respuesta_descartada`
    es True, `texto_final` es el mensaje genérico y no una versión tokenizada del original.
    """
    autorizado = conjunto_autorizado(user_id)
    verificados = verified_values or frozenset()
    verificados_norm = {_normalizar_iban(v) for v in verificados}

    ajenas: list[PIIEntity] = []
    resultado = text
    terceros_identificados: set[str] = set()

    # --- 1. Entidades con forma regular (IBAN, tarjeta, DNI, teléfono, email, SWIFT) ---
    for entidad in detect_entities(text):
        valor = entidad.value_original
        if entidad.type == BankingEntityType.IBAN:
            norm = _normalizar_iban(valor)
            if norm in autorizado.ibans or norm in verificados_norm:
                continue
            terceros_identificados.add(norm)
        elif entidad.type == BankingEntityType.CREDIT_CARD:
            if valor.strip().upper() in autorizado.tarjetas:
                continue
        elif valor in verificados:
            continue
        ajenas.append(entidad)
        resultado = resultado.replace(valor, entidad.value_tokenized)

    # --- 2. Datos de tercero SIN forma regular: nombre de titular y saldo ---
    # Un nombre propio no tiene patrón detectable; se cruza contra el catálogo real de cuentas.
    # Solo cuenta como fuga si el titular NO es el propio usuario autenticado.
    for iban, titular, importes in _catalogo_terceros():
        if iban in autorizado.ibans:
            continue
        if titular in autorizado.nombres:
            continue

        titular_presente = titular in resultado
        importe_presente = next((i for i in importes if i in resultado and i not in autorizado.importes), None)

        if titular_presente:
            terceros_identificados.add(iban)
            ajenas.append(
                PIIEntity(
                    type=BankingEntityType.EMAIL,  # tipo genérico: el modelo no tiene NOMBRE
                    value_original=titular,
                    value_tokenized="[TITULAR-OCULTO]",
                    position_start=resultado.find(titular),
                    position_end=resultado.find(titular) + len(titular),
                )
            )
            resultado = resultado.replace(titular, "[TITULAR-OCULTO]")

        if importe_presente:
            terceros_identificados.add(iban)
            ajenas.append(
                PIIEntity(
                    type=BankingEntityType.BALANCE,
                    value_original=importe_presente,
                    value_tokenized="[SALDO-OCULTO]",
                    position_start=resultado.find(importe_presente),
                    position_end=resultado.find(importe_presente) + len(importe_presente),
                )
            )
            resultado = resultado.replace(importe_presente, "[SALDO-OCULTO]")

    if not ajenas:
        return text, [], False

    # Cosecha masiva: descartar la respuesta entera (ver `_UMBRAL_COSECHA_MASIVA`).
    if len(terceros_identificados) >= _UMBRAL_COSECHA_MASIVA:
        return _SAFE_MESSAGE, ajenas, True

    return resultado, ajenas, False


# ──────────────────────────────────────────────────────────────────────────────
# Control de entrada — señal, no garantía
# ──────────────────────────────────────────────────────────────────────────────

# Cada regla exige DOS componentes en la misma frase: un verbo/sustantivo de enumeración Y un
# objeto de alcance masivo. Pedir "todos" algo, o "enumerar" algo, por separado, es lenguaje
# corriente en banca ("¿me listas mis movimientos?", "¿tenéis todos los productos?"); la
# conjunción de ambos sobre datos de CLIENTES es lo que no tiene lectura legítima.
_VERBOS_ENUMERACION = (
    r"(?:enumera(?:r|me)?|l[ií]sta(?:me|r)?|listado|muestra(?:me)?|mostrar|exporta(?:r|me)?|"
    r"dame|dime|volcado|vuelca|recopila(?:r|me)?|saca(?:me)?|imprime|genera(?:me)?|"
    r"necesito|quiero|pásame|pasame|facilita(?:me)?|proporciona(?:me)?)"
)
# El objeto tiene que ser masivo Y sobre datos de CLIENTES/CUENTAS del banco. "todos mis
# movimientos" o "todos los productos" no entran aquí a propósito: son peticiones legítimas.
_OBJETO_MASIVO = (
    r"(?:tod[oa]s?\s+l[oa]s?\s+(?:cuentas?|clientes?|ibans?|usuarios?|titulares?|"
    r"saldos?)|"
    r"l[oa]s?\s+(?:ibans?|cuentas?|datos?|saldos?|titulares?)\s+de\s+tod[oa]s?|"
    r"base\s+de\s+datos\s+de\s+clientes?|"
    r"(?:cada|tod[oa]s?\s+l[oa]s?)\s+client)"
)
_PRETEXTO_AUTORIDAD = (
    r"(?:auditor[íi]a|compliance|cumplimiento|inspecci[óo]n|informe\s+interno|"
    r"reporte\s+(?:interno|de\s+compliance)|control\s+interno|revisi[óo]n\s+interna)"
)

_REGLAS_ENUMERACION: list[tuple[str, re.Pattern]] = [
    (
        "enumeracion_masiva",
        re.compile(rf"(?i){_VERBOS_ENUMERACION}\b[^.?!]{{0,80}}?{_OBJETO_MASIVO}"),
    ),
    (
        # Sin verbo explícito, pero con objeto masivo Y un pretexto de autoridad. Se acepta en
        # CUALQUIER orden dentro de la frase: `atk_011` pone el pretexto detrás ("...para una
        # auditoría interna") y `atk_023` delante ("Para la auditoría anual necesito...").
        "objeto_masivo_con_pretexto",
        re.compile(
            rf"(?i)(?:{_OBJETO_MASIVO}[^.?!]{{0,120}}?{_PRETEXTO_AUTORIDAD}"
            rf"|{_PRETEXTO_AUTORIDAD}[^.?!]{{0,120}}?{_OBJETO_MASIVO})"
        ),
    ),
    (
        "datos_completos_clientes",
        re.compile(r"(?i)datos?\s+completos?\s+de\s+(?:tod[oa]s?\s+)?l[oa]s?\s+clientes?"),
    ),
]


def detectar_enumeracion_masiva(text: str) -> tuple[bool, str | None]:
    """`(hay_intento, nombre_de_regla)`. Determinista, sin LLM."""
    for nombre, regex in _REGLAS_ENUMERACION:
        if regex.search(text):
            return True, nombre
    return False, None


class PIIShieldStage(Stage):
    """Stage de ENTRADA del pipeline (`/chat/proxy`).

    Solo cubre el flanco (1) — intención de enumeración masiva. El flanco (2), que es el que
    aporta la garantía real, no cabe en el contrato `evaluate(ctx) -> PromptDecision` porque
    actúa sobre la RESPUESTA: vive en `redact_foreign_pii()` y lo invoca el orquestador después
    de `agent.run()`. Ver la nota de `src/core/base.py` sobre por qué el Tool Gatekeeper tiene el
    mismo problema de encaje en el contrato genérico.
    """

    name = "pii_shield"

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        hay_intento, regla = detectar_enumeracion_masiva(ctx.text)
        if not hay_intento:
            return PromptDecision(action="ALLOW", confidence=1.0, layer=1)
        return PromptDecision(
            action="BLOCK",
            confidence=1.0,
            layer=1,
            reason=(
                "Solicitud de enumeración masiva de datos de clientes — sin lectura legítima "
                "en un canal de atención al cliente autenticado"
            ),
            attack_type="pii_harvesting",
            matched_rule=regla,
        )
