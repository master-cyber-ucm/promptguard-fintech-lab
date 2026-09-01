"""Construye el índice de procedencia de una ejecución a partir de su evidencia.

Solo cuentan como valores de tool los que vienen de una invocación con resultado
autorizado: un `denied` no entregó nada, y un resultado que se declara consumado sin
recibo del dominio no acredita que ese dato saliera de ninguna parte.
"""

from __future__ import annotations

import json

from src.models.provenance import ValueProvenanceIndex
from src.models.tool_invocation import effect_observed, has_legacy_effect_evidence


def authorized_tool_values(tools: list[dict]) -> tuple[str, ...]:
    valores: list[str] = []
    for call in tools or []:
        result = call.get("result")
        if not isinstance(result, dict) or not result:
            continue
        if not (effect_observed(result) or has_legacy_effect_evidence(result)):
            continue
        valores.append(json.dumps(result, ensure_ascii=False, default=str))
    return tuple(valores)


def index_for(context) -> ValueProvenanceIndex:
    """Índice de procedencia del contexto de evaluación.

    `user_input` reúne todo lo que el atacante escribió: es lo que convierte una
    coincidencia en reflexión en vez de en fuga.
    """
    prompts = getattr(context, "prompts", None) or []
    return ValueProvenanceIndex(
        user_input="\n".join(str(p) for p in prompts),
        trusted_context=getattr(context, "system_prompt", "") or "",
        untrusted_documents=getattr(context, "documents", "") or "",
        authorized_tool_values=authorized_tool_values(getattr(context, "tools", [])),
        backend_secrets=_backend_secrets(context),
    )


def _backend_secrets(context) -> tuple[str, ...]:
    from src.core.canaries import canary_values  # noqa: PLC0415

    declarados = tuple(getattr(context, "backend_secrets", ()) or ())
    return tuple(dict.fromkeys((*canary_values(), *declarados)))
