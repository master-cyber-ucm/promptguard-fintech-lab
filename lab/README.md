# PromptGuard FinTech Lab

Lab vulnerable para simular ataques y defensas en un entorno bancario con IA generativa.

## Objetivo

El lab expone un asistente bancario, `Clara`, con tools mock y datos sintéticos para que el equipo pueda trabajar en:

- Ataques de prompt injection, jailbreak y leakage.
- Abuso de tools y confused deputy.
- Defensas por redacción, control de permisos y monitorización.

La arquitectura soporta:

- `Ollama` local.
- `OpenRouter` cloud.
- Cualquier proxy OpenAI-compatible en modo `custom` si se necesita más adelante.

## Requisitos

- Docker y Docker Compose.
- Python 3.11+ si quieres ejecutar los scripts de comprobación fuera de Docker.
- Ollama local si vas a usar el modo `ollama`.
- API key de OpenRouter si vas a usar el modo `openrouter`.

## Arranque rapido

1. Copia la plantilla de entorno:

```bash
cp .env.example .env
```

2. Elige el proveedor:

- `LLM_PROVIDER=ollama` para local.
- `LLM_PROVIDER=openrouter` para cloud.
- `LLM_PROVIDER=custom` si quieres apuntar a un proxy compatible como LiteLLM.

3. Levanta el stack:

```bash
docker compose up --build
```

4. Abre:

- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

## Modo Ollama

1. Arranca Ollama en el host:

```bash
ollama serve
```

2. Descarga el modelo:

```bash
ollama pull qwen3.5:9b
```

3. Deja estas variables en `.env`:

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
OLLAMA_MODEL=qwen3.5:9b
OLLAMA_API_KEY=ollama
```

## Modo OpenRouter

1. Crea una API key en `https://openrouter.ai/keys`.
2. Usa estas variables:

```bash
LLM_PROVIDER=openrouter
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=meta-llama/llama-3.3-70b-instruct:free
OPENROUTER_API_KEY=sk-or-v1-TU_API_KEY_AQUI
```

3. Puedes comprobar la key con:

```bash
../openrouter.sh
```

## Modo custom

Si el equipo quiere interponer LiteLLM u otro proxy compatible, usa:

```bash
LLM_PROVIDER=custom
LLM_BASE_URL=http://localhost:4000/v1
LLM_MODEL=clara-local
LLM_API_KEY=sk-local
```

Ese modo no es obligatorio para arrancar el lab. Está pensado para introducir un proxy sin tocar el backend.

## Verificacion

Comprueba primero el acceso al proveedor:

```bash
python scripts/check_providers.py --provider all
```

Luego ejecuta el smoke test end-to-end:

```bash
python scripts/smoke_test.py
```

## Ataques

Ejecuta la suite completa:

```bash
python scripts/run_attack_suite.py
```

Filtros utiles:

```bash
python scripts/run_attack_suite.py --type DIRECT_INJECTION
python scripts/run_attack_suite.py --id atk_004
python scripts/run_attack_suite.py --user usr_003
```

## Usuarios mock

- `usr_001` - María García López
- `usr_002` - Carlos Rodríguez Martín
- `usr_003` - Ana Fernández Ruiz
- `usr_admin` - Admin Banco

## Datos mock relevantes

- Cuentas y saldos sintéticos en `lab/backend/src/models/banking.py`.
- Transacciones sintéticas en `lab/backend/src/models/banking.py`.
- Prompts de ataque y prompts legítimos en `lab/backend/tests/fixtures/`.

## Endpoints utiles

- `GET /api/v1/health`
- `GET /api/v1/health/llm`
- `GET /api/v1/accounts`
- `GET /api/v1/users`
- `GET /api/v1/transactions/{user_id}`
- `POST /api/v1/chat`

## Troubleshooting

- Si usas Ollama y falla la conexion, comprueba que `ollama serve` sigue activo.
- Si OpenRouter devuelve `401`, revisa `OPENROUTER_API_KEY`.
- Si el backend arranca pero el proveedor no responde, usa `python scripts/check_providers.py` para aislar el fallo.
