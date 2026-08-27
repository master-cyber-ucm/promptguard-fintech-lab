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
        return (data.get("message") or {}).get("content", "").strip()
