"""Composición segura: quitar el dato prohibido no puede significar tirar la respuesta.

P26: cuando una capa detecta contenido sensible sustituye la respuesta ENTERA por una
negativa genérica. El secreto queda oculto y la petición legítima queda sin resolver.
Una consulta sobre cómo hacer una transferencia acababa en «No puedo compartir esa
información» porque, entre los pasos públicos y útiles, la respuesta mencionaba un
límite interno.

La unidad de bloqueo pasa a ser el **hallazgo**, no la respuesta:

    PASS_THROUGH    nada que quitar
    RECOMPOSE       se elimina el fragmento prohibido y se conserva lo útil
    SAFE_FALLBACK   no queda contenido aprovechable: plantilla de la intención
    ESCALATE        la petición no puede atenderse con seguridad en este canal

Un secreto detectado nunca se reinyecta en un LLM para «redactarlo mejor»: la
recomposición es determinista y usa artículos públicos aprobados.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

COMPOSER_SCHEMA_VERSION = 2


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class FindingCategory(_Str):
    CONFIG_SECRET = "CONFIG_SECRET"
    INTERNAL_THRESHOLD = "INTERNAL_THRESHOLD"
    FOREIGN_PII = "FOREIGN_PII"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"


class ComposerAction(_Str):
    PASS_THROUGH = "PASS_THROUGH"
    RECOMPOSE = "RECOMPOSE"
    SAFE_FALLBACK = "SAFE_FALLBACK"
    ESCALATE = "ESCALATE"


class Intent(_Str):
    """Intención legítima detectada. Determina la plantilla pública de respaldo."""

    TRANSFER_HOWTO = "TRANSFER_HOWTO"
    BALANCE_QUERY = "BALANCE_QUERY"
    CARD_BLOCK = "CARD_BLOCK"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class OutputFinding:
    """Hallazgo estructurado. La unidad que se elimina, no la respuesta entera."""

    category: FindingCategory
    span: str
    reason: str
    schema_version: int = COMPOSER_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "category": str(self.category),
            # El span NUNCA se publica: solo su longitud y su categoría.
            "span_length": len(self.span),
            "reason": self.reason,
        }


#: Artículos públicos aprobados. Reemplazan al dato interno explicando el procedimiento
#: sin revelar la regla confidencial.
PUBLIC_ARTICLES: dict[Intent, str] = {
    Intent.TRANSFER_HOWTO: (
        "El límite aplicable se te mostrará antes de confirmar la operación; si "
        "necesitas ampliarlo, contacta con soporte desde la app."
    ),
    Intent.BALANCE_QUERY: (
        "Puedes consultar tu saldo y tus últimos movimientos en la app, en Cuentas."
    ),
    Intent.CARD_BLOCK: (
        "Puedes bloquear tu tarjeta desde la app, en Tarjetas, o llamando al canal de "
        "atención al cliente."
    ),
    Intent.PASSWORD_CHANGE: (
        "Puedes cambiar tu contraseña desde Ajustes › Seguridad, o iniciar la "
        "recuperación desde el canal oficial de acceso."
    ),
}

#: Respuesta cuando no queda contenido aprovechable. Explica el motivo general y el
#: siguiente paso: una negativa sin salida es un fallo de producto, no una defensa.
SAFE_FALLBACKS: dict[Intent, str] = {
    Intent.TRANSFER_HOWTO: (
        "No puedo detallarte eso aquí. Para ordenar una transferencia, abre "
        "Transferencias › Nueva en la app: verás el importe y el beneficiario antes de "
        "confirmar."
    ),
    Intent.BALANCE_QUERY: (
        "No puedo darte ese dato en este canal. Consúltalo en la app, en Cuentas."
    ),
    Intent.CARD_BLOCK: (
        "No puedo completar eso aquí. Bloquea tu tarjeta desde la app, en Tarjetas, o "
        "llamando a atención al cliente."
    ),
    Intent.PASSWORD_CHANGE: (
        "No puedo ayudarte con credenciales por el chat. Cambia tu contraseña desde "
        "Ajustes › Seguridad."
    ),
    Intent.UNKNOWN: (
        "No puedo compartir esa información. Si me dices qué necesitas resolver, te "
        "indico el canal adecuado."
    ),
}

_INTENT_MARKERS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (Intent.TRANSFER_HOWTO, ("transferencia", "transferir", "enviar dinero", "sepa", "bizum")),
    (Intent.CARD_BLOCK, ("tarjeta", "bloquear", "perdid", "robad")),
    (Intent.PASSWORD_CHANGE, ("contraseña", "password", "clave de acceso", "credencial")),
    (Intent.BALANCE_QUERY, ("saldo", "movimientos", "cuánto tengo")),
)


def detect_intent(prompt: str) -> Intent:
    """Intención legítima del usuario, para elegir la plantilla correcta."""
    texto = (prompt or "").casefold()
    for intencion, marcas in _INTENT_MARKERS:
        if any(marca in texto for marca in marcas):
            return intencion
    return Intent.UNKNOWN


_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class Composition:
    """Resultado de la composición, con lo que se conservó y lo que se quitó."""

    response: str
    action: ComposerAction
    intent: Intent = Intent.UNKNOWN
    findings: list[dict] = field(default_factory=list)
    removed_sentences: int = 0

    @property
    def preserved_utility(self) -> bool:
        return self.action in (ComposerAction.PASS_THROUGH, ComposerAction.RECOMPOSE)

    def to_dict(self) -> dict:
        return {
            "schema_version": COMPOSER_SCHEMA_VERSION,
            "action": str(self.action),
            "intent": str(self.intent),
            "findings": self.findings,
            "removed_sentences": self.removed_sentences,
            "preserved_utility": self.preserved_utility,
        }


def compose(
    response: str,
    *,
    findings: list[OutputFinding],
    prompt: str = "",
    min_useful_chars: int = 40,
) -> Composition:
    """Elimina solo las frases con hallazgos y conserva el resto.

    Si al quitarlas no queda una respuesta con contenido suficiente, se usa la
    plantilla pública de la intención: sigue siendo un fallback, pero uno que dice qué
    hacer a continuación.
    """
    intencion = detect_intent(prompt)
    if not findings:
        return Composition(response, ComposerAction.PASS_THROUGH, intencion)

    # Un hallazgo sin span localizable no se puede recortar: el secreto podría estar
    # troceado o deletreado a lo largo de toda la respuesta. Ahí no se recompone nada.
    if any(not hallazgo.span for hallazgo in findings):
        return Composition(
            SAFE_FALLBACKS.get(intencion, SAFE_FALLBACKS[Intent.UNKNOWN]),
            ComposerAction.SAFE_FALLBACK, intencion, [h.to_dict() for h in findings],
        )

    frases = [f for f in _SENTENCE_RE.split(response or "") if f.strip()]
    conservadas = [
        frase for frase in frases
        if not any(hallazgo.span and hallazgo.span in frase for hallazgo in findings)
    ]
    eliminadas = len(frases) - len(conservadas)
    serializados = [h.to_dict() for h in findings]

    texto = " ".join(conservadas).strip()
    if len(texto) >= min_useful_chars:
        articulo = PUBLIC_ARTICLES.get(intencion)
        if articulo:
            # Se explica el procedimiento público en lugar de la regla confidencial.
            texto = f"{texto} {articulo}"
        return Composition(texto, ComposerAction.RECOMPOSE, intencion, serializados, eliminadas)

    return Composition(
        SAFE_FALLBACKS.get(intencion, SAFE_FALLBACKS[Intent.UNKNOWN]),
        ComposerAction.SAFE_FALLBACK, intencion, serializados, eliminadas,
    )
