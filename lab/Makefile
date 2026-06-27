# PromptGuard FinTech Lab — comandos principales
#
# Uso:
#   make up              Levanta toda la infra (build si hay cambios)
#   make down            Para y elimina los contenedores
#   make restart         Reinicia backend y frontend
#   make restart-backend Reinicia solo el backend
#   make restart-front   Reinicia solo el frontend
#   make logs            Sigue los logs de todos los servicios
#   make logs-backend    Sigue los logs del backend
#   make suite           Corre la suite de ataques completa dentro del backend
#   make suite ARGS="--kind attack-prompts --concurrency 3"
#   make smoke           Smoke test del stack

COMPOSE      = docker compose
BACKEND      = promptguard-backend
FIXTURES     = /app/tests/fixtures
RUN_MODEL    = qwen2.5:3b
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 3000

.PHONY: run up down restart restart-backend restart-front \
        logs logs-backend suite smoke help

## Cold start (evaluador / primera vez)

run:
	@printf 'APP_MODE=vulnerable\nLOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://ollama:11434/v1\nOLLAMA_MODEL=$(RUN_MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
	@echo ".env configurado → modelo $(RUN_MODEL) | backend :$(BACKEND_PORT) | frontend :$(FRONTEND_PORT)"
	$(COMPOSE) --profile ollama up -d ollama
	@echo "Descargando modelo $(RUN_MODEL) (solo la primera vez)..."
	$(COMPOSE) exec ollama ollama pull $(RUN_MODEL)
	$(COMPOSE) up -d --build backend frontend
	@echo ""
	@echo "  Lab listo"
	@echo "  Frontend → http://localhost:$(FRONTEND_PORT)"
	@echo "  API      → http://localhost:$(BACKEND_PORT)"
	@echo "  Docs     → http://localhost:$(BACKEND_PORT)/docs"
	@echo ""

## Infraestructura

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: restart-backend restart-front

restart-backend:
	$(COMPOSE) restart backend

restart-front:
	$(COMPOSE) restart frontend

## Logs

logs:
	$(COMPOSE) logs -f

logs-backend:
	$(COMPOSE) logs -f backend

## Scripts

suite:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/run_attack_suite.py $(ARGS)

smoke:
	$(COMPOSE) exec backend python scripts/smoke_test.py

## Ayuda

help:
	@echo ""
	@echo "  make up                  Levanta toda la infra"
	@echo "  make down                Para los contenedores"
	@echo "  make restart             Reinicia backend y frontend"
	@echo "  make restart-backend     Reinicia solo el backend"
	@echo "  make restart-front       Reinicia solo el frontend"
	@echo "  make logs                Sigue todos los logs"
	@echo "  make logs-backend        Sigue los logs del backend"
	@echo "  make run                               Cold start con puertos por defecto"
	@echo "  make run BACKEND_PORT=9000             Backend en puerto 9000"
	@echo "  make run BACKEND_PORT=9000 FRONTEND_PORT=4000"
	@echo "  make suite               Corre la suite completa de fixtures"
	@echo "  make suite ARGS='--kind attack-prompts --concurrency 3'"
	@echo "  make smoke               Smoke test del stack"
	@echo ""
