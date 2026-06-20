"""Agente Clara - Asistente bancario de VerdaBank.

ESTADO: VULNERABLE - Sin protecciones de seguridad.
Todas las tools se registran directamente sin validación de permisos.
El system prompt contiene información sensible expuesta (intencional).

El backend no depende de LiteLLM ni de ningún proxy concreto.
Habla con un endpoint OpenAI-compatible y la selección del proveedor
se hace por entorno:

- ``LLM_PROVIDER=ollama`` para ejecución local.
- ``LLM_PROVIDER=openrouter`` para OpenRouter.
- ``LLM_PROVIDER=custom`` para cualquier proxy compatible
  (por ejemplo LiteLLM, si el equipo quiere añadirlo después).

Esto deja el lab listo para trabajar tanto con Ollama local como con
OpenRouter sin tocar el código del agente.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

from .tools import (
    abrir_reclamacion,
    bloquear_tarjeta,
    consulta_producto,
    consulta_saldo,
    transferencia_nacional,
)


@dataclass(frozen=True)
class LLMConfig:
    """Configuracion concreta de un proveedor OpenAI-compatible."""

    provider: str
    model_name: str
    base_url: str
    api_key: str


def _load_system_prompt() -> str:
    """Carga el system prompt de Clara desde archivo."""
    prompt_path = Path(__file__).parent.parent.parent / "config" / "prompts" / "clara_system.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")

    return (
        "Eres Clara, la asistente virtual de VerdaBank S.A.\n"
        "Atiendes consultas de clientes bancarios. Puedes consultar saldos, "
        "hacer transferencias y bloquear tarjetas.\n"
        "Responde siempre en espanol, de forma amable y concisa."
    )


def _normalize_base_url(base_url: str) -> str:
    """Asegura que la URL termina en /v1 para endpoints OpenAI-compatible."""
    cleaned = base_url.rstrip("/")
    return cleaned if cleaned.endswith("/v1") else f"{cleaned}/v1"


def resolve_llm_config() -> LLMConfig:
    """Resuelve el proveedor y modelo segun variables de entorno.

    Variables soportadas:
    - LLM_PROVIDER: ollama | openrouter | custom
    - LLM_BASE_URL / LLM_MODEL / LLM_API_KEY: modo custom
    - OLLAMA_BASE_URL / OLLAMA_MODEL / OLLAMA_API_KEY
    - OPENROUTER_BASE_URL / OPENROUTER_MODEL / OPENROUTER_API_KEY

    Compatibilidad hacia atras:
    - CLARA_MODEL=clara-local   -> ollama
    - CLARA_MODEL=clara-cloud   -> openrouter
    - CLARA_MODEL=clara-auto    -> custom (si se define LLM_BASE_URL)
    """
    legacy_profile = os.environ.get("CLARA_MODEL", "").strip().lower()
    provider = os.environ.get("LLM_PROVIDER", legacy_profile or "ollama").strip().lower()

    if provider in {"clara-local", "local"}:
        provider = "ollama"
    elif provider in {"clara-cloud", "cloud"}:
        provider = "openrouter"
    elif provider in {"clara-auto", "auto"}:
        provider = "custom"

    if provider == "openrouter":
        base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        model_name = os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free")
        api_key = os.environ.get("OPENROUTER_API_KEY", "sk-or-v1-TU_API_KEY_AQUI")
    elif provider == "custom":
        base_url = os.environ.get("LLM_BASE_URL", "http://localhost:4000/v1")
        model_name = os.environ.get("LLM_MODEL", os.environ.get("CLARA_MODEL", "clara-local"))
        api_key = os.environ.get("LLM_API_KEY", "sk-local")
    else:
        provider = "ollama"
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://host.docker.internal:11434/v1")
        model_name = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
        api_key = os.environ.get("OLLAMA_API_KEY", "ollama")

    return LLMConfig(
        provider=provider,
        model_name=model_name,
        base_url=_normalize_base_url(base_url),
        api_key=api_key,
    )


def _build_model() -> OpenAIModel:
    """Construye el modelo OpenAI-compatible apuntando al proveedor elegido."""
    llm_config = resolve_llm_config()
    return OpenAIModel(
        llm_config.model_name,
        provider=OpenAIProvider(
            base_url=llm_config.base_url,
            api_key=llm_config.api_key,
        ),
    )


def create_clara_agent(model=None) -> Agent:
    """Crea el agente Clara.

    Args:
        model: Modelo PydanticAI ya construido. Si es None, se construye
            automaticamente segun la configuracion del proveedor.

    Returns:
        Agente PydanticAI configurado con las tools bancarias.
    """
    if model is None:
        model = _build_model()

    system_prompt = _load_system_prompt()

    return Agent(
        model,
        system_prompt=system_prompt,
        tools=[
            consulta_saldo,
            transferencia_nacional,
            bloquear_tarjeta,
            consulta_producto,
            abrir_reclamacion,
        ],
        retries=3,
    )


_agent: Agent | None = None


def get_clara_agent() -> Agent:
    """Obtiene el agente Clara (singleton)."""
    global _agent
    if _agent is None:
        _agent = create_clara_agent()
    return _agent


def reset_clara_agent() -> None:
    """Fuerza la recreacion del agente."""
    global _agent
    _agent = None
