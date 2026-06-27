# PromptGuard FinTech Lab

Lab vulnerable para simular ataques y defensas en un entorno bancario con IA generativa.

## Objetivo

El lab expone un asistente bancario, `Clara`, con tools mock y datos sintéticos para:

- Ataques de prompt injection, jailbreak y leakage.
- Abuso de tools y confused deputy.
- Defensas por redacción, control de permisos y monitorización.

## Requisitos

- Docker y Docker Compose.

## Arranque rápido (cold start)

Un solo comando levanta Ollama, descarga el modelo y arranca el stack completo:

```bash
make run
```

Puertos por defecto: frontend `:3000`, backend `:8000`. Si hay conflicto:

```bash
make run BACKEND_PORT=9000 FRONTEND_PORT=4000
```

## Comandos disponibles

| Comando | Descripción |
|---------|-------------|
| `make run` | Cold start completo: genera `.env`, levanta Ollama, descarga modelo, arranca stack |
| `make run BACKEND_PORT=9000` | Cold start con puertos personalizados |
| `make up` | Levanta el stack (requiere `.env` configurado) |
| `make down` | Para y elimina los contenedores |
| `make restart` | Reinicia backend y frontend |
| `make logs` | Sigue los logs de todos los servicios |
| `make logs-backend` | Sigue solo los logs del backend |
| `make suite` | Corre la suite completa de fixtures |
| `make suite ARGS="--kind attack-prompts"` | Suite con filtros |
| `make smoke` | Smoke test del stack |

## Proveedores LLM

El backend habla con cualquier endpoint OpenAI-compatible. Cambia `LLM_PROVIDER` en `.env`:

### Ollama en Docker (por defecto con `make run`)

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://ollama:11434/v1
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_API_KEY=ollama
```

### Ollama en el host (manual)

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_API_KEY=ollama
```

Requiere `ollama serve` activo en el host y el modelo descargado: `ollama pull qwen2.5:3b`.

### OpenRouter

```bash
LLM_PROVIDER=openrouter
OPENROUTER_MODEL=meta-llama/llama-3.2-3b-instruct:free
OPENROUTER_API_KEY=sk-or-v1-TU_API_KEY_AQUI
```

### Groq

```bash
LLM_PROVIDER=custom
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=gsk_...
```

### NVIDIA NIM

```bash
LLM_PROVIDER=custom
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.2-3b-instruct
LLM_API_KEY=nvapi-...
```

## Verificación

```bash
make smoke
```

O directamente dentro del contenedor:

```bash
docker compose exec backend python scripts/check_providers.py --provider all
```

## Suite de ataques

```bash
make suite                                      # todos los fixtures
make suite ARGS="--kind attack-prompts"         # solo ataques
make suite ARGS="--type DIRECT_INJECTION"       # por tipo
make suite ARGS="--id atk_004"                  # fixture concreto
make suite ARGS="--concurrency 3"               # ejecución paralela
```

Los resultados se guardan en `lab/audit/runs/` (JSON + Markdown).

## Auditoría

Cada interacción con Clara genera un fichero `.md` en `lab/audit/sessions/` con:
- System prompt activo
- Prompt completo enviado al agente (con contexto de usuario inyectado)
- Razonamiento del modelo (si el modelo lo expone)
- Tools invocadas y sus argumentos
- Respuesta completa
- Latencia

## Usuarios mock

| ID | Nombre |
|----|--------|
| `usr_001` | María García López |
| `usr_002` | Carlos Rodríguez Martín |
| `usr_003` | Ana Fernández Ruiz |
| `usr_admin` | Admin Banco |

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check del backend |
| `GET` | `/api/v1/health/llm` | Health check del proveedor LLM |
| `GET` | `/api/v1/fixtures` | Lista todos los fixtures disponibles |
| `GET` | `/api/v1/accounts` | Cuentas mock |
| `GET` | `/api/v1/users` | Usuarios mock |
| `GET` | `/api/v1/transactions/{user_id}` | Transacciones mock |
| `POST` | `/api/v1/chat` | Chat con Clara |

## Troubleshooting

| Síntoma | Causa probable | Solución |
|---------|---------------|----------|
| Backend arranca pero LLM no responde | Proveedor no alcanzable | `make logs-backend` para ver el error; revisar `.env` |
| OpenRouter `401` | API key inválida | Verificar `OPENROUTER_API_KEY` |
| `make run` se cuelga en la descarga | Modelo pesado o conexión lenta | Esperar; la descarga solo ocurre la primera vez |
| Puerto ocupado | Conflicto de puertos | `make run BACKEND_PORT=9000 FRONTEND_PORT=4000` |
