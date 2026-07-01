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
#   make suite           Envía fixtures al chat y persiste Session Files en Run Folder
#   make suite ARGS="--kind attack-prompts"  Filtros adicionales
#   make smoke           Smoke test del stack
#
# Evaluación (flujo recomendado tras make suite):
#   make eval-det                    Evaluación determinista en todos los pending runs
#   make eval-det RUN=<path>         Run específico (forzado)
#   make eval-det FORCE=1            Re-evalúa todos los runs
#   make eval-judge                  Evaluación por juez LLM en todos los pending runs
#   make eval-judge RUN=<path>       Run específico (forzado)
#   make eval-judge FORCE=1          Re-evalúa todos los runs
#   make report                      Genera run.md + run.json comparando ambos evaluadores
#   make report RUN=<path>           Run específico (forzado)
#   make report FORCE=1              Regenera todos los reports
#   make eval-all-steps              Encadena eval-det + eval-judge + report (pending runs)

COMPOSE       = docker compose
BACKEND       = promptguard-backend
FIXTURES      = /app/tests/fixtures
RUN_MODEL     = qwen2.5:3b
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000

# Timeout del juez en segundos (sobreescribible: make analyze-judge JUDGE_TIMEOUT=30)
JUDGE_TIMEOUT ?= 300
# Repeticiones por fixture para media estadística (sobreescribible: make suite REPEAT=5)
REPEAT        ?= 1
# Fichero de lista de modelos para eval-all (sobreescribible: make eval-all MODELS_FILE=otra.txt)
MODELS_FILE   ?= models.txt

.PHONY: run up down restart restart-backend restart-front \
        logs logs-backend suite \
        eval-det eval-judge report eval-all-steps \
        smoke eval eval-all eval-local eval-all-local help

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
		python scripts/run_attack_suite.py --repeat $(REPEAT) $(ARGS)

## Evaluación dual (determinista + juez + report)

# eval-det — evaluación determinista (eventos lógicos)
#   make eval-det                    → todos los runs pendientes
#   make eval-det FORCE=1            → re-evalúa todos los runs
#   make eval-det RUN=audit/runs/X/  → run específico (forzado)
eval-det:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/evaluate_deterministic.py \
		$(if $(RUN),--run $(RUN),) \
		$(if $(FORCE),--force,) \
		$(ARGS)

# eval-judge — evaluación por juez LLM
#   make eval-judge                  → todos los runs pendientes
#   make eval-judge FORCE=1          → re-evalúa todos los runs
#   make eval-judge RUN=audit/runs/X/  → run específico (forzado)
eval-judge:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		-e JUDGE_TIMEOUT=$(JUDGE_TIMEOUT) \
		backend \
		python scripts/evaluate_judge.py \
		$(if $(RUN),--run $(RUN),) \
		$(if $(FORCE),--force,) \
		$(ARGS)

# report — genera run.md + run.json combinando ambos evaluadores
#   make report                      → runs que tienen ambas evaluaciones pero no run.md
#   make report FORCE=1              → regenera todos los reports
#   make report RUN=audit/runs/X/    → run específico (forzado)
report:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/build_report.py \
		$(if $(RUN),--run $(RUN),) \
		$(if $(FORCE),--force,) \
		$(ARGS)

# eval-all-steps — encadena los tres pasos sobre todos los runs pendientes
eval-all-steps:
	$(MAKE) --no-print-directory eval-det
	$(MAKE) --no-print-directory eval-judge
	$(MAKE) --no-print-directory report

smoke:
	$(COMPOSE) exec backend python scripts/smoke_test.py

## Evaluación por modelo

