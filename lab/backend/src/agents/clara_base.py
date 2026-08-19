"""Infraestructura compartida de proveedores LLM para los agentes Clara.

Todos los agentes (clara_simple, clara_complex) importan de aquí.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

# Denegación de Servicio (#8, LLM10:2025) — "Generación sin techo": ninguna llamada al
# proveedor fijaba un límite de tokens de salida antes de esto. Ver
# docs/defensas/LLM10-unbounded-consumption/denegacion-de-servicio.md §3.2. Un valor de
# referencia generoso para el uso legítimo del lab (una respuesta de Clara con contexto
# no se acerca a este límite) — configurable porque el límite razonable depende del
# proveedor activo (Ollama local vs. uno de pago).
DEFAULT_MAX_OUTPUT_TOKENS = 1024


def _default_model_settings() -> ModelSettings:
    max_tokens = int(os.environ.get("CLARA_MAX_OUTPUT_TOKENS", DEFAULT_MAX_OUTPUT_TOKENS))
    return ModelSettings(max_tokens=max_tokens)


@dataclass(frozen=True)
class LLMConfig:
    """Configuracion concreta de un proveedor OpenAI-compatible."""

    provider: str
    model_name: str
    base_url: str
    api_key: str


def _normalize_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    return cleaned if cleaned.endswith("/v1") else f"{cleaned}/v1"


def resolve_llm_config() -> LLMConfig:
    """Resuelve el proveedor y modelo segun variables de entorno.

    Variables soportadas:
    - LLM_PROVIDER: ollama | openrouter | custom
    - LLM_BASE_URL / LLM_MODEL / LLM_API_KEY: modo custom
    - OLLAMA_BASE_URL / OLLAMA_MODEL / OLLAMA_API_KEY
    - OPENROUTER_BASE_URL / OPENROUTER_MODEL / OPENROUTER_API_KEY
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
    cfg = resolve_llm_config()
    return OpenAIModel(
        cfg.model_name,
        provider=OpenAIProvider(base_url=cfg.base_url, api_key=cfg.api_key),
    )
