#!/usr/bin/env bash
# Smoke test directo contra OpenRouter.
# Sirve para validar la API key y el modelo antes de levantar el lab.
#
# Uso:
#   export OPENROUTER_API_KEY="sk-or-v1-TU_API_KEY_AQUI"
#   ./openrouter.sh

set -euo pipefail

: "${OPENROUTER_API_KEY:?Falta OPENROUTER_API_KEY en el entorno. Obtén una en https://openrouter.ai/keys}"

MODEL="${OPENROUTER_MODEL:-meta-llama/llama-3.3-70b-instruct:free}"
BASE_URL="${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"

curl -sS "${BASE_URL}/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${OPENROUTER_API_KEY}" \
  -d "{
    \"model\": \"${MODEL}\",
    \"messages\": [
      {\"role\": \"user\", \"content\": \"Responde con una sola palabra: OK\"}
    ]
  }"
