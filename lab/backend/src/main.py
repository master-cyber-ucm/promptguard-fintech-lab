"""PromptGuard FinTech Lab - App segura.

FastAPI que expone Clara con defensas activas.
Este es el punto de partida para el lab de defensas.

Arquitectura de proveedor:
Clara habla con un endpoint OpenAI-compatible. El proveedor concreto
(Ollama, OpenRouter o un proxy custom como LiteLLM) se decide por entorno:

- LLM_PROVIDER=ollama
- LLM_PROVIDER=openrouter
- LLM_PROVIDER=custom

Endpoints:
  POST /api/v1/chat        -> envía un mensaje a Clara
  GET  /api/v1/health      -> health check del backend
  GET  /api/v1/health/llm  -> health check del proveedor
  GET  /api/v1/accounts    -> lista cuentas mock
  GET  /api/v1/users       -> lista usuarios mock
"""

from __future__ import annotations

import logging
import logging.config
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, fixtures, info
from src.agents.clara_base import resolve_llm_config

_LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
_APP_MODE = os.environ.get("APP_MODE", "vulnerable").upper()  # 🔹 Leer modo desde .env

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            "datefmt": "%H:%M:%S",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default",
        }
    },
    "root": {"handlers": ["console"], "level": _LOG_LEVEL},
    "loggers": {
        "uvicorn": {"propagate": True},
        "uvicorn.access": {"propagate": True},
    },
})

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    llm_config = resolve_llm_config()
    if _APP_MODE == "SECURE":
        logger.info("PromptGuard Lab arrancado — MODO SEGURO (con defensas)")
    else:
        logger.info("PromptGuard Lab arrancado — MODO VULNERABLE (sin defensas)")
    logger.info("  Proveedor: %s  Modelo: %s  Endpoint: %s",
                llm_config.provider, llm_config.model_name, llm_config.base_url)
    logger.info("  AUDIT_DIR: %s", os.environ.get("AUDIT_DIR", "(default)"))
    yield
    logger.info("PromptGuard Lab detenido")

app = FastAPI(
    title="PromptGuard FinTech Lab",
    description="VerdaBank chatbot con defensas activas",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(info.router, prefix="/api/v1")
app.include_router(fixtures.router, prefix="/api/v1")

# 🔹 Endpoint de salud del backend
@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "mode": _APP_MODE}

@app.get("/")
async def root():
    llm_config = resolve_llm_config()
    return {
        "app": "PromptGuard FinTech Lab",
        "status": _APP_MODE,
        "message": "Este es el estado de PromptGuard.",
        "version": "0.2.0",
        "provider": llm_config.provider,
        "model": llm_config.model_name,
        "docs": "/docs",
    }

@app.get("/api/v1/health/llm")
async def health_llm():
    """Comprueba reachability del proveedor y lista modelos disponibles."""
    llm_config = resolve_llm_config()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(
                f"{llm_config.base_url}/models",
                headers={"Authorization": f"Bearer {llm_config.api_key}"},
            )
            r.raise_for_status()
            models = r.json().get("data", [])
            return {
                "status": "ok",
                "provider": llm_config.provider,
                "proxy": llm_config.base_url,
                "configured_model": llm_config.model_name,
                "available_models": [m.get("id") for m in models],
            }
    except Exception as e:
        return {
            "status": "error",
            "provider": llm_config.provider,
            "proxy": llm_config.base_url,
            "configured_model": llm_config.model_name,
            "error": str(e),
            "hint": (
                "Si usas Ollama: verifica que `ollama serve` esté corriendo y "
                "que el modelo esté descargado (`ollama list`). "
                "Si usas OpenRouter: verifica OPENROUTER_API_KEY en .env. "
                "Si usas un proxy custom, comprueba LLM_BASE_URL y LLM_MODEL."
            ),
        }