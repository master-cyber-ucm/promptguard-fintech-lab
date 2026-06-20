"""Endpoint de chat — VULNERABLE.

Pasa el mensaje del usuario directamente a Clara sin ningún filtro.
No hay sanitización de input, no hay redacción de PII, no hay
validación de permisos en tools.

Este es el endpoint que ATACAREMOS en el lab.
"""

import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.agents.clara import get_clara_agent, reset_clara_agent
from src.models.banking import MOCK_USERS

router = APIRouter(tags=["chat"])


# --- Request / Response ---

class ChatRequest(BaseModel):
    """Request del chat. Simple: user_id + message."""
    user_id: str = Field(default="usr_001", description="ID del usuario")
    message: str = Field(..., description="Mensaje para Clara")
    session_id: Optional[str] = Field(default=None, description="ID de sesión (opcional)")


class ChatResponse(BaseModel):
    """Response del chat. Incluye metadata para análisis de ataques."""
    user_id: str
    message: str          # Mensaje enviado
    response: str         # Respuesta de Clara
    model: str            # Modelo usado por el proveedor LLM
    latency_ms: float     # Latencia total
    session_id: str       # ID de sesión
    tools_used: list      # Tools invocadas (si las hay)
    error: Optional[str]  # Error si lo hubo


# --- Endpoint ---

@router.post("/chat", response_model=ChatResponse)
async def chat_with_clara(request: ChatRequest):
    """Envía un mensaje a Clara SIN NINGUNA PROTECCIÓN.

    El mensaje del usuario va directamente al LLM con acceso completo
    a todas las tools bancarias. No hay filtros de entrada ni salida.

    ⚠️  ESTE ES EL ENDPOINT VULNERABLE DEL LAB.
    """
    start_time = time.time()

    # Buscar usuario mock
    user = MOCK_USERS.get(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {request.user_id} no encontrado")

    # Contexto del usuario (disponible para el agente)
    user_context = f"[Contexto del usuario autenticado: user_id={user['user_id']}, nombre={user['name']}, cuenta={user['account_id']}]"

    # Mensaje completo que se envía a Clara
    full_message = f"{user_context}\n\nMensaje del cliente: {request.message}"

    try:
        agent = get_clara_agent()
        result = await agent.run(full_message)

        latency_ms = (time.time() - start_time) * 1000

        # Extraer info de tools usadas si está disponible
        tools_used = []
        if hasattr(result, 'all_model_responses'):
            for resp in result.all_model_responses:
                if hasattr(resp, 'tool_calls') and resp.tool_calls:
                    for tc in resp.tool_calls:
                        tools_used.append({
                            "tool": tc.tool_name if hasattr(tc, 'tool_name') else str(tc),
                            "args": str(tc.args) if hasattr(tc, 'args') else "",
                        })

        return ChatResponse(
            user_id=request.user_id,
            message=request.message,
            response=str(result.output),
            model=str(agent.model),
            latency_ms=round(latency_ms, 1),
            session_id=request.session_id or f"ses_{int(time.time())}",
            tools_used=tools_used,
            error=None,
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        err_str = str(e)

        # Diagnóstico específico para los fallos más comunes del lab.
        hint = None
        low = err_str.lower()
        if "connection" in low or "refused" in low or "connect" in low:
            hint = (
                "Backend no puede alcanzar el proveedor LLM. Revisa la URL y que "
                "el servicio elegido este disponible."
            )
            # Si el agente quedó en estado inconsistente, lo reiniciamos para
            # que el siguiente intento construya de nuevo la conexión.
            reset_clara_agent()
        elif "ollama" in low or "model not found" in low:
            hint = (
                "Ollama no tiene el modelo. Descárgalo con "
                "`ollama pull qwen3.5:9b` o cambia LLM_PROVIDER=openrouter en .env."
            )
            reset_clara_agent()
        elif "401" in low or "api key" in low or "unauthorized" in low:
            hint = (
                "API key del proveedor invalida. Verifica OPENROUTER_API_KEY o LLM_API_KEY en lab/.env."
            )

        return ChatResponse(
            user_id=request.user_id,
            message=request.message,
            response="",
            model="",
            latency_ms=round(latency_ms, 1),
            session_id=request.session_id or f"ses_{int(time.time())}",
            tools_used=[],
            error=f"{err_str}{' | HINT: ' + hint if hint else ''}",
        )
