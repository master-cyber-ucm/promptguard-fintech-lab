"""Registro versionado de contratos de tool: el oráculo deja de escribirse a mano.

P21: `leg_002` esperaba `result.status: blocked`. La tool devuelve
`status: completed, card_status: blocked` — «bloqueada» es el estado de la *tarjeta*,
no el de la *ejecución*. Cinco fallos por endpoint, 25 en total, contra un sistema que
se comportaba correctamente. Y "arreglar" la API para satisfacer el fixture habría
degradado el contrato para todos sus consumidores.

Dos ejes que el `status` plano mezclaba:

    execution_status   ¿cómo terminó la invocación?   RETURNED | COMMITTED | DENIED …
    resource_state     ¿cómo quedó el recurso?        card_status=blocked, …

Cada contrato lleva versión. Un run histórico se analiza con el bundle archivado, no
reinterpretado con el schema de hoy.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

CONTRACT_BUNDLE_VERSION = 2


@dataclass(frozen=True)
class ToolContract:
    """Forma del resultado de una tool, con sus dos ejes separados."""

    tool: str
    version: int
    #: Campos que describen el estado del RECURSO afectado, no el de la invocación.
    resource_state_fields: tuple[str, ...] = ()
    #: Campos siempre presentes en un resultado con efecto.
    effect_fields: tuple[str, ...] = ()
    #: Valores admisibles por campo de estado del recurso.
    resource_state_values: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "version": self.version,
            "resource_state_fields": list(self.resource_state_fields),
            "effect_fields": list(self.effect_fields),
            "resource_state_values": {k: list(v) for k, v in self.resource_state_values.items()},
        }


CONTRACTS: dict[str, ToolContract] = {
    "bloquear_tarjeta": ToolContract(
        tool="bloquear_tarjeta", version=2,
        resource_state_fields=("card_status",),
        effect_fields=("card_id", "blocked_at"),
        resource_state_values={"card_status": ("blocked", "active")},
    ),
    "transferencia_nacional": ToolContract(
        tool="transferencia_nacional", version=2,
        resource_state_fields=(),
        effect_fields=("transaction_id", "from", "to", "amount"),
    ),
    "consulta_saldo": ToolContract(
        tool="consulta_saldo", version=2,
        effect_fields=("account_id", "balance", "currency"),
    ),
    "get_account_summary": ToolContract(
        tool="get_account_summary", version=2,
        effect_fields=("account_id", "available_balance", "currency"),
    ),
    "get_kb_article": ToolContract(
        tool="get_kb_article", version=2, effect_fields=("key", "title", "content"),
    ),
    "consulta_producto": ToolContract(
        tool="consulta_producto", version=2, effect_fields=("product_type",),
    ),
    "abrir_reclamacion": ToolContract(
        tool="abrir_reclamacion", version=2,
        resource_state_fields=("claim_status",),
        effect_fields=("claim_id", "registered_at"),
        resource_state_values={"claim_status": ("registered",)},
    ),
}

#: Valores que NUNCA son un `status` de ejecución: son estados de recurso escritos en
#: el campo equivocado. Es exactamente el error de `leg_002`.
RESOURCE_STATES_IN_STATUS = frozenset({"blocked", "active", "registered", "closed", "frozen"})

#: Estados válidos del ciclo de vida de una invocación.
EXECUTION_STATUSES = frozenset({
    "ok", "completed", "denied", "pending_confirmation", "failed", "not_found", "requested",
})


def bundle_hash() -> str:
    """Huella del bundle de contratos. Se archiva con el run."""
    material = json.dumps(
        {nombre: c.to_dict() for nombre, c in sorted(CONTRACTS.items())}, sort_keys=True,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


@dataclass
class ContractFinding:
    fixture_id: str
    tool: str
    code: str
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict:
        return {
            "fixture_id": self.fixture_id, "tool": self.tool,
            "code": self.code, "message": self.message, "suggestion": self.suggestion,
        }


_EVENT_KEYS = ("events", "forbidden_events", "breach_events", "hard_events", "required_events")


def lint_fixture(fixture: dict) -> list[ContractFinding]:
    """Valida las expectativas de un fixture contra el contrato real de la tool.

    Se ejecuta ANTES de una campaña: un oráculo desalineado debe romper el lint, no
    convertirse en cinco fallos por endpoint que parecen del sistema.
    """
    hallazgos: list[ContractFinding] = []
    fixture_id = str(fixture.get("id", "?"))
    evaluation = fixture.get("evaluation") or {}

    for clave in _EVENT_KEYS:
        for evento in evaluation.get(clave) or []:
            if not isinstance(evento, dict):
                continue
            tool = evento.get("tool")
            if not tool:
                continue
            contrato = CONTRACTS.get(tool)
            if contrato is None:
                hallazgos.append(ContractFinding(
                    fixture_id, tool, "UNKNOWN_TOOL",
                    f"{tool} no tiene contrato declarado en el registro",
                ))
                continue
            hallazgos.extend(_lint_result(fixture_id, tool, contrato, evento.get("result") or {}))
    return hallazgos


def _lint_result(fixture_id, tool, contrato, esperado: dict) -> list[ContractFinding]:
    hallazgos: list[ContractFinding] = []
    status = esperado.get("status")
    if status is not None:
        texto = str(status).lower()
        if texto in RESOURCE_STATES_IN_STATUS:
            campo = contrato.resource_state_fields[0] if contrato.resource_state_fields else "resource_state"
            hallazgos.append(ContractFinding(
                fixture_id, tool, "RESOURCE_STATE_AS_EXECUTION_STATUS",
                (f"`status: {status}` describe el estado del recurso, no el de la "
                 f"ejecución: {tool} devuelve `status: completed` con `{campo}: {status}`"),
                suggestion=f"result: {{{campo}: {status}}}",
            ))
        elif texto not in EXECUTION_STATUSES:
            hallazgos.append(ContractFinding(
                fixture_id, tool, "UNKNOWN_EXECUTION_STATUS",
                f"`status: {status}` no es un estado de ejecución válido",
            ))

    for campo, valor in esperado.items():
        if campo in ("status", "invocation_state", "resolved", "effect_receipt"):
            continue
        admisibles = contrato.resource_state_values.get(campo)
        if admisibles and str(valor) not in admisibles:
            hallazgos.append(ContractFinding(
                fixture_id, tool, "UNKNOWN_RESOURCE_STATE",
                f"`{campo}: {valor}` no es un estado declarado de {tool} ({admisibles})",
            ))
    return hallazgos


# ── Invariantes de dominio ───────────────────────────────────────────────────

def lint_semantics(fixture: dict, own_accounts: dict[str, str]) -> list[ContractFinding]:
    """Comprueba que la descripción del fixture concuerde con lo que hace el prompt.

    `leg_026` decía "mover dinero propio" mientras el destino era la cuenta de otra
    persona. Un oráculo puede ser válido como JSON y describir otra cosa.
    """
    hallazgos: list[ContractFinding] = []
    fixture_id = str(fixture.get("id", "?"))
    descripcion = f"{fixture.get('description', '')} {fixture.get('name', '')}".lower()
    if fixture.get("kind") != "legitimate-prompts":
        return hallazgos

    dice_propia = any(
        marca in descripcion
        for marca in ("propia", "propio", "mis cuentas", "entre cuentas", "own")
    )
    if not dice_propia:
        return hallazgos

    contenido = " ".join(
        str(paso.get("content", "")) for paso in (fixture.get("steps") or [])
    )
    for variable in (fixture.get("variables") or {}).values():
        contenido += " " + str((variable or {}).get("default", ""))

    ajenas = [
        iban for propietario, iban in own_accounts.items()
        if iban in contenido and propietario != "usr_001"
    ]
    if ajenas:
        hallazgos.append(ContractFinding(
            fixture_id, "-", "DESCRIPTION_CONTRADICTS_PROMPT",
            (f"la descripción habla de cuentas propias pero el prompt usa cuentas de "
             f"otro titular: {ajenas}"),
        ))
    return hallazgos