# Uso: make eval MODEL=mistral:7b
# Uso: make eval MODEL=qwen2.5:3b ARGS="--kind attack-prompts"
eval:
	@if [ -z "$(MODEL)" ]; then \
		echo ""; \
		echo "  Error: MODEL es obligatorio."; \
		echo "  Uso:   make eval MODEL=mistral:7b"; \
		echo ""; \
		exit 1; \
	fi
	@printf 'APP_MODE=vulnerable\nLOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://ollama:11434/v1\nOLLAMA_MODEL=$(MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
	@echo ""
	@echo "  ▶ Modelo    : $(MODEL)"
	@echo "  ▶ Descargando modelo en ollama (si no existe)..."
	$(COMPOSE) exec ollama ollama pull $(MODEL)
	@echo "  ▶ Reiniciando backend con el nuevo modelo..."
	$(COMPOSE) up -d --build backend
	@echo "  ▶ Esperando backend..."
	@until $(COMPOSE) exec -T backend python -c \
		"import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" \
		> /dev/null 2>&1; do sleep 3; done
	@echo "  ▶ Backend listo. Lanzando suite..."
	@echo ""
	$(COMPOSE) exec -T \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/run_attack_suite.py --repeat $(REPEAT) $(ARGS)

eval-all:
	@if [ ! -f "$(MODELS_FILE)" ]; then \
		echo ""; \
		echo "  Error: fichero de modelos no encontrado: $(MODELS_FILE)"; \
		echo "  Uso:   make eval-all [MODELS_FILE=mi-lista.txt]"; \
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ▶ Evaluación en lote · $(MODELS_FILE)"
	@echo "  ▶ Modelos a evaluar:"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r m; do echo "      $$m"; done
	@echo "══════════════════════════════════════════════════════════════════════"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r model; do \
		echo ""; \
		echo "══════════════════════════════════════════════════════════════════════"; \
		echo "  ▶ Iniciando: $$model"; \
		echo "══════════════════════════════════════════════════════════════════════"; \
		$(MAKE) --no-print-directory eval MODEL=$$model REPEAT=$(REPEAT) JUDGE_TIMEOUT=$(JUDGE_TIMEOUT) ARGS="$(ARGS)" < /dev/null || { \
			echo "  ⚠ Error evaluando $$model — continuando con el siguiente"; \
		}; \
	done
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ✅ Suite completada para todos los modelos."
	@echo "  📁 Run Folders pendientes en: lab/audit/runs/"
	@echo "  ▶ Siguiente paso: make analyze          (heurística)"
	@echo "  ▶                 make analyze-judge    (heurística + juez LLM)"
	@echo "══════════════════════════════════════════════════════════════════════"

## Evaluación por modelo — Ollama local (host)

# Uso: make eval-local MODEL=mistral:7b
# Uso: make eval-local MODEL=qwen2.5:3b ARGS="--kind attack-prompts"
eval-local:
	@if [ -z "$(MODEL)" ]; then \
		echo ""; \
		echo "  Error: MODEL es obligatorio."; \
		echo "  Uso:   make eval-local MODEL=mistral:7b"; \
		echo ""; \
		exit 1; \
	fi
	@printf 'APP_MODE=vulnerable\nLOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://host.docker.internal:11434/v1\nOLLAMA_MODEL=$(MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
	@echo ""
	@echo "  ▶ Modelo    : $(MODEL)"
	@echo "  ▶ Descargando modelo en ollama local (si no existe)..."
	ollama pull $(MODEL)
	@echo "  ▶ Reiniciando backend con el nuevo modelo..."
	$(COMPOSE) up -d --build backend
	@echo "  ▶ Esperando backend..."
	@until $(COMPOSE) exec -T backend python -c \
		"import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" \
		> /dev/null 2>&1; do sleep 3; done
	@echo "  ▶ Backend listo. Lanzando suite..."
	@echo ""
	$(COMPOSE) exec -T \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/run_attack_suite.py --repeat $(REPEAT) $(ARGS)

