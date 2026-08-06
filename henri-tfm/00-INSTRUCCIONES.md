# Instrucciones permanentes — TFM Henri — Ataque #7

> Este documento es el contexto que se debe leer (y mantener actualizado) al empezar cualquier sesión
> de trabajo sobre este TFM. Vive dentro del repo, en `henri-tfm/`, en la raíz del proyecto, y se
> commitea a la rama `feature/henri-attack-7` junto con el resto del trabajo.

## 0. Encuadre — qué es esto

Máster en Ciberseguridad — UCM. TFM colectivo: **PromptGuard FinTech** (evaluación y defensa de
ciberseguridad en un chatbot bancario basado en LLM). Cada alumno toma uno o varios ataques del
catálogo y los lleva de punta a punta: ataque → defensa → marco normativo.

**Repo del proyecto:** `/home/henri/Projects/promptguard-fintech-lab` (git, org
`master-cyber-ucm`). Esta carpeta (`henri-tfm/`) vive en su raíz.
**Rama de trabajo:** `feature/henri-attack-7`.
**Cómo levantar el lab:** `cd lab && make run` (cold start completo con Ollama local por defecto;
ver `lab/README.md` para otros proveedores — OpenRouter, Groq, NVIDIA NIM).

**Escenario ficticio:** VerdaBank S.A. (neobank español ficticio) y su asistente conversacional
**Clara**, construido con PydanticAI. Clara tiene acceso a 5 tools bancarias mock:
`consulta_saldo`, `transferencia_nacional`, `bloquear_tarjeta`, `consulta_producto`,
`abrir_reclamacion`. El incidente motivador del TFM (ficticio): un cliente manipuló a Clara para
filtrar el saldo de otro usuario vía manipulación de contexto (marzo 2025, brecha GDPR
Art. 33 notificada a la AEPD).

## 1. Ataque asignado — #7 del catálogo

**Prompt Injection Indirecta vía Documento**
`OWASP LLM01:2025` · `MITRE ATLAS AML.T0051.001 (Prompt Injection — Indirect)` · Táctica ATLAS
`TA0043 — Initial Access`.

**Resumen:** un cliente sube un documento (nómina, extracto) con instrucciones ocultas (texto
blanco sobre blanco, fuente 1pt, texto fuera del viewport, o metadatos). El backend extrae el
texto del documento y lo inyecta en el contexto del LLM **sin distinguirlo del prompt del
usuario**. El modelo ejecuta esas instrucciones ocultas como si fueran legítimas — típicamente
para filtrar datos de un tercero o forzar una tool bancaria no autorizada.

Es la variante **indirecta** de Prompt Injection (LLM01): el payload no viaja por el mensaje de
chat visible (eso sería la variante directa, ataque #2 del catálogo, ya cubierta por otro
compañero en `docs/ataques/LLM01-prompt-injection/directa/`), sino por un contenido que el
sistema procesa como **dato**.

### Estado real del lab a fecha de hoy (2026-07-19)

- El endpoint `POST /chat` (`lab/backend/src/api/routes/chat.py`) **no acepta documentos**:
  `ChatRequest` solo tiene `user_id`, `message`, `session_id` y campos de fixture/auditoría. No
  hay canal de subida de archivos.
- `lab/gen_adversarial_pdf.py` ya existe como utilidad base: genera un PDF con texto blanco sobre
  blanco y texto fuera del viewport, pero con un payload de RRHH (no bancario) y no está integrado
  en el flujo del lab.
- Ya existen fixtures que **simulan** el ataque pegando el "documento" como texto plano dentro del
  chat (`atk_021_indirect_doc_es.yaml`, `atk_022_indirect_doc_en_claude.yaml` en
  `lab/backend/tests/fixtures/LLM01-prompt-injection/indirecta-documento/`), pero esto **no es**
  subir un archivo real — es un sustituto textual mientras no existe el canal de subida.
