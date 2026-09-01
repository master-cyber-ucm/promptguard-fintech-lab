"""Catálogo único de tools: agente, runtime y fixtures comparten la misma verdad.

P20: `consulta_saldo` estaba en el registro pero no en la lista de tools de ningún
agente, mientras varios fixtures evaluaban su uso — medían algo que el modelo no podía
hacer. Y `get_account_summary` no acepta argumentos, pero Qwen 2.5 3B envía
`account_id`, `account_number` o `user_id` una y otra vez: entre el 30% y el 39% de las
invocaciones acababan como `unknown`.

Dos reglas:

* **Un solo catálogo.** Lo que ve el agente, lo que valida el runtime y lo que los
  fixtures pueden evaluar salen de aquí, y su hash viaja en la Postura efectiva.
* **Los alias se normalizan, la identidad no se acepta.** Que el modelo mande
  `account_id` no puede reventar la llamada, pero tampoco puede ampliar su autoridad:
  el argumento se registra como intento y el recurso se resuelve server-side.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from src.models.tool_invocation import ToolCriticality, criticality_of

#: Argumentos que el modelo intenta pasar y que NUNCA amplían autoridad. Se aceptan
#: para que la llamada no falle, se anotan como intento y se ignoran al resolver.
IDENTITY_ALIASES = ("account_id", "account_number", "accountId", "user_id", "userId", "iban")


@dataclass(frozen=True)
class ToolSpec:
    """Contrato de una tool tal como lo ven modelo, runtime y fixtures."""

    name: str
    criticality: ToolCriticality
    description: str
    #: Parámetros que el modelo SÍ controla.
    params: tuple[str, ...] = ()
    #: Alias tolerados que se normalizan y no conceden autoridad.
    ignored_aliases: tuple[str, ...] = ()
    exposed_to_agent: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "criticality": str(self.criticality),
            "description": self.description,
            "params": list(self.params),
            "ignored_aliases": list(self.ignored_aliases),
            "exposed_to_agent": self.exposed_to_agent,
        }


CATALOG: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="get_account_summary",
        criticality=criticality_of("get_account_summary"),
        description=(
            "Resumen de la cuenta del cliente autenticado. No necesita identificadores: "
            "la cuenta se resuelve desde el canal de autenticación."
        ),
        ignored_aliases=IDENTITY_ALIASES,
    ),
    ToolSpec(
        name="consulta_saldo",
        criticality=criticality_of("consulta_saldo"),
        description=(
            "Saldo, divisa y últimos movimientos de una cuenta. Sin `account_id` "
            "resuelve la cuenta propia; con él, verifica titularidad."
        ),
        params=("account_id",),
    ),
    ToolSpec(
        name="get_kb_article",
        criticality=criticality_of("get_kb_article"),
        description="Artículo aprobado y versionado de la base de conocimiento.",
        params=("key",),
    ),
    ToolSpec(
        name="transferencia_nacional",
        criticality=criticality_of("transferencia_nacional"),
        description="Propone una transferencia SEPA nacional.",
        params=("to_account", "amount", "from_account", "concept"),
    ),
    ToolSpec(
        name="bloquear_tarjeta",
        criticality=criticality_of("bloquear_tarjeta"),
        description="Bloquea una tarjeta del cliente autenticado.",
        params=("card_id", "reason"),
    ),
    ToolSpec(
        name="consulta_producto",
        criticality=criticality_of("consulta_producto"),
        description="Catálogo de productos bancarios.",
        params=("product_type",),
    ),
    ToolSpec(
        name="abrir_reclamacion",
        criticality=criticality_of("abrir_reclamacion"),
        description="Registra una reclamación del cliente autenticado.",
        params=("subject", "description"),
    ),
)

BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in CATALOG}


def exposed_tool_names() -> tuple[str, ...]:
    return tuple(spec.name for spec in CATALOG if spec.exposed_to_agent)


def catalog_hash() -> str:
    """Huella del catálogo efectivo. Viaja en la Postura: dos runs con catálogos
    distintos no son comparables aunque tengan los mismos controles."""
    material = json.dumps([spec.to_dict() for spec in CATALOG], sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def normalize_arguments(tool: str, arguments: dict) -> tuple[dict, list[str]]:
    """Separa lo que el modelo controla de lo que solo intentó pasar.

    Devuelve `(argumentos_efectivos, alias_ignorados)`. Un alias ignorado no es un
    error: es telemetría sobre lo que el modelo cree que necesita, y la señal para
    arreglar el contrato en vez de contar la llamada como `unknown`.
    """
    spec = BY_NAME.get(tool)
    if spec is None:
        return dict(arguments), []
    efectivos = {}
    ignorados = []
    for clave, valor in (arguments or {}).items():
        if clave in spec.params:
            efectivos[clave] = valor
        elif clave in spec.ignored_aliases:
            ignorados.append(clave)
        else:
            ignorados.append(clave)
    return efectivos, sorted(ignorados)


def missing_from_agent(fixture_tools: set[str]) -> list[str]:
    """Tools que los fixtures evalúan y el agente no expone.

    Es el desajuste que hacía inevaluable a `consulta_saldo`: el fixture medía el uso
    de una tool que el modelo no tenía delante.
    """
    expuestas = set(exposed_tool_names())
    return sorted(fixture_tools - expuestas)
