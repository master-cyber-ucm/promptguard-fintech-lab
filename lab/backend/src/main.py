"""PromptGuard FinTech Lab - App vulnerable.

FastAPI que expone Clara directamente, sin ninguna capa de seguridad.
Este es el punto de partida para el lab de ataques.

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

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import chat, info
from src.agents.clara import resolve_llm_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: diagnostico y carga perezosa del agente."""
    llm_config = resolve_llm_config()
    print("🏦 PromptGuard Lab - MODO VULNERABLE (sin defensas)")
    print(f"   Proveedor LLM:       {llm_config.provider}")
    print(f"   Modelo:              {llm_config.model_name}")
    print(f"   Endpoint:            {llm_config.base_url}")
    print("   Clara agent: lazy init (se creara en la primera peticion)")
    yield
    print("🛑 PromptGuard Lab detenido")


app = FastAPI(
    title="PromptGuard FinTech Lab",
    description="VerdaBank chatbot vulnerable - sin protecciones de seguridad",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(info.router, prefix="/api/v1")


@app.get("/")
async def root():
    llm_config = resolve_llm_config()
    return {
        "app": "PromptGuard FinTech Lab",
        "status": "VULNERABLE",
        "message": "Este es el estado pre-PromptGuard. Sin defensas activas.",
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
                "Si usas Ollama: verifica que `ollama serve` esta corriendo y "
                "que el modelo esta descargado (`ollama list`). "
                "Si usas OpenRouter: verifica OPENROUTER_API_KEY en .env. "
                "Si usas un proxy custom, comprueba LLM_BASE_URL y LLM_MODEL."
            ),
        }
