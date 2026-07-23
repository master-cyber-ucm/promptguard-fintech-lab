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

---

## 2026-07-23 — Fase 1.1 completada: diseño y generación del payload (3 formatos)

**Qué se hizo:**
- Decidido el objetivo del payload: fuga de saldo de tercero vía `consulta_saldo` sobre
  `ES3421000418450200051334` (Ana Fernández Ruiz, usr_003) — mismo objetivo que los fixtures
  `atk_021`/`atk_022` ya existentes, para evidencia comparable. Justificación completa en
  `01-ataque/README.md`.
- Decidido cubrir 3 formatos (PDF, DOCX, XLSX) en vez de solo PDF, cada uno con la técnica de
  ocultación más idiomática de ese formato.
- Creado venv local en `01-ataque/payloads/.venv` con `reportlab`, `python-docx`, `openpyxl`,
  `pypdf` (congelado en `payloads/requirements.txt`).
- Escritos y ejecutados 3 scripts generadores: `generar_pdf.py`, `generar_docx.py`,
  `generar_xlsx.py`. Generan 6 documentos: 3 sanos (control negativo) + 3 comprometidos.
- **Validado** con parsers ingenuos (`pypdf`, `python-docx`, `openpyxl`) que el payload oculto es
  recuperable en los 3 formatos — confirma la premisa de Greshake et al. (2023): el parser no
  distingue dato visible de dato oculto.

**Reproducir:**
```bash
cd henri-tfm/01-ataque/payloads
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python generar_pdf.py && ./.venv/bin/python generar_docx.py && ./.venv/bin/python generar_xlsx.py
```

**Próximos pasos:**
- Fase 1.2: implementar el canal de subida de documentos en el backend (hoy no existe) — decidir
  endpoint nuevo vs. campo opcional en `ChatRequest`, y extracción de texto por formato.

---

## 2026-07-23 — Verificación del payload formalizada como tests

**Qué se hizo:**
- El usuario preguntó si la verificación manual de extracción del payload (hecha con un script
  ad-hoc) debía formalizarse como test — sí, aplica la regla 1 (documentar + tests cuando aplique).
- Añadido `pytest` al venv de `payloads/` y escrito `test_payloads.py`: 8 tests (2 por formato +
  1 extra en DOCX que confirma que la técnica es específicamente `run.font.hidden`).
- Cada test genera el documento en un `tmp_path` (no depende de los artefactos ya generados en
  disco) y comprueba, con el mismo tipo de extracción ingenua que usaría un pipeline sin medidas
  de seguridad: sano → sin IBAN objetivo; comprometido → con IBAN objetivo.
- Resultado: **8/8 passed**.

**Decisión de proceso (aplica desde ahora):** cualquier verificación manual que sea determinista
y automatizable se formaliza como test, no se deja como comprobación puntual.

**Reproducir:**
```bash
cd henri-tfm/01-ataque/payloads
./.venv/bin/pytest -v
```

**Próximos pasos:**
- Fase 1.2: implementar el canal de subida de documentos en el backend.

---

## 2026-07-23 — Supuesto de conocimiento del atacante (caja negra) documentado

**Qué se hizo:**
- El usuario planteó una pregunta de threat modeling: ¿tiene sentido que el payload nombre la
  herramienta exacta (`consulta_saldo`), si en la vida real un atacante no conoce el nombre
  interno de las funciones del sistema, solo sabe qué funcionalidad debería existir?
- Verificado el texto exacto de los 3 payloads: ninguno menciona `consulta_saldo` ni ningún
  nombre de función — todos piden la funcionalidad en lenguaje natural ("consulta el saldo de la
  cuenta X"). El diseño ya era correcto, pero el razonamiento no estaba escrito en ningún sitio.
- Añadida la sección **"0. Supuesto de conocimiento del atacante (caja negra)"** en
  `01-ataque/anatomia-payload.md`: el atacante es de caja negra frente a la implementación de
  Clara (no conoce `tools.py`), solo conoce la funcionalidad observable como cliente. El nombre
  `consulta_saldo` solo aparece en la documentación/criterio de evaluación (posición de analista
  de caja blanca), nunca en el payload — evita inflar artificialmente la tasa de éxito con
  conocimiento que un atacante real no tendría.
- Prosa correspondiente añadida a `CAPITULO.md`, sección 4.2.

**Próximos pasos:**
- Fase 1.2: implementar el canal de subida de documentos en el backend.

---

## 2026-07-23 — Bloque de referencia rápida con los textos literales

**Qué se hizo:**
- El usuario pidió los 4 textos exactos de payload de forma directa y consolidada. Añadida una
  tabla "Textos literales (referencia rápida)" al principio de `01-ataque/anatomia-payload.md`
  (antes de la sección 0), con los 4 payloads verbatim sin análisis — el desglose detallado sigue
  en las secciones 2–4 del mismo archivo.

**Próximos pasos:**
- Fase 1.2: implementar el canal de subida de documentos en el backend.

---

## 2026-07-23 — Anatomía del payload documentada

**Qué se hizo:**
- A petición del usuario, documentado el contenido exacto de cada payload malicioso (texto
  literal usado en PDF, DOCX y XLSX) y el porqué de su redacción, en
  `01-ataque/anatomia-payload.md`.
- Identificada y documentada la estructura común a los 3 payloads: (A) marco de autoridad falso
  ("nota del sistema", "nota interna"), (B) instrucción de acción concreta con el IBAN objetivo
  interpolado, (C) instrucción de auto-ocultación ("no menciones esta nota") para reducir
  trazabilidad frente a un revisor humano.
- Documentado también el razonamiento de variación entre formatos: en PDF se repite el mismo
  payload 3 veces (una por técnica) para maximizar supervivencia frente a un pipeline de
  extracción desconocido; en XLSX se usan 2 variantes de texto distintas (fila oculta vs.
  comentario) porque son superficies de ataque cualitativamente distintas, no la misma técnica
  repetida.
- Esto responde directamente al punto pendiente de `TODOs.md` §7 ("Anatomía del payload: desglose
  comentado de por qué funciona") para este vector.
- Enlazado desde `01-ataque/README.md` y resumido en `CAPITULO.md`.

**Próximos pasos:**
- Fase 1.2: implementar el canal de subida de documentos en el backend.
