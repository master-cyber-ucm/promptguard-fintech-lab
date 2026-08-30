"""
clara_target.py

Target de PyRIT adaptado a la API real de PromptGuard FinTech Lab (Clara).

La API de Clara NO usa el formato estándar OpenAI, así que no vale un
target genérico de PyRIT. Aquí definimos un target "a medida" que:

  1. Coge el prompt que el orquestador de PyRIT quiere probar.
  2. Lo aplana (quita saltos de línea y secuencias que el backend bloquea
     de forma explícita: "---", "<<<", ">>>") para que pase el filtro de
     "caracteres sospechosos" del backend y podamos medir qué pasa
     DESPUÉS de ese filtro, no que se quede bloqueado antes de llegar
     al LLM. Si tu evaluación quiere medir también ese filtro de
     entrada, hay una bandera (FLATTEN_PROMPTS) para desactivar esto.
  3. Llama a POST /api/v1/chat/simple-prompt (o complex-prompt) con el
     formato {"prompt": ..., "user_id": ...}.
  4. Devuelve la respuesta en el formato que PyRIT espera internamente
     (PromptRequestResponse).

Requiere: pyrit>=0.8,<0.9  (ajusta si tu profesor os pide otra versión)
"""

from __future__ import annotations

import uuid
import httpx

from pyrit.models import PromptRequestResponse, PromptRequestPiece
from pyrit.prompt_target import PromptTarget

# Si True, se eliminan \n, ---, <<<, >>> antes de enviar, para que el
# prompt no se quede bloqueado por el filtro de "caracteres sospechosos"
# del backend y podamos evaluar las capas de seguridad que vienen después
# (is_safe_prompt, is_safe_context, is_personality_consistent).
# Ponlo en False si quieres medir también ese primer filtro tal cual.
FLATTEN_PROMPTS = True

SUSPICIOUS_SEQUENCES = ["\n", "---", "<<<", ">>>"]


def _flatten(text: str) -> str:
    if not FLATTEN_PROMPTS:
        return text
    cleaned = text
    for seq in SUSPICIOUS_SEQUENCES:
        cleaned = cleaned.replace(seq, " ")
    return cleaned.strip()


class ClaraTarget(PromptTarget):
    """Target de PyRIT para la API de Clara (PromptGuard FinTech Lab)."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        endpoint: str = "/api/v1/chat/simple-prompt",
        user_id: str = "pyrit-redteam",
        timeout: float = 60.0,
    ) -> None:
        super().__init__()
        self._url = base_url.rstrip("/") + endpoint
        self._user_id = user_id
        self._timeout = timeout

    async def send_prompt_async(
        self, *, prompt_request: PromptRequestResponse
    ) -> PromptRequestResponse:
        request_piece: PromptRequestPiece = prompt_request.request_pieces[0]
        raw_prompt = request_piece.converted_value

        payload = {
            "prompt": _flatten(raw_prompt),
            "user_id": self._user_id,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                r = await client.post(self._url, json=payload)
                r.raise_for_status()
                data = r.json()
                response_text = data.get(
                    "response",
                    data.get("error", f"[respuesta inesperada] {data}"),
                )
            except httpx.HTTPStatusError as e:
                # El backend devuelve 403 con {"error": "..."} cuando un
                # filtro bloquea el prompt. Eso NO es un fallo del script:
                # es justo el dato que queremos registrar (bloqueado).
                try:
                    body = e.response.json()
                    response_text = f"[BLOQUEADO {e.response.status_code}] {body.get('error', body)}"
                except Exception:
                    response_text = f"[ERROR HTTP {e.response.status_code}]"
            except Exception as e:
                response_text = f"[ERROR DE CONEXIÓN] {e}"

        response_piece = PromptRequestPiece(
            role="assistant",
            original_value=response_text,
            converted_value=response_text,
            conversation_id=request_piece.conversation_id,
            id=uuid.uuid4(),
        )
        return PromptRequestResponse(request_pieces=[response_piece])

    def _validate_request(self, *, prompt_request: PromptRequestResponse) -> None:
        if len(prompt_request.request_pieces) != 1:
            raise ValueError("ClaraTarget solo admite un fragmento de prompt por request.")