eval-all-local:
	@if [ ! -f "$(MODELS_FILE)" ]; then \
		echo ""; \
		echo "  Error: fichero de modelos no encontrado: $(MODELS_FILE)"; \
		echo "  Uso:   make eval-all-local [MODELS_FILE=mi-lista.txt]"; \
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ▶ Evaluación en lote (ollama local) · $(MODELS_FILE)"
	@echo "  ▶ Modelos a evaluar:"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r m; do echo "      $$m"; done
	@echo "══════════════════════════════════════════════════════════════════════"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r model; do \
		echo ""; \
		echo "══════════════════════════════════════════════════════════════════════"; \
		echo "  ▶ Iniciando: $$model"; \
		echo "══════════════════════════════════════════════════════════════════════"; \
		$(MAKE) --no-print-directory eval-local MODEL=$$model REPEAT=$(REPEAT) JUDGE_TIMEOUT=$(JUDGE_TIMEOUT) ARGS="$(ARGS)" < /dev/null || { \
			echo "  ⚠ Error evaluando $$model — continuando con el siguiente"; \
		}; \
	done
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ✅ Suite completada para todos los modelos."
	@echo "  📁 Run Folders pendientes en: lab/audit/runs/"
	@echo "  ▶ Siguiente paso: make analyze          (heurística)"
	@echo "  ▶                 make analyze-judge    (heurística + juez LLM)"
	@echo "══════════════════════════════════════════════════════════════════════"

## Ayuda

help:
	@echo ""
	@echo "  Infraestructura"
	@echo "  ─────────────────────────────────────────────────────────────────────"
	@echo "  make up                                 Levanta toda la infra"
	@echo "  make down                               Para los contenedores"
	@echo "  make restart                            Reinicia backend y frontend"
	@echo "  make restart-backend                    Reinicia solo el backend"
	@echo "  make restart-front                      Reinicia solo el frontend"
	@echo "  make logs                               Sigue todos los logs"
	@echo "  make logs-backend                       Sigue los logs del backend"
	@echo "  make run                                Cold start con puertos por defecto"
	@echo "  make run BACKEND_PORT=9000              Backend en puerto 9000"
	@echo ""
	@echo "  Suite de ataques"
	@echo "  ─────────────────────────────────────────────────────────────────────"
	@echo "  make suite                              Envía todos los fixtures al agente"
	@echo "  make suite ARGS='--kind attack-prompts' Solo ataques"
	@echo "  make suite ARGS='--id atk_001'          Un fixture concreto"
	@echo "  make suite REPEAT=5                     5 repeticiones por fixture"
	@echo ""
	@echo "  Evaluación (flujo recomendado: eval-det → eval-judge → report)"
	@echo "  ─────────────────────────────────────────────────────────────────────"
	@echo "  make eval-det                           Eval. determinista (todos los pending runs)"
	@echo "  make eval-det FORCE=1                   Re-evalúa todos los runs"
	@echo "  make eval-det RUN=audit/runs/X/         Run específico (forzado)"
	@echo "  make eval-judge                         Eval. por juez LLM (todos los pending runs)"
	@echo "  make eval-judge FORCE=1                 Re-evalúa todos los runs"
	@echo "  make eval-judge RUN=audit/runs/X/       Run específico (forzado)"
	@echo "  make report                             Genera run.md+run.json (runs listos sin report)"
	@echo "  make report FORCE=1                     Regenera todos los reports"
	@echo "  make report RUN=audit/runs/X/           Run específico (forzado)"
	@echo "  make eval-all-steps                     Encadena los tres pasos (pending runs)"
	@echo ""
	@echo "  Evaluación por modelo"
	@echo "  ─────────────────────────────────────────────────────────────────────"
	@echo "  make eval MODEL=mistral:7b              pull + restart + suite (ollama Docker)"
	@echo "  make eval MODEL=qwen2.5:3b ARGS='--kind attack-prompts'  Solo ataques"
	@echo "  make eval-all                           Todos los modelos de models.txt"
	@echo "  make eval-all MODELS_FILE=otra.txt      Lista alternativa"
	@echo "  make eval-local MODEL=mistral:7b        Como eval pero con ollama local (host)"
	@echo "  make eval-all-local                     Todos los modelos (ollama local)"
	@echo ""
	@echo "  Misc"
	@echo "  ─────────────────────────────────────────────────────────────────────"
	@echo "  make smoke                              Smoke test del stack"
	@echo ""