- Para ejecutar el ataque *de verdad* (con un PDF/DOCX/XLSX real, como pide este TFM) hace falta
  **implementar el canal de subida + extracción de texto** primero. Esto está fuera del
  "Escenario Base" formal de la propuesta (pertenece a la Extensión 2 — Canal Multimodal), pero es
  imprescindible para este capítulo, así que se implementa como parte del trabajo de la Fase 1.

### Material de referencia ya existente en el repo (NO se edita todavía, solo se consulta)

Carpeta `docs/ataques/LLM01-prompt-injection/indirecta-documento/` — 7 capítulos + README, todos
marcados **"PRE-implementación"** (análisis teórico, sin payload ejecutado). Está muy bien
elaborado y sirve de plantilla/referencia directa para lo que hay que producir con evidencia real:

| Archivo | Contenido |
|---|---|
| `README.md` | Resumen del vector, defensa prevista, checklist de estado |
| `01-mapeo-taxonomico.md` | OWASP/ATLAS/NIST AI RMF, kill chain de 6 fases, relación con otras categorías LLM |
| `02-threat-modeling.md` | Actor de amenaza, pre-requisitos, CVSS 3.1 orientativo (9.1 — Crítica) |
| `03-casos-reales.md` | Greshake et al. (2023), Perez & Ribeiro (2022), caso Bing "Sydney" |
| `04-analisis-tecnico.md` | Anatomía del ataque, técnicas de ocultación en PDF, diagrama de flujo, mecanismo del fallo |
| `05-cumplimiento-normativo.md` | GDPR (Art. 5.1.c, 32, 33, 34), DORA (Art. 9, 10), AI Act (Art. 9, 15) — ya con un primer borrador |
| `06-contexto-verdabank.md` | Narrativa del incidente hipotético, timeline ficticia, impacto cuantificado |
| `07-playbook-incident-response.md` | Roles, fases (detección → contención → erradicación → recuperación → notificación → post-mortem) |

Otras referencias del repo:
- `docs/anexo-catalogo-ataques-llm.md` — catálogo completo de 29 ataques, posición del #7.
- `docs/propuesta-formal-promptguard-fintech.md` — propuesta formal del TFM (arquitectura,
  extensiones declaradas, marco normativo general).
- `CONTEXT.md` (raíz del repo) — glosario de términos del proyecto (Fixture, Kind, Step, Session
  File, Run Folder, Verdict, etc.) — **usar esta terminología exacta**, no inventar sinónimos.
- `lab/gen_adversarial_pdf.py` — generador base de PDF adversarial (reportlab).
- Fixtures existentes: `atk_021_indirect_doc_es.yaml`, `atk_022_indirect_doc_en_claude.yaml`,
  `leg_023_document_summary.yaml`, `navi_004_ignore_hidden_instructions.yaml`.

## 2. Índice oficial del documento final del TFM

Esta es la estructura que se va a seguir **siempre** al redactar el documento entregable. Cualquier
contenido que se escriba debe pensarse en términos de a qué sección de este índice alimenta.

1. Introducción y motivación
2. Estado del arte
   - 2.1. Ataques a sistemas LLM: OWASP LLM Top 10 y MITRE ATLAS
   - 2.2. Defensas existentes y red teaming automatizado (Garak y similares)
   - 2.3. Vectores de ataque
3. Objetivos, alcance y metodología
4. Diseño e implementación de PromptGuard
   - 4.1. Arquitectura general (Input Sanitizer, PII Shield, Tool Gatekeeper, Output Auditor,
     Compliance Logger)
   - 4.2. Vectores de ataque evaluados
5. Red teaming automatizado y continuo
6. Validación experimental y resultados
   - 6.1. Métricas y resultados por vector de ataque
   - 6.2. Análisis y discusión
7. Marco normativo y cumplimiento (DORA, AI Act, RGPD)
8. Conclusiones y trabajo futuro
9. Bibliografía

