# Imagen LiteLLM experimental para el lab PromptGuard.
#
# Se deja como referencia opcional si el equipo quiere montar un proxy
# OpenAI-compatible más adelante. El arranque por defecto del lab no depende
# de esta imagen.
#
# Imagen resultante: ~250 MB, arranca en ~2-3s.

FROM python:3.11-slim

ARG LITELLM_VERSION=1.40.0
RUN pip install --no-cache-dir "litellm[proxy]==${LITELLM_VERSION}"

WORKDIR /app
EXPOSE 4000

# --drop_params evita errores al pasar parámetros que algún proveedor no soporta
# (típico al cambiar Ollama ↔ OpenRouter).
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000", "--num_workers", "1", "--drop_params"]
