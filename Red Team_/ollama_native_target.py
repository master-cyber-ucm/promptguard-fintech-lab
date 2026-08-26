"""
ollama_native_target.py

Target de PyRIT que interactúa con la API nativa de Ollama (/api/chat),
en lugar de la capa de compatibilidad OpenAI (/v1/chat/completions).

¿Por qué existe este archivo?
- El modelo qwen3.5:4b tiene un modo "thinking" que genera un razonamiento interno
  largo (miles de tokens) antes de responder. Este modo puede desactivarse
  con el parámetro `think: false`, pero **solo funciona en la API nativa de Ollama**.
  La capa de compatibilidad OpenAI ignora este parámetro.
- Usar la API nativa reduce el tiempo de respuesta de minutos a segundos,
  manteniendo la misma calidad de evaluación, pero sin gastar tiempo en el
  "diálogo interno" que no aporta a la puntuación.

Uso:
Se utiliza de la misma forma que `OpenAIChatTarget` en PyRIT: se pasa como
`chat_target` a un scorer (o como `objective_target` a un orchestrator).
"""

from __future__ import annotations

import uuid
import httpx

from pyrit.models import PromptRequestResponse, PromptRequestPiece
from pyrit.prompt_target import PromptChatTarget

class OllamaNativeTarget(PromptChatTarget):
    """Target de PyRIT para interactuar con la API nativa de Ollama (/api/chat).

    Permite desactivar el modo "thinking" para obtener respuestas rápidas.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model_name: str = "qwen3.5:4b",
        think: bool = False,
        timeout: float = 180.0,
    ) -> None:
        super().__init__()
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model_name = model_name
        self._think = think
        self._timeout = timeout

    async def send_prompt_async(
        self, *, prompt_request: PromptRequestResponse
    ) -> PromptRequestResponse:
        request_piece: PromptRequestPiece = prompt_request.request_pieces[0]

        # Recupera el historial completo de la conversación (útil para uso futuro como atacante multi-turno).
        conversation = self._memory.get_conversation(
            conversation_id=request_piece.conversation_id
        )
        messages = []
        for turn in conversation:
            piece = turn.request_pieces[0]
            messages.append({"role": piece.role, "content": piece.converted_value})

        # Si no hay historial previo en memoria, usa al menos el mensaje actual.
        if not messages:
            messages = [{"role": "user", "content": request_piece.converted_value}]

        payload = {
            "model":    self._model_name,
            "messages": messages,
            "stream":   False,
            "think":    self._think,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                r = await client.post(self._url, json=payload)
                r.raise_for_status()
                data = r.json()
                response_text = data.get("message", {}).get("content", "")
                if not response_text:
                    response_text = f"[RESPUESTA VACÍA] {data}"
            except Exception as e:
                print(f"[DEBUG] Error en la conexión con Ollama: {type(e).__name__}: {e}")
                response_text = f"[ERROR DE CONEXIÓN CON OLLAMA] {str(e)}"

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
            raise ValueError(
                "OllamaNativeTarget solo admite un fragmento de prompt por solicitud. "
                f"Se recibieron {len(prompt_request.request_pieces)} fragmentos."
            )

    def is_json_response_supported(self) -> bool:
        """Indica si este target soporta respuestas en formato JSON.

        Returns:
            bool: Siempre False, ya que OllamaNativeTarget no soporta respuestas JSON.
        """
        return False