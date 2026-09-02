# PromptGuard FinTech Lab — comandos principales
#
# Flujo normal:
#   make suite                  → envía fixtures al agente, guarda Session Files
#   make evaluate               → evalúa todos los runs pendientes
#   make report                 → genera run.md + run.json
#
#   make eval-all-steps         → encadena los tres pasos anteriores
#
# Evaluación por modelo:
#   make eval MODEL=mistral:7b  → pull + suite (ollama Docker)
#   make eval-all               → todos los modelos de models.txt
#   make eval-local MODEL=...   → como eval pero con ollama en el host

COMPOSE       = docker compose
BACKEND       = promptguard-backend
FIXTURES      = /app/tests/fixtures
RUN_MODEL     = qwen2.5:3b
BACKEND_PORT  ?= 8000
FRONTEND_PORT ?= 3000

JUDGE_TIMEOUT ?= 300
LEVEL         ?= evaluation

# Procedencia de git: el contenedor no monta el repositorio (solo `src`, `scripts` y
# `audit`), así que el commit se inyecta desde el host. Sin esto, `provenance.json`
# saldría sin commit y el run no sería reproducible ni agregable (P14).
GIT_COMMIT      := $(shell git rev-parse HEAD 2>/dev/null)
GIT_BRANCH      := $(shell git rev-parse --abbrev-ref HEAD 2>/dev/null)
GIT_DIRTY_FILES := $(shell git status --porcelain 2>/dev/null | grep -c . )
GIT_DIRTY       := $(shell test "$(GIT_DIRTY_FILES)" -gt 0 2>/dev/null && echo true || echo false)
GIT_ENV          = -e GIT_COMMIT=$(GIT_COMMIT) -e GIT_BRANCH=$(GIT_BRANCH) \
                   -e GIT_DIRTY=$(GIT_DIRTY) -e GIT_DIRTY_FILES=$(GIT_DIRTY_FILES)
REPEAT        ?= 1
MODELS_FILE   ?= models.txt
# Matriz principal del TFM. El canal documental entra con sus propias posturas: sin él,
# once fixtures (seis ataques de inyección indirecta y cinco legítimos sobre documentos
# benignos) quedaban cargados y nunca ejecutados — ver P10.
# SUITE_ENDPOINTS   ?= simple-prompt complex-prompt complex-with-context proxy complex-with-document
SUITE_ENDPOINTS   ?= simple-prompt complex-prompt complex-with-context proxy
PROXY_PROFILES    ?= baseline full
DOCUMENT_PROFILES ?= document-baseline document-full

.PHONY: up down restart restart-backend restart-front \
        logs logs-backend run suite check-suite \
        evaluate report final-report eval-all-steps \
        eval eval-all eval-local eval-all-local \
        smoke test help

# ──────────────────────────────────────────────────────────────────────────────
# Infraestructura
# ──────────────────────────────────────────────────────────────────────────────

run:
	@printf 'LOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://ollama:11434/v1\nOLLAMA_MODEL=$(RUN_MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
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

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

restart: restart-backend restart-front

restart-backend:
	$(COMPOSE) restart backend

restart-front:
	$(COMPOSE) restart frontend

logs:
	$(COMPOSE) logs -f

logs-backend:
	$(COMPOSE) logs -f backend

# ──────────────────────────────────────────────────────────────────────────────
# Suite de ataques
# ──────────────────────────────────────────────────────────────────────────────

# Envía los fixtures al agente y guarda Session Files en audit/runs/. La matriz
# incluye los tres escenarios de prompt y cuatro posturas del mismo proxy.
# Se puede acotar sin crear comandos nuevos, p. ej.:
#   make suite SUITE_ENDPOINTS="proxy" PROXY_PROFILES="baseline full"
#   make suite
#   make suite ARGS="--kind attack-prompts"
#   make suite ARGS="--id atk_001"
#   make suite REPEAT=5
# suite:
# 	$(COMPOSE) exec \
# 		-e FIXTURES_DIR=$(FIXTURES) \
# 		$(GIT_ENV) \
# 		backend \
# 		python scripts/run_attack_suite.py --repeat $(REPEAT) \
# 			$(foreach endpoint,$(SUITE_ENDPOINTS),--endpoint $(endpoint)) \
# 			$(foreach profile,$(PROXY_PROFILES),--proxy-profile $(profile)) \
# 			$(foreach profile,$(DOCUMENT_PROFILES),--document-profile $(profile)) $(ARGS)

