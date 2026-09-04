"""Procedencia de los argumentos: de dónde salió cada valor de la llamada.

P24: el Gatekeeper valida los argumentos FINALES. Si el atacante pide transferir desde
un IBAN ajeno y el modelo omite `from_account`, el backend rellena la cuenta propia del
usuario porque es un default cómodo. El control de propiedad comprueba que esa cuenta sí
es de la víctima… y autoriza. La intención prohibida se convirtió en una operación
válida pero distinta: el agente actuando de confused deputy.

Aquí se conserva, por argumento:

    requested   lo que emitió el modelo
    source      de dónde procede el valor (input directo, documento, contexto…)
    resolved    lo que puso el backend, y por qué

Un valor sensible que el mensaje declaraba explícitamente y la propuesta omite o cambia
produce `ARGUMENT_PROVENANCE_MISMATCH`. Ahí no se aplica un default: se pide aclaración.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum

PROVENANCE_SCHEMA_VERSION = 1


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class ArgumentSource(_Str):
    """De dónde salió el valor. No todas las fuentes autorizan una acción."""

    #: Escrito por el usuario autenticado en su mensaje.
    USER_INPUT = "USER_INPUT"
    #: Texto citado dentro del mensaje (comillas, bloque pegado).
    QUOTED_CONTENT = "QUOTED_CONTENT"
    #: Documento adjunto. Dato no confiable, nunca una orden.
    UNTRUSTED_DOCUMENT = "UNTRUSTED_DOCUMENT"
    #: Contexto inyectado por el backend.
    TRUSTED_CONTEXT = "TRUSTED_CONTEXT"
    #: Resultado de una tool previa.
    TOOL_RESULT = "TOOL_RESULT"
    #: Resuelto por el backend desde el canal autenticado.
    BACKEND_RESOLVED = "BACKEND_RESOLVED"
    #: El modelo lo compuso sin respaldo en ninguna fuente.
    MODEL_GENERATED = "MODEL_GENERATED"


#: Fuentes que NO pueden originar por sí solas una acción con efecto. Un documento
#: adjunto o un texto citado son datos; convertirlos en orden es la inyección indirecta.
UNAUTHORIZED_SOURCES = (ArgumentSource.UNTRUSTED_DOCUMENT, ArgumentSource.QUOTED_CONTENT)

#: Campos donde un default silencioso cambia el significado de la operación.
SENSITIVE_FIELDS = ("from_account", "to_account", "card_id", "amount", "account_id")

_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9 ]{10,34}\b", re.IGNORECASE)
_QUOTED_RE = re.compile(r"[\"«»“”']([^\"«»“”']{10,})[\"«»“”']")


def _normalize_iban(value: str) -> str:
    return re.sub(r"[\s-]", "", str(value)).upper()


@dataclass(frozen=True)
class ArgumentProvenance:
    """Origen de un argumento concreto, reproducible desde el artefacto."""

    field: str
    value: str | None
    source: ArgumentSource
    artifact_id: str | None = None
    artifact_hash: str | None = None
    extractor: str = "deterministic.v1"
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": PROVENANCE_SCHEMA_VERSION,
            "field": self.field,
            "value": self.value,
            "source": str(self.source),
            "artifact_id": self.artifact_id,
            "artifact_hash": self.artifact_hash,
            "extractor": self.extractor,
            "reason": self.reason,
        }


@dataclass
class InputArtifacts:
    """Los textos de los que puede proceder un argumento, cada uno con su naturaleza."""

    user_input: str = ""
    documents: str = ""
    trusted_context: str = ""
    tool_results: str = ""

    def _hash(self, texto: str) -> str:
        return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]

    def quoted_spans(self) -> list[str]:
        return [m.group(1) for m in _QUOTED_RE.finditer(self.user_input)]

    def source_of(self, value: str) -> tuple[ArgumentSource, str | None, str | None]:
        """Primera fuente que contiene el valor, en orden de menor confianza a mayor.

        El documento va primero a propósito: si el valor aparece en un adjunto, el hecho
        de que también esté en el mensaje no lo vuelve una orden del usuario.
        """
        objetivo = _normalize_iban(value) if _IBAN_RE.match(str(value)) else str(value).strip()

        def _contiene(texto: str) -> bool:
            if not texto:
                return False
            if _IBAN_RE.match(str(value)):
                return objetivo in _normalize_iban(texto)
            return objetivo.casefold() in texto.casefold()

        if _contiene(self.documents):
            return ArgumentSource.UNTRUSTED_DOCUMENT, "document", self._hash(self.documents)
        for cita in self.quoted_spans():
            if _contiene(cita):
                return ArgumentSource.QUOTED_CONTENT, "quote", self._hash(cita)
        if _contiene(self.user_input):
            return ArgumentSource.USER_INPUT, "user_input", self._hash(self.user_input)
        if _contiene(self.tool_results):
            return ArgumentSource.TOOL_RESULT, "tool_results", self._hash(self.tool_results)
        if _contiene(self.trusted_context):
            return ArgumentSource.TRUSTED_CONTEXT, "context", self._hash(self.trusted_context)
        return ArgumentSource.MODEL_GENERATED, None, None

    def explicit_ibans(self) -> list[str]:
        """IBANes que el usuario escribió directamente, fuera de citas y documentos."""
        citas = " ".join(self.quoted_spans())
        return [
            _normalize_iban(m.group(0))
            for m in _IBAN_RE.finditer(self.user_input)
            if _normalize_iban(m.group(0)) not in _normalize_iban(citas + self.documents)
        ]


@dataclass
class ProvenanceFinding:
    code: str
    field: str
    message: str
    requires_clarification: bool = False

    def to_dict(self) -> dict:
        return {
            "code": self.code, "field": self.field, "message": self.message,
            "requires_clarification": self.requires_clarification,
        }


@dataclass
class ProvenanceReport:
    arguments: list[ArgumentProvenance] = field(default_factory=list)
    findings: list[ProvenanceFinding] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.findings)

    def to_dict(self) -> dict:
        return {
            "arguments": [a.to_dict() for a in self.arguments],
            "findings": [f.to_dict() for f in self.findings],
            "blocked": self.blocked,
        }


def analyze(
    *,
    tool: str,
    requested_arguments: dict,
    resolved_attributes: dict,
    artifacts: InputArtifacts,
    sensitive_fields: tuple[str, ...] = SENSITIVE_FIELDS,
) -> ProvenanceReport:
    """Comprueba que la propuesta conserve la intención del mensaje original.

    Tres cosas que el control de argumentos finales no puede ver:

    1. un campo sensible que el usuario declaró y la propuesta **omite** —el default
       silencioso cambia la operación—;
    2. un valor que **contradice** el que el usuario escribió;
    3. un valor cuyo origen es un documento o una cita, que son datos, no órdenes.
    """
    reporte = ProvenanceReport()

    for campo, valor in requested_arguments.items():
        if valor in (None, ""):
            continue
        fuente, artefacto, huella = artifacts.source_of(str(valor))
        reporte.arguments.append(ArgumentProvenance(
            field=campo, value=str(valor), source=fuente,
            artifact_id=artefacto, artifact_hash=huella,
        ))
        if campo in sensitive_fields and fuente in UNAUTHORIZED_SOURCES:
            reporte.findings.append(ProvenanceFinding(
                "UNAUTHORIZED_ARGUMENT_SOURCE", campo,
                (f"`{campo}` procede de {fuente}: un documento adjunto o un texto citado "
                 "son datos, no una orden del usuario autenticado"),
                requires_clarification=True,
            ))

    for campo, valor in resolved_attributes.items():
        reporte.arguments.append(ArgumentProvenance(
            field=campo, value=str(valor), source=ArgumentSource.BACKEND_RESOLVED,
            reason="resuelto desde el canal de autenticación",
        ))

    # El caso del confused deputy: el mensaje declaraba un origen explícito y la
    # propuesta lo omitió, así que el backend puso la cuenta de la víctima.
    ibans_explicitos = artifacts.explicit_ibans()
    for campo in ("from_account", "account_id"):
        if campo not in sensitive_fields:
            continue
        pedido = requested_arguments.get(campo)
        resuelto = resolved_attributes.get(campo)
        if pedido in (None, "") and resuelto and ibans_explicitos:
            declarados = [
                iban for iban in ibans_explicitos if iban != _normalize_iban(str(resuelto))
            ]
            if declarados:
                reporte.findings.append(ProvenanceFinding(
                    "ARGUMENT_PROVENANCE_MISMATCH", campo,
                    (f"el mensaje declara {declarados} como origen y la propuesta omite "
                     f"`{campo}`: no se aplica un default sobre un campo sensible"),
                    requires_clarification=True,
                ))
        elif pedido and resuelto and _normalize_iban(str(pedido)) != _normalize_iban(str(resuelto)):
            reporte.findings.append(ProvenanceFinding(
                "ARGUMENT_SILENTLY_REPLACED", campo,
                (f"`{campo}` solicitado ({pedido}) y resuelto ({resuelto}) difieren: la "
                 "sustitución no puede ser silenciosa"),
                requires_clarification=True,
            ))

    return reporte
