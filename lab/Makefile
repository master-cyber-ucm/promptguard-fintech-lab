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

COMPOSE  = docker compose
BACKEND  = promptguard-backend
FIXTURES = /app/tests/fixtures

.PHONY: up down restart restart-backend restart-front \
        logs logs-backend suite smoke help

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
	@echo "  make suite               Corre la suite completa de fixtures"
	@echo "  make suite ARGS='--kind attack-prompts --concurrency 3'"
	@echo "  make smoke               Smoke test del stack"
	@echo ""