suite:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		$(GIT_ENV) \
		backend \
		python scripts/run_attack_suite.py --repeat $(REPEAT) \
			$(foreach endpoint,$(SUITE_ENDPOINTS),--endpoint $(endpoint)) \
			$(foreach profile,$(PROXY_PROFILES),--proxy-profile $(profile)) $(ARGS)

# Reconcilia el Run Folder contra su Plan de cobertura sellado: cada ejecución
# planificada debe tener exactamente un estado terminal, aunque sea un error técnico.
# Niveles acumulativos: plan | execution | evidence | evaluation.
#   make check-suite RUN=20260827_133926_qwen2.5-3b
#   make check-suite RUN=X LEVEL=execution
#   make check-suite RUN=X CHECK_ARGS=--json
check-suite:
	@if [ -z "$(RUN)" ]; then echo "RUN es obligatorio: make check-suite RUN=<Run Folder>"; exit 2; fi
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/check_suite_run.py --run $(RUN) --level $(LEVEL) $(CHECK_ARGS)

# ──────────────────────────────────────────────────────────────────────────────
# Evaluación
# ──────────────────────────────────────────────────────────────────────────────

# Evalúa los Session Files usando el bloque evaluation: de cada fixture.
# Aplica DeterministicEvaluator o LLMEvaluator según el método definido.
#
#   make evaluate                             → todos los runs pendientes
#   make evaluate FORCE=1                     → re-evalúa todos los runs
#   make evaluate RUN=audit/runs/20260628_X/  → run específico (forzado)
evaluate:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		-e JUDGE_TIMEOUT=$(JUDGE_TIMEOUT) \
		backend \
		python scripts/evaluate.py \
		$(if $(RUN),--run $(RUN),) \
		$(if $(FORCE),--force,) \
		$(ARGS)

# Genera run.json + run.md a partir de las secciones ## Evaluación · de los Session Files.
#
#   make report                               → runs con evaluación y sin run.md
#   make report FORCE=1                       → regenera todos los reports
#   make report RUN=audit/runs/20260628_X/    → run específico (forzado)
report:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend \
		python scripts/report.py \
		$(if $(RUN),--run $(RUN),) \
		$(if $(FORCE),--force,) \
		$(ARGS)

# Consolida Run Folders ya evaluados.
final-report:
	@if [ -z "$(RUNS)" ]; then echo "RUNS es obligatorio: make final-report RUNS='run_a run_b'"; exit 2; fi
	$(COMPOSE) exec backend python scripts/final_report.py \
		$(foreach run,$(RUNS),--run $(run)) --output audit/final-results.md

# Encadena evaluate + report sobre todos los runs pendientes
eval-all-steps:
	$(MAKE) --no-print-directory evaluate
	$(MAKE) --no-print-directory report

# ──────────────────────────────────────────────────────────────────────────────
# Evaluación por modelo (ollama en Docker)
# ──────────────────────────────────────────────────────────────────────────────

# Pull + restart + suite para un modelo concreto
#   make eval MODEL=mistral:7b
#   make eval MODEL=qwen2.5:3b ARGS="--kind attack-prompts"
eval:
	@if [ -z "$(MODEL)" ]; then \
		echo ""; \
		echo "  Error: MODEL es obligatorio."; \
		echo "  Uso:   make eval MODEL=mistral:7b"; \
		echo ""; \
		exit 1; \
	fi
	@printf 'LOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://ollama:11434/v1\nOLLAMA_MODEL=$(MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
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

# Todos los modelos de models.txt
#   make eval-all
#   make eval-all MODELS_FILE=otra.txt
eval-all:
	@if [ ! -f "$(MODELS_FILE)" ]; then \
		echo ""; \
		echo "  Error: fichero de modelos no encontrado: $(MODELS_FILE)"; \
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ▶ Evaluación en lote · $(MODELS_FILE)"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r m; do echo "      $$m"; done
	@echo "══════════════════════════════════════════════════════════════════════"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r model; do \
		echo ""; \
		echo "  ▶ Iniciando: $$model"; \
		$(MAKE) --no-print-directory eval MODEL=$$model REPEAT=$(REPEAT) ARGS="$(ARGS)" < /dev/null || \
			echo "  ⚠ Error evaluando $$model — continuando con el siguiente"; \
	done
	@echo ""
	@echo "  ✅ Suite completada. Siguiente: make eval-all-steps"

