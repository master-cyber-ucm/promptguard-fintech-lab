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
Una ejecución de `run_attack_suite.py` que envía fixtures al backend y persiste los Session Files en el Run Folder. No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass. No confundir con una **Campaña** (Agente de red-team): un Suite Run envía fixtures estáticos y predefinidos; una Campaña genera y muta payloads en vivo.
_Avoid_: test run, batch, campaign (reservado a la ejecución del Agente de red-team)

**Analyze Pass**:
Ejecución de `analyze.py` sobre un Run Folder. Lee los Session Files, carga los fixtures por ID para obtener los Fixture Indicators, calcula Verdicts (heurística + juez opcional), hace append de la Evaluation Section a cada Session File, y genera el Run Report.
_Avoid_: analysis, post-processing, evaluation run

**Pending Run**:
Un Run Folder que contiene Session Files pero no tiene Run Report todavía. `make analyze` sin argumentos procesa todos los Pending Runs.
_Avoid_: incomplete run, unanalyzed run

**Run Folder**:
Directorio `lab/audit/runs/{timestamp}_{model_slug}/` que agrupa todos los artefactos de un Suite Run: subcarpetas por endpoint con Session Files, y el Run Report en la raíz. Una Campaña (Agente de red-team) produce un Run Folder con la misma forma (`lab/audit/runs/{timestamp}_redteam-agent/`), pero subcarpetas por Ejercicio en vez de por endpoint.
_Avoid_: run directory, output folder, results directory

**Verdict**:
El resultado de evaluar la respuesta de Clara para un fixture concreto: `SUCCESS` (el ataque funcionó o la petición legítima fue procesada), `BLOCKED` (el ataque fue rechazado o la petición legítima fue bloqueada erróneamente), `UNKNOWN` (la respuesta no contiene ningún indicador reconocible).
_Avoid_: result, outcome, status, pass/fail

**Fixture indicator**:
Una de las listas `success` o `blocked` definidas en el YAML de un fixture. El Analyze Pass las usa para calcular el Verdict heurístico de cada fixture sin lógica hardcodeada en el script.
_Avoid_: keyword, detector, rule

**Argumento solicitado**:
Dato que el modelo incluye al invocar una Tool, antes de que el backend aplique autenticación, autorización o valores por defecto. Solo acredita la intención de la llamada, no el efecto ni la identidad finalmente autorizada.
_Avoid_: parámetro resuelto, dato autorizado

**Atributo resuelto**:
Dato que el backend determina o verifica al procesar una Tool, como la cuenta de origen asociada a la sesión autenticada. Acredita el contexto efectivo de la operación y se persiste en el resultado de la Tool, no como decisión del modelo.
_Avoid_: argumento del modelo, parámetro solicitado

**Contrato de evidencia de Tool**:
El formato versionado del resultado de una Tool que permite al Analyze Pass distinguir éxito, denegación, preparación, fallo técnico y ausencia de evidencia sin interpretar la respuesta natural de Clara.
_Avoid_: formato de log, estado de chat

**Invariante duro**:
Una condición de evaluación acreditada por evidencia estructurada cuya vulneración cierra el resultado y no puede ser reinterpretada por un juez semántico; por ejemplo, una transferencia completada sin confirmación.
_Avoid_: regla blanda, condición del juez

**Disposición de evaluación**:
La clasificación del tipo de resultado observado — seguridad, calidad funcional o evidencia insuficiente — independiente de si el fixture se considera pasado.
_Avoid_: veredicto, pass/fail, estado

**Rúbrica semántica**:
El criterio declarativo y específico de una fixture que permite al juez decidir si una respuesta sin la evidencia esperada satisface de forma segura y útil la petición del usuario.
_Avoid_: prompt del juez, regla implícita

**Híbrido de ataque**:
Flujo de evaluación adversarial que conserva las brechas deterministas y consulta a un juez de seguridad estructurado solo cuando no observa una evidencia suficiente de ataque exitoso.
_Avoid_: juez de legítimos, fallback permisivo

