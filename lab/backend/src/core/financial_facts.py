"""Hechos financieros con evidencia: ninguna cifra sin una lectura autorizada detrás.

P25: las defensas de salida buscan secretos o valores catalogados. Una cifra
**inventada** no coincide con ningún catálogo y llega al cliente. En `atk_044`, el
modelo repite el IBAN que el atacante aportó y le asigna un saldo sin que ninguna
lectura autorizada respalde esa combinación. El evaluador lo trataba como posible fuga
por coincidencia textual, cuando el problema principal era falsedad con apariencia
bancaria.

Un `FinancialFact` nace del servicio de dominio y lleva su `evidence_call_id`. El
verificador comprueba tres cosas a la vez:

    ¿existe un hecho autorizado para ESE recurso?
    ¿pertenece al MISMO principal?
    ¿el valor entregado coincide con el del hecho?

Si falta cualquiera, la afirmación es una alucinación, no una fuga — y se informa como
tal, que es una clase de problema distinta con otro dueño.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

FINANCIAL_FACT_SCHEMA_VERSION = 1

#: Un hecho deja de ser utilizable pasado este tiempo: un saldo de hace una hora no
#: respalda una afirmación en presente.
DEFAULT_FRESHNESS_SECONDS = 300


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class FactType(_Str):
    BALANCE = "BALANCE"
    OWNER = "OWNER"
    ACCOUNT_STATUS = "ACCOUNT_STATUS"
    TRANSACTION = "TRANSACTION"
    CARD_STATUS = "CARD_STATUS"


class ClaimVerdict(_Str):
    """Qué respalda —o no— una afirmación financiera de la respuesta."""

    #: Hay un hecho autorizado, vigente y del mismo principal que la sostiene.
    SUPPORTED = "SUPPORTED"
    #: No existe ningún hecho para ese recurso: el modelo se lo inventó.
    HALLUCINATED = "HALLUCINATED"
    #: Existe un hecho, pero el valor entregado no coincide.
    CONTRADICTED = "CONTRADICTED"
    #: El hecho existe y pertenece a otro sujeto: eso sí es una fuga.
    UNAUTHORIZED = "UNAUTHORIZED"
    #: El hecho existe pero caducó.
    STALE = "STALE"


@dataclass(frozen=True)
class FinancialFact:
    """Dato financiero emitido por el dominio, con su evidencia."""

    fact_type: FactType
    resource_ref: str
    value: str
    subject: str
    evidence_call_id: str
    as_of: float
    currency: str | None = None
    schema_version: int = FINANCIAL_FACT_SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "fact_type": str(self.fact_type),
            "resource_ref": self.resource_ref,
            "value": self.value,
            "subject": self.subject,
            "evidence_call_id": self.evidence_call_id,
            "as_of": self.as_of,
            "currency": self.currency,
        }


def _normalize_amount(value: str) -> str:
    """Solo dígitos: el separador decimal y el de millares se escriben al revés según
    la locale y no distinguen el valor."""
    return re.sub(r"[^\d]", "", str(value))


def _normalize_iban(value: str) -> str:
    return re.sub(r"[\s-]", "", str(value)).upper()


def facts_from_tool_results(tools: list[dict], *, subject: str) -> list[FinancialFact]:
    """Extrae los hechos que las tools autorizadas devolvieron en este turno.

    Solo cuentan las invocaciones con recibo del dominio: un resultado que se declara
    consumado sin comprobante no respalda ninguna afirmación.
    """
    from src.models.tool_invocation import effect_observed, has_legacy_effect_evidence  # noqa: PLC0415

    hechos: list[FinancialFact] = []
    for call in tools or []:
        resultado = call.get("result")
        if not isinstance(resultado, dict) or not resultado:
            continue
        if not (effect_observed(resultado) or has_legacy_effect_evidence(resultado)):
            continue
        recibo = resultado.get("effect_receipt") or {}
        actor = recibo.get("actor_subject") or subject
        call_id = str(resultado.get("invocation_id") or call.get("tool_call_id") or "")
        ahora = datetime.now(timezone.utc).timestamp()
        cuenta = resultado.get("account_id")

        if cuenta and (resultado.get("balance") or resultado.get("available_balance")):
            hechos.append(FinancialFact(
                fact_type=FactType.BALANCE,
                resource_ref=_normalize_iban(cuenta),
                value=str(resultado.get("balance") or resultado.get("available_balance")),
                subject=actor, evidence_call_id=call_id, as_of=ahora,
                currency=resultado.get("currency"),
            ))
        if cuenta and resultado.get("owner"):
            hechos.append(FinancialFact(
                fact_type=FactType.OWNER, resource_ref=_normalize_iban(cuenta),
                value=str(resultado["owner"]), subject=actor,
                evidence_call_id=call_id, as_of=ahora,
            ))
        if resultado.get("card_id") and resultado.get("card_status"):
            hechos.append(FinancialFact(
                fact_type=FactType.CARD_STATUS,
                resource_ref=str(resultado["card_id"]).upper(),
                value=str(resultado["card_status"]), subject=actor,
                evidence_call_id=call_id, as_of=ahora,
            ))
        if resultado.get("transaction_id"):
            hechos.append(FinancialFact(
                fact_type=FactType.TRANSACTION,
                resource_ref=str(resultado["transaction_id"]),
                value=str(resultado.get("amount", "")), subject=actor,
                evidence_call_id=call_id, as_of=ahora,
            ))
    return hechos


@dataclass
class ClaimAssessment:
    """Veredicto de una afirmación concreta de la respuesta."""

    fact_type: FactType
    resource_ref: str
    claimed_value: str
    verdict: ClaimVerdict
    evidence_call_id: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict:
        return {
            "fact_type": str(self.fact_type),
            "resource_ref": self.resource_ref,
            "claimed_value": self.claimed_value,
            "verdict": str(self.verdict),
            "evidence_call_id": self.evidence_call_id,
            "detail": self.detail,
        }


#: IBAN estricto: compacto o agrupado de cuatro en cuatro, siempre en mayúsculas. Sin
#: esta forma el patrón se comía la palabra siguiente ("…1334 TIENE 231").
IBAN_PATTERN = r"\b[A-Z]{2}\d{2}(?:[A-Z0-9]{10,30}|(?:\s[A-Z0-9]{4}){3,8})\b"

_BALANCE_CLAIM_RE = re.compile(
    rf"(?P<iban>{IBAN_PATTERN})"
    r"(?P<between>(?:(?!" + IBAN_PATTERN + r").){0,120}?)"
    r"(?P<amount>\d[\d.,]*)\s*(?:€|EUR|eur)",
    re.DOTALL,
)


def extract_balance_claims(response: str) -> list[tuple[str, str]]:
    """Pares (IBAN, importe) que la respuesta afirma. Es el claim de `atk_044`."""
    return [
        (_normalize_iban(m.group("iban")), m.group("amount"))
        for m in _BALANCE_CLAIM_RE.finditer(response or "")
    ]


def verify_claims(
    response: str,
    *,
    facts: list[FinancialFact],
    subject: str,
    freshness_seconds: int = DEFAULT_FRESHNESS_SECONDS,
    now: float | None = None,
) -> list[ClaimAssessment]:
    """Comprueba cada afirmación de saldo contra los hechos autorizados del turno."""
    ahora = now if now is not None else datetime.now(timezone.utc).timestamp()
    por_recurso = {
        f.resource_ref: f for f in facts if f.fact_type == FactType.BALANCE
    }
    evaluaciones: list[ClaimAssessment] = []

    for iban, importe in extract_balance_claims(response):
        hecho = por_recurso.get(iban)
        if hecho is None:
            evaluaciones.append(ClaimAssessment(
                FactType.BALANCE, iban, importe, ClaimVerdict.HALLUCINATED,
                detail="ninguna lectura autorizada respalda un saldo para esa cuenta",
            ))
            continue
        if hecho.subject != subject:
            evaluaciones.append(ClaimAssessment(
                FactType.BALANCE, iban, importe, ClaimVerdict.UNAUTHORIZED,
                evidence_call_id=hecho.evidence_call_id,
                detail=f"el hecho pertenece a {hecho.subject}",
            ))
            continue
        if ahora - hecho.as_of > freshness_seconds:
            evaluaciones.append(ClaimAssessment(
                FactType.BALANCE, iban, importe, ClaimVerdict.STALE,
                evidence_call_id=hecho.evidence_call_id,
                detail="la evidencia caducó",
            ))
            continue
        if _normalize_amount(importe) != _normalize_amount(hecho.value):
            evaluaciones.append(ClaimAssessment(
                FactType.BALANCE, iban, importe, ClaimVerdict.CONTRADICTED,
                evidence_call_id=hecho.evidence_call_id,
                detail=f"la evidencia dice {hecho.value}",
            ))
            continue
        evaluaciones.append(ClaimAssessment(
            FactType.BALANCE, iban, importe, ClaimVerdict.SUPPORTED,
            evidence_call_id=hecho.evidence_call_id,
        ))
    return evaluaciones


# ── Composición segura ───────────────────────────────────────────────────────

UNVERIFIABLE_MESSAGE = (
    "No he podido verificar ese dato con una consulta autorizada, así que no voy a "
    "darte una cifra. Puedes consultarlo en la app, en Cuentas, o pedirme el resumen "
    "de tu cuenta."
)


@dataclass
class CompositionResult:
    response: str
    replaced: bool = False
    assessments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "replaced": self.replaced,
            "assessments": self.assessments,
        }


def compose_safe_response(
    response: str, *, facts: list[FinancialFact], subject: str,
    freshness_seconds: int = DEFAULT_FRESHNESS_SECONDS, now: float | None = None,
) -> CompositionResult:
    """Sustituye la respuesta si contiene una afirmación financiera sin respaldo.

    No se corrige el número ni se pide a otro modelo que lo arregle: se explica que no
    pudo verificarse y se indica el siguiente paso. Inventar una cifra bancaria es un
    problema de integridad, y taparlo con otra generación no lo resuelve.
    """
    evaluaciones = verify_claims(
        response, facts=facts, subject=subject,
        freshness_seconds=freshness_seconds, now=now,
    )
    sin_respaldo = [e for e in evaluaciones if e.verdict != ClaimVerdict.SUPPORTED]
    if not sin_respaldo:
        return CompositionResult(response, False, [e.to_dict() for e in evaluaciones])
    return CompositionResult(
        UNVERIFIABLE_MESSAGE, True, [e.to_dict() for e in evaluaciones],
    )
