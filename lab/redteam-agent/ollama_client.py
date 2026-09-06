"""Cliente mínimo para el Modelo atacante — habla con Ollama directamente (API nativa
/api/chat), independiente del backend del lab. El modelo atacante es un parámetro de
Campaña separado del modelo que sirve a Clara (ver ADR 0008 y CONTEXT.md).
"""

from __future__ import annotations

import httpx


class OllamaClient:
    def __init__(self, base_url: str, model: str, temperature: float = 0.9, max_tokens: int = 256) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(self, messages: list[dict], *, temperature: float | None = None) -> str:
        """Envía `messages` ([{role, content}]) y devuelve el texto de la respuesta."""
        resp = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                # La familia qwen3.5 tiene modo "thinking" activado por defecto: si no se
                # desactiva, el modelo puede gastar todo `num_predict` razonando y devolver
                # `message.content` VACÍO (el texto real queda en `message.thinking`) — visto
                # de verdad en la campaña de 6 técnicas del 2026-09-06 (fusión con Red Team_):
                # las 5 técnicas sin semilla de Garak generaron el fallback fijo de
                # `attacker.py::_extraer_payload` en TODOS los intentos porque `chat()`
                # devolvía "". Mismo bug que ya había documentado y evitado
                # `Red Team_/attack_loop.py::ollama_generate()` para este mismo modelo.
                "think": False,
                "options": {
                    "temperature": temperature if temperature is not None else self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
            # Modelos grandes en hardware sin GPU dedicada pueden tardar minutos por llamada
            # (medido: qwen3.5:9b ~170s en caliente, más bajo carga concurrente con el target) —
            # ver README.md § Alcance. 120s cortaba llamadas válidas, no solo cuelgues reales.
            timeout=300.0,
        )
        resp.raise_for_status()
        data = resp.json()
        message = data.get("message") or {}
        contenido = (message.get("content") or "").strip()
        if contenido:
            return contenido
        # Defensivo: si pese a `think: False` el modelo sigue devolviendo el texto útil por
        # `thinking` (visto en algunas versiones de Ollama con esta familia de modelos), no lo
        # descartamos — es mejor que caer siempre al fallback fijo de `_extraer_payload`.
        return (message.get("thinking") or "").strip()
