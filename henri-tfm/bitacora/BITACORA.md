# Bitácora de trabajo — Ataque #7

> Una entrada por sesión de trabajo. Formato: qué se hizo, qué se decidió y por qué, próximos
> pasos. Sirve como registro de reproducibilidad y como base para el capítulo "Objetivos, alcance
> y metodología" (sección 3 del índice del TFM).

---

## 2026-07-19 — Setup del entorno de trabajo

**Qué se hizo:**
- Exploración completa del repo `promptguard-fintech-lab`: propuesta formal del TFM, README raíz
  y de `lab/`, `CONTEXT.md` (glosario), `TODOs.md`.
- Confirmado el ataque asignado: **#7 — Prompt Injection Indirecta vía Documento**
  (OWASP LLM01:2025 · MITRE ATLAS AML.T0051.001), en la rama `feature/henri-attack-7`.
- Localizada y leída la carpeta de referencia ya existente:
  `docs/ataques/LLM01-prompt-injection/indirecta-documento/` (README + 7 capítulos), todos
  marcados "PRE-implementación".
- Confirmado que el canal de subida de documentos **no existe** en el backend actual
  (`ChatRequest` solo acepta `message` de texto) — es un bloqueante de la Fase 1.
- Localizados los fixtures existentes que simulan el ataque por texto:
  `atk_021_indirect_doc_es.yaml`, `atk_022_indirect_doc_en_claude.yaml`.
- Creado el entorno de trabajo inicialmente en `/home/henri/TFM/henri/` (fuera del repo git).
- Corregido: movido a `henri-tfm/` en la **raíz del repo** (`promptguard-fintech-lab/henri-tfm/`),
  para que quede junto al proyecto y se commitee en la rama `feature/henri-attack-7`.

**Decisiones tomadas:**
- Los 7 capítulos de referencia se usan como plantilla/fuente, no se editan todavía.
- El TFM final seguirá el índice de 9 capítulos indicado por el usuario (ver
  `00-INSTRUCCIONES.md`, sección 2).
- Orden de trabajo fijo: Ataque → Defensa → Marco normativo (ver `ROADMAP.md`).
- La carpeta `henri-tfm/` vive en la raíz del repo y se sube al repositorio (no queda solo en
  local).

**Próximos pasos:**
- Verificar que `make run` levanta el lab en local.
- Empezar la Fase 1.1: diseño del payload bancario (documento sano vs. comprometido).

---

## 2026-07-23 — Lab levantado en local

**Qué se hizo:**
- Confirmado: `make run` levanta el stack en local (Ollama + backend + frontend) y se pudo entrar
  al playground.
- Corridos `make smoke` — detectados y arreglados 2 bugs preexistentes en infraestructura
  compartida (no específicos del ataque #7):
  1. `lab/scripts/smoke_test.py` llamaba a `POST /api/v1/chat`, endpoint que ya no existe (se
     dividió en `/chat/simple-prompt`, `/chat/complex-prompt`, `/chat/complex-with-context` en un
     refactor anterior). Corregido a `/chat/complex-with-context` (configuración vulnerable actual
     del lab).
  2. El target `smoke` del `Makefile` no pasaba `FIXTURES_DIR=/app/tests/fixtures` al contenedor
     (a diferencia de `suite`), por lo que `fixture_loader.py` no encontraba ningún fixture dentro
     del contenedor. Corregido añadiendo la misma variable de entorno.
  - Reproducir: `cd lab && make smoke` → ahora 4/4 pasos superados.
  - Commits pendientes de hacer en el repo (no específicos de mi carpeta personal):
    `lab/Makefile`, `lab/scripts/smoke_test.py`.

**Próximos pasos:**
- Empezar la Fase 1.1: diseño del payload bancario (documento sano vs. comprometido).
