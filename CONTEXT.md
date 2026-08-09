# PromptGuard FinTech Lab

Laboratorio experimental del TFM que simula un chatbot bancario vulnerable (VerdaBank / Clara) para evaluar ataques LLM y defensas.

## Language

### Fixtures y casos de prueba

**Fixture**:
Un caso de prueba estructurado en YAML que describe un ataque o petición legítima contra Clara. Incluye metadatos (id, category, severity), variables y uno o más steps.
_Avoid_: test case, prompt file, escenario

**Kind**:
El rol que desempeña un fixture: `attack-prompts` (ataques reales), `legitimate-prompts` (peticiones normales), `navi-prompts` (ataques ingenuos/obvios). Refleja el subdirectorio dentro de cada subcategoría.
_Avoid_: type, role, class

**Step**:
Un único turn de conversación dentro de un fixture: `{step, role, content}`. Un fixture con `type: single` tiene exactamente un step; `multi-step` tiene dos o más.
_Avoid_: message, turn, prompt

**Rendered step**:
Un step con todos los placeholders `{{variable}}` interpolados a sus valores por defecto. Listo para enviar al backend sin edición.
_Avoid_: resolved step, expanded step

**Variable**:
Un placeholder nombrado dentro del contenido de un step (ej. `{{target_account}}`). Cada variable declara un valor `default` en el YAML del fixture.
_Avoid_: parameter, placeholder, token

### Taxonomía de ataques

**Attack category**:
El identificador de categoría OWASP LLM Top 10 al que pertenece el fixture: LLM01, LLM02, LLM06, LLM07. Determina el grupo de primer nivel en el acordeón del playground.
_Avoid_: category, LLM category, owasp category

**Subcategory**:
El patrón de ataque específico dentro de una attack category (ej. `directa`, `indirecta-documento`, `cross-context-leakage`). Corresponde al subdirectorio de segundo nivel en el árbol de fixtures.
_Avoid_: attack type, variant, subtype

**Severity**:
El nivel de riesgo asignado a un fixture: `CRITICAL`, `HIGH`, `LOW`. Determina el badge de color en el acordeón.
_Avoid_: risk level, priority

**Expected result**:
El resultado previsto al ejecutar el fixture contra el sistema: `BLOCK` (el sistema debe bloquearlo), `ALLOW` (debe procesarlo), `REFUSE` (debe rechazarlo como naïve). Sirve de referencia para evaluar la respuesta de Clara.
_Avoid_: expected behavior, outcome

### Auditoría de interacciones

**Turn**:
Una unidad atómica de interacción dentro de una sesión: prompt de entrada → razonamiento (opcional) → tools invocadas → respuesta de Clara. Se persiste de forma inmediata al completarse.
_Avoid_: step (reservado para los pasos de un fixture), message, exchange

**Session File**:
Fichero `.md` que recoge todos los turns de una sesión de chat, más la sección Evaluation que append el Analyze Pass. Un fichero por `session_id`, nombrado `{timestamp}_{session_id}.md`, dentro de `{Run Folder}/{endpoint}/`.
_Avoid_: log, transcript, audit log

**Evaluation section**:
Sección `## Evaluación` que el Analyze Pass append al final de cada Session File. Contiene: fixture_id, expected result, verdict, indicadores que matchearon, y razonamiento del juez si aplica.
_Avoid_: result section, verdict block, analysis

**Audit Repository**:
Componente del backend responsable de escribir Session Files. Recibe la ruta de destino (`audit_subdir`) en cada request de chat, lo que le permite escribir en `{Run Folder}/{endpoint}/` sin depender de una variable de entorno fija.
_Avoid_: logger, audit service, file writer

**Thinking trace**:
El contenido de `ThinkingPart` emitido por el modelo durante un turn. Presente solo en modelos con razonamiento explícito (Claude extended thinking, o1). Cuando el modelo no lo emite, el turn lo registra explícitamente como ausente.
_Avoid_: reasoning, chain of thought, internal monologue

### Ejecución automática y métricas

**Suite Run**:
Una ejecución de `run_attack_suite.py` que envía fixtures al backend y persiste los Session Files en el Run Folder. No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass.
_Avoid_: test run, batch, campaign

**Analyze Pass**:
Ejecución de `analyze.py` sobre un Run Folder. Lee los Session Files, carga los fixtures por ID para obtener los Fixture Indicators, calcula Verdicts (heurística + juez opcional), hace append de la Evaluation Section a cada Session File, y genera el Run Report.
_Avoid_: analysis, post-processing, evaluation run

**Pending Run**:
Un Run Folder que contiene Session Files pero no tiene Run Report todavía. `make analyze` sin argumentos procesa todos los Pending Runs.
_Avoid_: incomplete run, unanalyzed run

**Run Folder**:
Directorio `lab/audit/runs/{timestamp}_{model_slug}/` que agrupa todos los artefactos de un Suite Run: subcarpetas por endpoint con Session Files, y el Run Report en la raíz.
_Avoid_: run directory, output folder, results directory

**Verdict**:
El resultado de evaluar la respuesta de Clara para un fixture concreto: `SUCCESS` (el ataque funcionó o la petición legítima fue procesada), `BLOCKED` (el ataque fue rechazado o la petición legítima fue bloqueada erróneamente), `UNKNOWN` (la respuesta no contiene ningún indicador reconocible).
_Avoid_: result, outcome, status, pass/fail