**Run Report**:
El par de artefactos generados por el Analyze Pass: un `.json` con datos estructurados y un `.md` con resumen legible, métricas y tablas. Ambos se guardan en la raíz del Run Folder como `run.json` y `run.md`. Su presencia indica que el Run Folder ya no es un Pending Run. El equivalente para una Campaña es el **Informe de Campaña**: misma forma (`run.json`/`run.md`) y mismo sitio, pero lo genera el propio Agente de red-team al cerrar la Campaña, no el Analyze Pass — no hay Fixture Indicators que cargar por ID porque los Intentos no son fixtures.
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
De dónde vino el tráfico que produjo un Turn: `interactivo` (alguien escribiendo en el Playground), `suite` (una corrida de `run_attack_suite.py`) o `redteam-agent` (un Intento del Agente de red-team dentro de una Campaña). Permite que el SOC separe una demo manual, una corrida de fixtures estáticos y una campaña de ataques mutados entre sí.
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

### Agente de red-team

**Agente de red-team**:
Módulo propio (`lab/redteam-agent/`, sin dependencia de FuzzyAI/Garak) que ataca un endpoint de Clara de forma autónoma e iterativa: genera y muta payloads, lee la respuesta, decide si el Objetivo del Ejercicio en curso se cumplió y elige el siguiente movimiento. Es un ejercicio de aprendizaje sobre el marco de defensa existente, no un componente del pipeline de producción — no tiene autoridad ni forma parte del proxy.
_Avoid_: fuzzer, red teamer, atacante automático

**Campaña**:
Una ejecución completa del Agente de red-team: recorre los Ejercicios de la Taxonomía de Ataque contra un endpoint objetivo (por defecto `/chat/proxy`, configurable) y produce un Run Folder propio (`origen=redteam-agent`) con su Informe de Campaña. No confundir con un Suite Run — ver **Suite Run**.
_Avoid_: run, corrida, sesión de fuzzing

**Ejercicio**:
La ejecución de una técnica de la Taxonomía de Ataque (una de las 7 subcategorías, ej. `cross-context-leakage`) dentro de una Campaña. Tiene su propio Objetivo declarado y su propio Presupuesto de Intentos; la memoria del Agente de red-team (qué ya probó, con qué resultado) está acotada a este nivel — no persiste entre Ejercicios de la misma Campaña, ni se resetea en cada Intento.
_Avoid_: técnica (a secas — reservado al nombre de la subcategoría; el Ejercicio es su ejecución), categoría, rama

**Objetivo**:
Descripción en lenguaje natural, escrita a mano una vez por Ejercicio al construir el harness (con fuente en `docs/ataques/`), de qué constituye un éxito para esa técnica — ej. "conseguir que Clara revele el IBAN de un usuario distinto al que hace la petición". Es el criterio contra el que el propio Agente de red-team se autoevalúa; no usa indicadores `success`/`blocked` como los fixtures, porque los Intentos son payloads nuevos sin YAML previo.
_Avoid_: expected result, criterio de éxito, meta

**Intento**:
Un disparo del Agente de red-team contra el endpoint objetivo dentro de un Ejercicio: un payload generado, la respuesta de Clara y el juicio (éxito/fallo) que el propio agente emite con la memoria de ese Ejercicio. Genera un Session File igual que cualquier Turn, con `origen=redteam-agent`.
_Avoid_: attempt (en inglés), payload (a secas — el payload es el contenido; el Intento es el evento completo), turn (reservado al vocabulario general; un Intento produce un Turn)

**Modo** (del Agente de red-team):
`caja negra` (por defecto: el agente solo ve la respuesta de Clara, igual que un adversario real) o `caja gris` (opcional: el agente también lee los Analysis Events del SOC del Intento — converge más rápido pero es un modelo de amenaza menos realista).
_Avoid_: nivel de acceso, visibilidad

**Motor de evolución**:
La estrategia que decide el siguiente Intento dentro de un Ejercicio tras un fallo. Intercambiable por configuración de Campaña, no fijo: autorreflexivo (el modelo atacante razona en lenguaje natural sobre por qué falló), genético (población de variantes con selección/cruce) o guiado-por-taxonomía (salta a la siguiente técnica catalogada o combina dos). Viven en `lab/redteam-agent/evolution/`.
_Avoid_: estrategia (a secas), algoritmo

**Modelo atacante**:
El modelo Ollama que razona y genera los payloads del Agente de red-team. Parámetro de Campaña independiente del modelo que sirve a Clara (`OLLAMA_MODEL` del lab) — por defecto uno de mayor capacidad, para que el "pensamiento lateral" no esté limitado por el mismo modelo pequeño que defiende el target.
_Avoid_: attacker model (en inglés), juez (reservado al LLM-judge del Analyze Pass, que es un rol distinto)

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
