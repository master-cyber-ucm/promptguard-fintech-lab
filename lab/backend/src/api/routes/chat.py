"""Endpoint de chat — VULNERABLE.

Pasa el mensaje del usuario directamente a Clara sin ningún filtro.
No hay sanitización de input, no hay redacción de PII, no hay
validación de permisos en tools.

Este es el endpoint que ATACAREMOS en el lab.
"""

import logging
import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pydantic_ai.messages import ThinkingPart

from src.agents.clara import get_clara_agent, reset_clara_agent
from src.models.banking import MOCK_USERS
from src.utils.audit_repository import append_turn

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


# --- Request / Response ---

class ChatRequest(BaseModel):
    """Request del chat."""
    user_id: str = Field(default="usr_001", description="ID del usuario")
    message: str = Field(..., description="Mensaje para Clara")
    session_id: Optional[str] = Field(default=None, description="ID de sesión (opcional)")
    # Metadatos opcionales del fixture que originó este turno
    fixture_id: Optional[str] = Field(default=None)
    fixture_kind: Optional[str] = Field(default=None)
    fixture_expected_result: Optional[str] = Field(default=None)


class ChatResponse(BaseModel):
    """Response del chat. Incluye metadata para análisis de ataques."""
    user_id: str
    message: str
    response: str
    model: str
    latency_ms: float
    session_id: str
    tools_used: list
    audit_file: Optional[str] = None
    error: Optional[str] = None


# --- Helpers ---

def _extract_tools_and_thinking(result) -> tuple[list[dict], str | None]:
    """Extrae tools invocadas y thinking trace de all_model_responses."""
    tools: list[dict] = []
    thinking: str | None = None

    if not hasattr(result, "all_messages"):
        return tools, thinking

    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ThinkingPart):
                thinking = part.content
            elif hasattr(part, "tool_name"):
                tools.append({
                    "tool": part.tool_name,
                    "args": str(getattr(part, "args", "")),
                })

    return tools, thinking


# --- Endpoint ---

@router.post("/chat", response_model=ChatResponse)
async def chat_with_clara(request: ChatRequest):
    """Envía un mensaje a Clara SIN NINGUNA PROTECCIÓN.

    El mensaje del usuario va directamente al LLM con acceso completo
    a todas las tools bancarias. No hay filtros de entrada ni salida.

    ⚠️  ESTE ES EL ENDPOINT VULNERABLE DEL LAB.
    """
    start_time = time.time()

    user = MOCK_USERS.get(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {request.user_id} no encontrado")

    user_context = (
        f"[Contexto del usuario autenticado: user_id={user['user_id']}, "
        f"nombre={user['name']}, cuenta={user['account_id']}]"
    )
    full_message = f"{user_context}\n\nMensaje del cliente: {request.message}"
    session_id = request.session_id or f"ses_{int(time.time())}"

    fixture_tag = f" fixture={request.fixture_id}" if request.fixture_id else ""
    logger.info("[%s]%s → procesando mensaje (usuario=%s)", session_id, fixture_tag, request.user_id)

    try:
        agent = get_clara_agent()
        result = await agent.run(full_message)
        latency_ms = (time.time() - start_time) * 1000

        tools_used, thinking = _extract_tools_and_thinking(result)
        response_text = str(result.output)
        model_name = str(agent.model)

        audit_path = append_turn(
            session_id=session_id,
            user_id=request.user_id,
            model=model_name,
            prompt=request.message,
            thinking=thinking,
            tools=tools_used,
            response=response_text,
            latency_ms=latency_ms,
            fixture_id=request.fixture_id,
            fixture_kind=request.fixture_kind,
            fixture_expected_result=request.fixture_expected_result,
        )

        tool_names = [t["tool"] for t in tools_used] if tools_used else []
        thinking_tag = " [thinking]" if thinking else ""
        logger.info(
            "[%s]%s ✓ %dms tools=%s%s audit=%s",
            session_id, fixture_tag, round(latency_ms), tool_names, thinking_tag, audit_path.name,
        )

        return ChatResponse(
            user_id=request.user_id,
            message=request.message,
            response=response_text,
            model=model_name,
            latency_ms=round(latency_ms, 1),
            session_id=session_id,
            tools_used=tools_used,
            audit_file=audit_path.name,
        )

    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000
        err_str = str(e)

        hint = None
        low = err_str.lower()
        if "connection" in low or "refused" in low or "connect" in low:
            hint = (
                "Backend no puede alcanzar el proveedor LLM. Revisa la URL y que "
                "el servicio elegido este disponible."
            )
            reset_clara_agent()
        elif "ollama" in low or "model not found" in low:
            hint = (
                "Ollama no tiene el modelo. Descárgalo con "
                "`ollama pull qwen3.5:9b` o cambia LLM_PROVIDER=openrouter en .env."
            )
            reset_clara_agent()
        elif "401" in low or "api key" in low or "unauthorized" in low:
            hint = "API key del proveedor invalida. Verifica OPENROUTER_API_KEY o LLM_API_KEY en lab/.env."

        logger.error("[%s]%s ✗ %dms error=%s", session_id, fixture_tag, round(latency_ms), err_str)

        return ChatResponse(
            user_id=request.user_id,
            message=request.message,
            response="",
            model="",
            latency_ms=round(latency_ms, 1),
            session_id=session_id,
            tools_used=[],
            error=f"{err_str}{' | HINT: ' + hint if hint else ''}",
        )
