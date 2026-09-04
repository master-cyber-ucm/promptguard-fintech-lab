"""Agente Clara — Configuración: system prompt complejo.

System prompt completo: rol + capacidades + reglas de seguridad + información
interna + formato de respuesta.

Variable experimental medida: efecto de las instrucciones de seguridad y de la
exposición de información interna en el sistema prompt.

Usado por dos endpoints que difieren solo en la inyección de contexto:
  POST /api/v1/chat/complex-prompt        → sin contexto de usuario en el mensaje
  POST /api/v1/chat/complex-with-context  → con contexto de usuario en el mensaje
"""

from __future__ import annotations

from pathlib import Path

from pydantic_ai import Agent

from .clara_base import _build_model, _default_model_settings
from .tool_catalog import exposed_tool_names
from .tools import TOOL_DEFINITIONS, Deps

from src.core.canaries import render_system_prompt


def _load_prompt() -> str:
    """Carga el system prompt con los canarios del run ya sustituidos.

    Los valores confidenciales pueden rotarse por corrida (`CANARY_SALT`) para que una
    coincidencia accidental deje de ser posible al medir fugas — ver `core/canaries.py`.
    """
    p = Path(__file__).parent.parent.parent / "config" / "prompts" / "clara_system.txt"
    if p.exists():
        return render_system_prompt(p.read_text(encoding="utf-8"))
    return (
        "Eres Clara, la asistente virtual de VerdaBank S.A.\n"
        "Responde siempre en español, de forma amable y concisa."
    )


def create_clara_agent_complex(model=None) -> Agent:
    return Agent(
        model or _build_model(),
        deps_type=Deps,
        system_prompt=_load_prompt(),
        # El catálogo es único: lo que ve el agente, lo que valida el runtime y lo que
        # los fixtures pueden evaluar salen del mismo sitio. `consulta_saldo` estaba en
        # el registro y NO en esta lista, mientras varios fixtures medían su uso (P20).
        tools=[TOOL_DEFINITIONS[nombre]["function"] for nombre in exposed_tool_names()],
        retries=3,
        model_settings=_default_model_settings(),
    )


_agent: Agent | None = None


def get_clara_agent_complex() -> Agent:
    global _agent
    if _agent is None:
        _agent = create_clara_agent_complex()
    return _agent


def reset_clara_agent_complex() -> None:
    global _agent
    _agent = None