**Dónde encaja el trabajo de este capítulo (ataque #7):**
- **4.2** — descripción del vector "Prompt Injection Indirecta vía Documento" como parte del
  diseño/implementación de PromptGuard (qué módulo lo mitiga y cómo).
- **5** — si el ataque se integra en la suite automatizada (`run_attack_suite.py`), aporta al
  capítulo de red teaming continuo.
- **6.1 / 6.2** — resultados y métricas específicas de este vector (tasa de éxito antes/después de
  la defensa, falsos positivos, latencia añadida).
- **7** — el análisis normativo específico de este vector (GDPR/DORA/AI Act, y NIST/ISO 27001 si
  aplica) alimenta directamente el capítulo normativo global.
- Contribuye también con ejemplos concretos a **2.1–2.3** (estado del arte / taxonomía de
  vectores) y con evidencia de reproducibilidad citable en cualquier apéndice.

## 3. Reglas de trabajo absolutas

1. **Documentar y especificar siempre.** Cada paso —diseño de payload, cambio de código, medida
   de defensa— se documenta por escrito antes o al momento de ejecutarlo, no después de memoria.
   Si aplica, se acompaña de un test (fixture automatizado o test pytest).
1.b. **Redacción del capítulo del TFM — en paralelo, con wrap-up al cierre de cada fase.** El
   archivo `CAPITULO.md` acumula prosa de calidad TFM (no notas de trabajo) a medida que se
   completa cada sub-paso relevante, organizada por la sección del índice oficial a la que
   alimenta (ver §2). Al cerrar cada fase (1.4, 2.4, Fase 3), se hace una pasada de wrap-up sobre
   lo acumulado: coherencia, transiciones entre sub-secciones, y verificación de que toda
   afirmación tiene su evidencia y cita correspondiente. Las notas de trabajo (specs técnicas en
   `01-ataque/README.md`, etc.) siguen existiendo aparte — son la materia prima, no sustituyen la
   prosa de `CAPITULO.md`.
2. **Reproducibilidad estricta.** Toda evidencia (ataque exitoso, ataque bloqueado, métrica) debe
   venir acompañada del procedimiento exacto para reproducirla: comando, fixture ID, commit,
   modelo/proveedor usado, y ruta del Session File / Run Report generado.
3. **Referenciar MITRE.** Al redactar cualquier análisis, citar la táctica/técnica/subtécnica
   ATLAS relevante (para este ataque: `TA0043 — Initial Access` / `AML.T0051.001`), igual que ya
   hace `01-mapeo-taxonomico.md`.
4. **Orden de fases fijo — no saltarse pasos:**
   `Fase 1 (Ataque) → Fase 2 (Defensa) → Fase 3 (Marco normativo)`.
   Cada fase se cierra con su(s) capítulo(s) redactado(s) antes de pasar a la siguiente. Ver
   `ROADMAP.md` para el desglose paso a paso con checkboxes.
5. **Los 7 capítulos de referencia en `docs/ataques/.../indirecta-documento/` NO se editan
   todavía.** Se usan como plantilla y fuente de contenido reutilizable (taxonomía, CVSS, casos
   reales, normativa ya investigada). Cuando haya evidencia real, se decide explícitamente si se
   actualizan in-place o se referencian desde el documento final.
6. **Alcance ético/legal.** Todo el trabajo de ataque y defensa se ejecuta **en local**, contra el
   propio lab del TFM (Máster en Ciberseguridad, UCM), en un contexto académico autorizado. Nada
   de esto se dirige a sistemas de terceros ni sale de este entorno controlado.

## 4. Convención de carpetas de este workspace

```
promptguard-fintech-lab/henri-tfm/
├── 00-INSTRUCCIONES.md   ← este archivo
├── ROADMAP.md            ← checklist paso a paso
├── CAPITULO.md           ← borrador acumulativo del capítulo del TFM (prosa, no notas)
├── bitacora/BITACORA.md  ← diario de trabajo cronológico
├── 01-ataque/            ← Fase 1: payloads, evidencia, notas técnicas (materia prima)
├── 02-defensa/           ← Fase 2: brainstorm, implementación, evidencia
├── 03-normativa/         ← Fase 3: investigación normativa
└── referencias/          ← papers, capturas de fuentes oficiales citadas
```