# ──────────────────────────────────────────────────────────────────────────────
# Evaluación por modelo (ollama en el host)
# ──────────────────────────────────────────────────────────────────────────────

eval-local:
	@if [ -z "$(MODEL)" ]; then \
		echo ""; \
		echo "  Error: MODEL es obligatorio."; \
		echo "  Uso:   make eval-local MODEL=mistral:7b"; \
		echo ""; \
		exit 1; \
	fi
	@printf 'LOG_LEVEL=INFO\nLLM_PROVIDER=ollama\nOLLAMA_BASE_URL=http://host.docker.internal:11434/v1\nOLLAMA_MODEL=$(MODEL)\nOLLAMA_API_KEY=ollama\nBACKEND_PORT=$(BACKEND_PORT)\nFRONTEND_PORT=$(FRONTEND_PORT)\n' > .env
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
		echo ""; \
		exit 1; \
	fi
	@echo ""
	@echo "══════════════════════════════════════════════════════════════════════"
	@echo "  ▶ Evaluación en lote (ollama local) · $(MODELS_FILE)"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r m; do echo "      $$m"; done
	@echo "══════════════════════════════════════════════════════════════════════"
	@grep -v '^\s*#' "$(MODELS_FILE)" | grep -v '^\s*$$' | while IFS= read -r model; do \
		echo ""; \
		echo "  ▶ Iniciando: $$model"; \
		$(MAKE) --no-print-directory eval-local MODEL=$$model REPEAT=$(REPEAT) ARGS="$(ARGS)" < /dev/null || \
			echo "  ⚠ Error evaluando $$model — continuando con el siguiente"; \
	done
	@echo ""
	@echo "  ✅ Suite completada. Siguiente: make eval-all-steps"

# ──────────────────────────────────────────────────────────────────────────────
# Misc
# ──────────────────────────────────────────────────────────────────────────────

smoke:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend python scripts/smoke_test.py

test:
	$(COMPOSE) exec \
		-e FIXTURES_DIR=$(FIXTURES) \
		backend python -m pytest tests/ -v

help:
	@echo ""
	@echo "  Infraestructura"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make run                               Cold start (ollama Docker)"
	@echo "  make up / down / restart               Gestión de contenedores"
	@echo "  make logs / logs-backend               Seguir logs"
	@echo ""
	@echo "  Suite de ataques"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make suite                             Matriz principal (sin documentos)"
	@echo "  make suite ARGS='--kind attack-prompts'  Solo ataques"
	@echo "  make suite ARGS='--id atk_001'           Un fixture concreto"
	@echo "  make suite REPEAT=5                    5 repeticiones por fixture"
	@echo "  make suite SUITE_ENDPOINTS='proxy' PROXY_PROFILES='baseline full'  Matriz acotada"
	@echo ""
	@echo "  Evaluación"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make evaluate                          Evalúa todos los runs pendientes"
	@echo "  make evaluate FORCE=1                  Re-evalúa todos los runs"
	@echo "  make evaluate RUN=audit/runs/X/        Run específico"
	@echo "  make report                            Genera run.md + run.json"
	@echo "  make report FORCE=1                    Regenera todos los reports"
	@echo "  make report RUN=audit/runs/X/          Run específico"
	@echo "  make final-report RUNS='X Y'           Consolida runs en audit/final-results.md"
	@echo "  make eval-all-steps                    evaluate + report (pendientes)"
	@echo ""
	@echo "  Por modelo (ollama Docker)"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make eval MODEL=mistral:7b             pull + suite"
	@echo "  make eval-all                          Todos los modelos de models.txt"
	@echo "  make eval-all MODELS_FILE=otra.txt     Lista alternativa"
	@echo ""
	@echo "  Por modelo (ollama local)"
	@echo "  ─────────────────────────────────────────────────────────────────"
	@echo "  make eval-local MODEL=mistral:7b       pull + suite (host ollama)"
	@echo "  make eval-all-local                    Todos los modelos (host ollama)"
	@echo ""
	@echo "  make smoke                             Smoke test del stack"
	@echo ""
