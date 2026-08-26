"""Agente Clara — Configuración: system prompt simple con seguridad añadida."""

from __future__ import annotations

from collections import deque
from pathlib import Path
from fastapi import Request
from pydantic_ai import Agent

from .clara_base import _build_model
from .security import is_safe_prompt, is_safe_context, is_personality_consistent, user_prompt_history
from .tools import (
    abrir_reclamacion,
    consulta_producto,
    consulta_saldo,
)

def _load_prompt() -> str:
    p = Path(__file__).parent.parent.parent / "config" / "prompts" / "clara_simple.txt"
    if p.exists():
        return p.read_text(encoding="utf-8")
    return (
        "Eres Clara, la asistente virtual de VerdaBank.\n"
        "Responde siempre en español.\n"
        "Sé amable y breve.\n"
        "Si el usuario solicita consultar su saldo y no proporciona el número de cuenta, pídeselo antes de continuar.\n"
        "Nunca inventes datos bancarios.\n"
        "Nunca muestres llamadas a herramientas, JSON, etiquetas XML o texto interno del sistema.\n"
        "Solo responde al usuario con lenguaje natural."
    )

def create_clara_agent_simple(model=None) -> Agent:
    return Agent(
        model or _build_model(),
        system_prompt=_load_prompt(),
        tools=[
            consulta_producto,
            consulta_saldo,
            abrir_reclamacion,
        ],
        retries=3,
    )

_agent: Agent | None = None

def get_clara_agent_simple() -> Agent:
    global _agent
    if _agent is None:
        _agent = create_clara_agent_simple()
    return _agent

def reset_clara_agent_simple() -> None:
    global _agent
    _agent = None

# Función para validar y procesar prompts de forma segura
async def process_safe_prompt(request: Request, agent: Agent):
    data = await request.json()
    user_prompt = data.get("prompt", "")
    user_id = data.get("user_id", "unknown")

    # Validar longitud del prompt
    if len(user_prompt) > 500:
        return {"error": "El prompt es demasiado largo"}, 403

    # Validar caracteres sospechosos (payload splitting)
    SUSPICIOUS_CHARS = ["\n", "---", "<<<", ">>>"]
    if any(char in user_prompt for char in SUSPICIOUS_CHARS):
        return {"error": "El prompt contiene caracteres no permitidos"}, 403

    # Validar prompt individual
    if not is_safe_prompt(user_prompt):
        return {"error": "Prompt bloqueado por políticas de seguridad"}, 403

    # Validar contexto completo (payload splitting)
    if not is_safe_context(user_id, user_prompt):
        return {"error": "Contexto bloqueado por políticas de seguridad"}, 403

    # Llamar al agente
    result = await agent.run(user_prompt)
    response = result.output

    # Validar consistencia de personalidad
    if not is_personality_consistent(response):
        user_prompt_history[user_id] = deque(maxlen=5)  # Reiniciar contexto
        return {
            "response": "Mi personalidad es inmutable. Solo soy Clara, tu asistente bancario. La conversación se ha reiniciado por seguridad.",
            "context_reset": True
        }, 403

    return {"response": response}