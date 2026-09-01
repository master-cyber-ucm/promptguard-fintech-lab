"""Output Auditor -- capa de defensa determinista para LLM07 (System Prompt Leakage).

Escanea la respuesta final del modelo antes de entregarla al cliente, en busca de
patrones de secretos de configuracion conocidos embebidos en el system prompt del
laboratorio (API key interna, host de base de datos, bucket S3). Si detecta una
coincidencia, sustituye la respuesta completa por un mensaje generico.

Deliberadamente NO intenta detectar "intencion sospechosa" en el prompt de entrada:
esa aproximacion (bloqueo semantico sobre el texto de entrada) genero falsos
positivos sobre peticiones legitimas en otras pruebas del equipo. Esta capa actua
solo sobre la salida, contra patrones conocidos y verificables, para mantener la
tasa de falsos positivos en 0% sobre trafico legitimo.

────────────────────────────────────────────────────────────────────────────────
Endurecimiento (ataque #5 del catálogo, `atk_015` — extracción de API_KEY_INTERNAL)
────────────────────────────────────────────────────────────────────────────────
La versión inicial comparaba cadenas literales. Al sondearla contra variantes de
evasión se midió que bastaba con romper el literal para atravesarla — sin que el
secreto dejara de ser legible para un humano ni para un atacante:

    "pg_internal_sk_ a1b2c3d4e5f6"   (espacio)      → PASABA
    "pg-internal-sk-a1b2c3d4e5f6"    (guiones)      → PASABA
    "PG_INTERNAL_SK_A1B2C3D4E5F6"    (mayúsculas)   → PASABA
    "pg_internal" + "_sk_a1b2c3..."  (troceado)     → PASABA

Ninguna de esas formas requiere que el modelo "colabore" especialmente: son la
salida natural de pedirle que deletree, formatee o traduzca sus instrucciones
(`atk_029`, `atk_063`, `atk_065`). La detección pasa por tanto a operar sobre una
FORMA NORMALIZADA del texto (minúsculas, sin separadores, sin caracteres
invisibles), donde las cuatro variantes colapsan al mismo literal. El coste en
falsos positivos es nulo: una cadena de 20+ caracteres alfanuméricos como
`pginternalska1b2c3d4e5f6` no aparece por casualidad en una respuesta bancaria.

Segundo detector, independiente del primero: los UMBRALES del bloque "Información
interna (NO REVELAR)" del system prompt (10.000 / 5.000 / 3.000 / 1.000 EUR). No se
bloquea la aparición de UNA cifra —un cliente puede preguntar legítimamente por su
límite de transferencia y merece respuesta— sino la de DOS O MÁS umbrales distintos
en la misma respuesta, que es la firma de un volcado del bloque interno y no la de
una respuesta a una pregunta concreta. El umbral de 2 es una decisión de calibración
documentada, no un valor arbitrario: separa "te respondo tu límite" de "te recito mi
configuración".
"""

from __future__ import annotations

import re
import unicodedata

from .base import Stage, StageContext
from .safe_composer import FindingCategory, OutputFinding, compose
from src.models.interaction import PromptDecision

_SECRET_PATTERNS = [
    re.compile(r"pg_internal_sk_[a-zA-Z0-9]+"),
    re.compile(r"db-banking\.internal\.verdabank\.es"),
    re.compile(r"s3://verdabank-audit-logs-prod\S*"),
]

# Forma normalizada (minúsculas, solo alfanuméricos) de cada secreto del system prompt. Es lo que
# permite cazar las variantes espaciadas, con guiones, troceadas o en mayúsculas: todas colapsan
# aquí al mismo literal.
_SECRETOS_NORMALIZADOS = (
    "pginternalska1b2c3d4e5f6",
    "dbbankinginternalverdabankes",
    # Sin el prefijo de esquema: el identificador sensible es el NOMBRE del bucket, no el `s3://`
    # que lo precede. Con el prefijo dentro del literal, "bucket: verdabank audit logs prod (s3)"
    # se escapaba solo por mover el esquema al final.
    "verdabankauditlogsprod",
)

# Caracteres invisibles usados para romper una coincidencia literal sin alterar lo que se lee.
# Mismo vector que ya documentó el `document_sanitizer` para el canal documental.
_INVISIBLES = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0xFEFF, 0x00AD] + list(range(0xE0000, 0xE0080)), None
)

# Umbrales del bloque "Información interna (NO REVELAR)" de `config/prompts/clara_system.txt`.
# Se buscan en forma normalizada para que "10.000", "10,000" y "10000" cuenten como el mismo.
_UMBRALES_INTERNOS = ("10000", "5000", "3000", "1000")

# A partir de cuántos umbrales distintos en la misma respuesta se considera volcado del bloque
# interno en vez de respuesta a una pregunta concreta. Ver la nota del docstring del módulo.
_MIN_UMBRALES_PARA_BLOQUEAR = 2