**Fixture indicator**:
Una de las listas `success` o `blocked` definidas en el YAML de un fixture. El Analyze Pass las usa para calcular el Verdict heurístico de cada fixture sin lógica hardcodeada en el script.
_Avoid_: keyword, detector, rule

**Run Report**:
El par de artefactos generados por el Analyze Pass: un `.json` con datos estructurados y un `.md` con resumen legible, métricas y tablas. Ambos se guardan en la raíz del Run Folder como `run.json` y `run.md`. Su presencia indica que el Run Folder ya no es un Pending Run.
_Avoid_: report, output, results file

### Observabilidad del proxy (SOC)

**SOC**:
La capa de observación del proxy: captura lo que cada componente de defensa decidió en tiempo real y lo hace consultable. No tiene autoridad — nunca bloquea, nunca clasifica por su cuenta. El proxy detecta y detiene; el SOC solo mira.
_Avoid_: monitor, auditoría, dashboard (a secas), WAF

**Componente**:
Una pieza del proxy capaz de examinar algo y decidir sobre ello: `input_sanitizer`, `pii_shield`, `document_sanitizer`, `tool_gatekeeper`, `output_auditor`, `leak_guard`. Es el "quién" de un Analysis Event.
_Avoid_: stage (reservado a las que implementan `core.base.Stage`; el Tool Gatekeeper y el Document Sanitizer no lo hacen), capa, layer, módulo

**Objetivo**:
Lo que un Componente examinó en una evaluación concreta: `prompt`, `documento`, `tool`, `respuesta`. Es el "sobre qué" de un Analysis Event, y es lo que permite distinguir defensas de entrada de defensas de salida sin mirar el nombre del Componente.
_Avoid_: target, input, scope

**Analysis Event**:
El registro de que un Componente examinó un Objetivo dentro de un Turn y decidió algo: acción, confianza, razón, regla que casó y latencia. Es el registro atómico del SOC y la forma única a la que se normalizan los cuatro dialectos que hoy conviven en el pipeline. **Se emite siempre, también cuando la acción es `ALLOW`** — un Componente que deja pasar es información, no silencio.
_Avoid_: log, decisión (a secas), alerta, hallazgo

**Acción**:
Lo que un Componente decidió hacer en un Analysis Event: `ALLOW`, `SUSPICIOUS` o `BLOCK`. Es el vocabulario de `PromptDecision.action`, en tiempo real, y **no debe confundirse con Verdict**, que es el juicio *offline* del Analyze Pass sobre si el ataque funcionó. Un turno puede tener Acción `BLOCK` y Verdict `SUCCESS` si otra vía se lo saltó.
_Avoid_: veredicto, resultado, estado

**Origen**:
De dónde vino el tráfico que produjo un Turn: `interactivo` (alguien escribiendo en el Playground) o `suite` (una corrida de `run_attack_suite.py`). Permite que el SOC separe una demo manual de las 400+ trazas de una corrida completa.
_Avoid_: source, tipo, modo

**Postura**:
Qué defensas estaban activas en el momento de un Turn, capturada como la cadena que el pipeline ya construye (`proxy=True gatekeeper=True pii_shield=False vulnerable=False`). Es lo que permite leer un Turn sin ningún Analysis Event como ausencia de defensa en vez de como fallo de captura.
_Avoid_: configuración, defensas activas, modo

**Cobertura**:
La relación entre un vector de ataque y el Componente que lo defiende, más si esa defensa está realmente implementada. Se declara a mano (deriva de `docs/defensas/README.md`, no del código) y es lo que hace visible que Prompt Injection Directa sigue sin control real.
_Avoid_: mapa de defensas, matriz, protección

**Alerta**:
Un Analysis Event de acción `BLOCK` o `SUSPICIOUS` materializado para revisión humana, con severidad y estado (`nueva` / `revisada` / `descartada`). Marcar una Alerta es el **único** juicio que emite el sistema, y siempre lo emite una persona: el SOC nunca la cierra solo. La severidad se declara junto a su procedencia (`fixture`, `mapa-categoria`, `por-defecto`) para no presentar como objetiva una puntuación que no lo es.
_Avoid_: incidente, hallazgo, detección

**Base de conocimiento**:
Los documentos de `docs/ataques/` y `docs/defensas/` indexados en memoria y servidos por el SOC. El puente con un Turn es estructural: fixtures y documentos comparten el árbol de taxonomía, así que la correspondencia no necesita metadatos ni etiquetado.
_Avoid_: docs, wiki, ayuda

### Entidades del sistema

**Playground**:
El frontend web (`playground.html`) que expone a Clara sin defensas para pruebas manuales de ataques. Puerto 3000.
_Avoid_: UI, frontend, dashboard

**Clara**:
El agente de IA bancario de VerdaBank, implementado con pydantic-ai. En modo vulnerable, no tiene ninguna capa de seguridad.
_Avoid_: bot, asistente, LLM

**Fixture Browser**:
El panel lateral del Playground que lista los fixtures disponibles agrupados por attack category, permitiendo cargar sus rendered steps en el textarea de chat.
_Avoid_: attack panel, side panel, fixture list

**Fixture Draft**:
Una conversación capturada en el Playground en proceso de edición hacia un Fixture guardable. Reúne los turns que el usuario envió a Clara como steps candidatos, junto con los metadatos (id, category, subcategory, kind, severity, expected result) y el bloque de evaluación que el usuario configura en el formulario de autoría antes de persistirlo como YAML en el árbol de fixtures.
_Avoid_: draft, borrador, nuevo test, capture
