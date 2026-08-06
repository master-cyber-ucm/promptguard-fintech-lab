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

from pydantic_ai import Agent, Tool  # [Damaro] Tool para exponer alias con nombre distinto

from .clara_base import _build_model
from .tools import (
    abrir_reclamacion,
    bloquear_tarjeta,
    ClaraDeps,                    # [Damaro] deps del Gatekeeper
    consulta_producto,
    consulta_saldo,
    consulta_saldo_gatekeeper,    # [Damaro] tool con validación de propiedad
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

# ============================================================
# [DEFENSA GATEKEEPER — agregado por Damaro, TFM PromptGuard]
# Agente en PARALELO a create_clara_agent_complex(). No modifica
# ni reemplaza el agente original — ese sigue usándose intacto en
# los endpoints /chat/complex-prompt y /chat/complex-with-context
# (modo vulnerable, pruebas ya documentadas).
#
# Este agente nuevo usa consulta_saldo_gatekeeper en vez de
# consulta_saldo, y requiere deps_type=ClaraDeps para recibir el
# user_id autenticado de forma estructural (vía RunContext) en
# lugar de solo como texto libre en el prompt.
# ============================================================

def create_clara_agent_gatekeeper(model=None) -> Agent:
    return Agent(
        model or _build_model(),
        deps_type=ClaraDeps,
        system_prompt=_load_prompt(),
     tools=[
    # [Damaro] Se expone con el mismo NOMBRE "consulta_saldo" que usan los
    # fixtures reales (atk_008/atk_009), para que el ataque original corra
    # SIN modificar el YAML. Por debajo ejecuta consulta_saldo_gatekeeper,
    # que sí valida propiedad de cuenta. Así el bloqueo ocurre por la razón
    # correcta (defensa), no por incompatibilidad de nombres.
    Tool(consulta_saldo_gatekeeper, name="consulta_saldo"),
    transferencia_nacional,
    bloquear_tarjeta,
    consulta_producto,
    abrir_reclamacion,
          ],
        retries=3,
    )


_agent_gatekeeper: Agent | None = None


def get_clara_agent_gatekeeper() -> Agent:
    """[Damaro] Singleton del agente Gatekeeper, mismo patrón que get_clara_agent_complex()."""
    global _agent_gatekeeper
    if _agent_gatekeeper is None:
        _agent_gatekeeper = create_clara_agent_gatekeeper()
    return _agent_gatekeeper


def reset_clara_agent_gatekeeper() -> None:
    """[Damaro] Reset del singleton, usado por hot-reload / tests."""
    global _agent_gatekeeper
    _agent_gatekeeper = None

# ============================================================
# [FIN bloque Damaro — Gatekeeper]
# ============================================================