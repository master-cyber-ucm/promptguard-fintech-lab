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

from .clara_base import _build_model
from .tools import (
    Deps,
    abrir_reclamacion,
    bloquear_tarjeta,
    consulta_producto,
    consulta_saldo,
    transferencia_nacional,
)


def _load_prompt() -> str:
    p = Path(__file__).parent.parent.parent / "config" / "prompts" / "clara_system.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return (
        "Eres Clara, la asistente virtual de VerdaBank S.A.\n"
        "Responde siempre en español, de forma amable y concisa."
    )


def create_clara_agent_complex(model=None) -> Agent:
    return Agent(
        model or _build_model(),
        deps_type=Deps,
        system_prompt=_load_prompt(),
        tools=[consulta_saldo, transferencia_nacional, bloquear_tarjeta, consulta_producto, abrir_reclamacion],
        retries=3,
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
