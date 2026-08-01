"""Endpoints de chat — tres configuraciones pre-proxy.

Progresión de menor a mayor defensa:

  POST /api/v1/chat/simple-prompt
      System prompt mínimo (rol + capacidades + formato).
      Sin reglas de seguridad ni información interna.
      Sin contexto de usuario en el mensaje.

  POST /api/v1/chat/complex-prompt
      System prompt completo de Clara (reglas + info interna).
      Sin contexto de usuario en el mensaje.

  POST /api/v1/chat/complex-with-context
      System prompt completo + bloque [Contexto del usuario autenticado]
      inyectado en cada mensaje. Configuración actual del lab vulnerable.
"""

import logging
import time
from typing import Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from pydantic_ai.messages import ThinkingPart

from src.agents.clara_complex import get_clara_agent_complex, reset_clara_agent_complex
from src.agents.clara_simple import get_clara_agent_simple, reset_clara_agent_simple
from src.models.banking import MOCK_USERS
from src.utils.audit_repository import append_turn
from src.core.output_auditor import audit_response

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


# --- Request / Response ---

class ChatRequest(BaseModel):
    user_id: str = Field(default="usr_001", description="ID del usuario")
    message: str = Field(..., description="Mensaje para Clara")
    session_id: Optional[str] = Field(default=None, description="ID de sesión (opcional)")
    fixture_id: Optional[str] = Field(default=None)
    fixture_kind: Optional[str] = Field(default=None)
    fixture_expected_result: Optional[str] = Field(default=None)
    audit_subdir: Optional[str] = Field(default=None, description="Ruta absoluta del directorio destino para el Session File")


class ChatResponse(BaseModel):
    user_id: str
    message: str
    response: str
    model: str
    latency_ms: float
    session_id: str
    tools_used: list
    endpoint: str
    audit_file: Optional[str] = None
    error: Optional[str] = None


# --- Helpers ---

def _extract_tools_and_thinking(result) -> tuple[list[dict], str | None]:
    tools: list[dict] = []
    thinking: str | None = None
    if not hasattr(result, "all_messages"):
        return tools, thinking
    for msg in result.all_messages():
        for part in getattr(msg, "parts", []):
            if isinstance(part, ThinkingPart):
                thinking = part.content
            elif hasattr(part, "tool_name"):
                tools.append({"tool": part.tool_name, "args": str(getattr(part, "args", ""))})
    return tools, thinking


async def _process_chat(
    request: ChatRequest,
    endpoint_name: str,
    agent,
    reset_fn: Callable,
    inject_context: bool,
) -> ChatResponse:
    start_time = time.time()

    user = MOCK_USERS.get(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail=f"Usuario {request.user_id} no encontrado")

    if inject_context:
        user_context = (
            f"[Contexto del usuario autenticado: user_id={user['user_id']}, "
            f"nombre={user['name']}, cuenta={user['account_id']}]"
        )
        full_message = f"{user_context}\n\nMensaje del cliente: {request.message}"
    else:
        full_message = request.message

    session_id = request.session_id or f"ses_{int(time.time())}"
    fixture_tag = f" fixture={request.fixture_id}" if request.fixture_id else ""
    logger.info("[%s]%s → %s (usuario=%s)", session_id, fixture_tag, endpoint_name, request.user_id)

    try:
        result = await agent.run(full_message)
        latency_ms = (time.time() - start_time) * 1000

        tools_used, thinking = _extract_tools_and_thinking(result)
        response_text = str(result.output)
        response_text, leak_blocked = audit_response(response_text)
        if leak_blocked:
            logger.warning(
                "[%s]%s ⚠ Output Auditor bloqueó una fuga de secreto de configuración",
                session_id, fixture_tag,
            )
        model_name = getattr(agent.model, "model_name", str(agent.model))

        audit_path = append_turn(
            session_id=session_id,
            user_id=request.user_id,
            model=model_name,
            prompt=full_message,
            thinking=thinking,
            tools=tools_used,
            response=response_text,
            latency_ms=latency_ms,
            system_prompt="\n".join(agent._system_prompts) or None,
            fixture_id=request.fixture_id,
            fixture_kind=request.fixture_kind,
            fixture_expected_result=request.fixture_expected_result,
            audit_subdir=request.audit_subdir,
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
            endpoint=endpoint_name,
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
            reset_fn()
        elif "ollama" in low or "model not found" in low:
            hint = (
                "Ollama no tiene el modelo. Descárgalo con "
                "`ollama pull qwen3.5:9b` o cambia LLM_PROVIDER=openrouter en .env."
            )
            reset_fn()
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
            endpoint=endpoint_name,
            error=f"{err_str}{' | HINT: ' + hint if hint else ''}",
        )


# --- Endpoints ---

@router.post("/chat/simple-prompt", response_model=ChatResponse)
async def chat_simple_prompt(request: ChatRequest):
    """System prompt mínimo (rol + capacidades). Sin reglas de seguridad ni contexto de usuario."""
    return await _process_chat(
        request, "simple-prompt",
        get_clara_agent_simple(), reset_clara_agent_simple,
        inject_context=False,
    )


@router.post("/chat/complex-prompt", response_model=ChatResponse)
async def chat_complex_prompt(request: ChatRequest):
    """System prompt completo de Clara. Sin contexto de usuario inyectado en el mensaje."""
    return await _process_chat(
        request, "complex-prompt",
        get_clara_agent_complex(), reset_clara_agent_complex,
        inject_context=False,
    )


@router.post("/chat/complex-with-context", response_model=ChatResponse)
async def chat_complex_with_context(request: ChatRequest):
    """System prompt completo + contexto de usuario inyectado. Configuración actual del lab vulnerable."""
    return await _process_chat(
        request, "complex-with-context",
        get_clara_agent_complex(), reset_clara_agent_complex,
        inject_context=True,
    )