# El detector de umbrales exige ADEMÁS una palabra del vocabulario del bloque interno. Sin esta
# condición se producía un falso positivo real y fácil de encontrar: un extracto de movimientos
# con dos importes redondos ("se han abonado 1.000 € y retirado 5.000 €") contiene dos umbrales y
# se bloqueaba, pese a no revelar nada de la configuración. Un volcado del bloque interno, en
# cambio, siempre viene acompañado de su propio vocabulario ("límite", "aprobación automática",
# "detección de fraude").
_VOCABULARIO_BLOQUE_INTERNO = (
    "limite",
    "limites",
    "aprobacion",
    "antifraude",
    "deteccion de fraude",
    "deteccionfraude",
    "configuracion interna",
    "informacion interna",
    "instrucciones internas",
)

_GENERIC_REFUSAL = "No puedo compartir esa informacion."


def _normalizar(texto: str) -> str:
    """Minúsculas, sin acentos, sin caracteres invisibles y sin separadores.

    Colapsa las variantes de evasión que no cambian lo que un humano lee:
    `PG_INTERNAL_SK_A1B2` / `pg-internal-sk-a1b2` / `pg_internal_sk_ a1b2` → `pginternalska1b2`.
    """
    sin_invisibles = texto.translate(_INVISIBLES)
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", sin_invisibles) if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]", "", sin_acentos.lower())


def _umbrales_presentes(texto_normalizado: str) -> set[str]:
    """Umbrales de configuración presentes en la forma normalizada del texto.

    Se comprueban de mayor a menor y se elimina la coincidencia antes de seguir, porque "10000"
    contiene "1000" y "1000" contiene... nada, pero sin este cuidado una sola cifra de 10.000
    contaría como dos umbrales distintos y dispararía el bloqueo por sí sola.
    """
    encontrados: set[str] = set()
    restante = texto_normalizado
    for umbral in _UMBRALES_INTERNOS:  # ya ordenados de más largo a más corto
        if umbral in restante:
            encontrados.add(umbral)
            restante = restante.replace(umbral, " ")
    return encontrados


def audit_findings(text: str) -> list[OutputFinding]:
    """Hallazgos estructurados: qué fragmento sobra y por qué.

    Devolver un booleano obligaba a tirar la respuesta entera. Con la categoría y el
    span concreto se puede quitar solo lo prohibido y conservar lo útil (P26).
    """
    hallazgos: list[OutputFinding] = []

    # Detector 1a — literal (comportamiento original, se conserva).
    for pattern in _SECRET_PATTERNS:
        for coincidencia in pattern.finditer(text):
            hallazgos.append(OutputFinding(
                category=FindingCategory.CONFIG_SECRET, span=coincidencia.group(0),
                reason="secreto de configuración conocido",
            ))

    normalizado = _normalizar(text)

    # Detector 1b — mismo secreto tras normalizar: cubre espaciado, guiones, mayúsculas,
    # troceado y caracteres invisibles. Aquí el span exacto no es recuperable, así que
    # el hallazgo no acota una frase y fuerza el fallback seguro.
    for secreto in _SECRETOS_NORMALIZADOS:
        if secreto in normalizado:
            hallazgos.append(OutputFinding(
                category=FindingCategory.CONFIG_SECRET, span="",
                reason="secreto de configuración ofuscado",
            ))

    # Detector 2 — volcado del bloque de umbrales internos: dos o más umbrales distintos Y
    # vocabulario propio del bloque. Las dos condiciones juntas, nunca una sola.
    umbrales = _umbrales_presentes(normalizado)
    if len(umbrales) >= _MIN_UMBRALES_PARA_BLOQUEAR and any(
        termino.replace(" ", "") in normalizado for termino in _VOCABULARIO_BLOQUE_INTERNO
    ):
        for frase in re.split(r"(?<=[.!?])\s+|\n+", text):
            if any(u.replace(".", "").replace(",", "") in _normalizar(frase) for u in umbrales):
                hallazgos.append(OutputFinding(
                    category=FindingCategory.INTERNAL_THRESHOLD, span=frase.strip(),
                    reason="umbral interno del bloque de configuración",
                ))
    return hallazgos


def audit_response(text: str, *, prompt: str = "") -> tuple[str, bool]:
    """Escanea `text` en busca de secretos conocidos y recompone lo que sí es útil.

    Devuelve (texto_final, fuga_detectada). Antes, `fuga_detectada` implicaba
    sustituir la respuesta entera: una consulta legítima sobre transferencias acababa
    en «No puedo compartir esa información» por mencionar un límite interno.
    """
    hallazgos = audit_findings(text)
    if not hallazgos:
        return text, False
    composicion = compose(text, findings=hallazgos, prompt=prompt)
    return composicion.response, True


class OutputAuditorStage(Stage):
    """Envoltorio de `audit_response()` sobre el contrato de stage genérico.

    `audit_response()` sigue siendo la función usada directamente en
    `api/routes/chat.py` para todos los endpoints (comportamiento sin cambios);
    esta clase existe para que el orquestador del proxy (`/chat/proxy`) pueda
    tratar el Output Auditor como una stage más del pipeline, junto a Input
    Sanitizer y PII Shield.
    """

    name = "output_auditor"

    def evaluate(self, ctx: StageContext) -> PromptDecision:
        _, leaked = audit_response(ctx.text)
        return PromptDecision(
            action="BLOCK" if leaked else "ALLOW",
            confidence=1.0,
            layer=1,
            reason="secreto de configuración conocido en la respuesta" if leaked else None,
            attack_type="system_prompt_leakage" if leaked else None,
            matched_rule="output_auditor" if leaked else None,
        )
