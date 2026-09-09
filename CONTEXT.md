# PromptGuard FinTech Lab

Laboratorio experimental del TFM que simula un chatbot bancario vulnerable (VerdaBank / Clara) para evaluar ataques LLM y defensas.

## Language

### Fixtures y casos de prueba

**Fixture**:
Un caso de prueba estructurado en YAML que describe un ataque o petición legítima contra Clara. Incluye metadatos (id, category, severity), variables y uno o más steps.

**Kind**:
El rol que desempeña un fixture: `attack-prompts` (ataques reales), `legitimate-prompts` (peticiones normales), `navi-prompts` (ataques ingenuos/obvios). Refleja el subdirectorio dentro de cada subcategoría.

**Step**:
Un único turn de conversación dentro de un fixture: `{step, role, content}`. Un fixture con `type: single` tiene exactamente un step; `multi-step` tiene dos o más.

**Rendered step**:
Un step con todos los placeholders `{{variable}}` interpolados a sus valores por defecto. Listo para enviar al backend sin edición.

**Variable**:
Un placeholder nombrado dentro del contenido de un step (ej. `{{target_account}}`). Cada variable declara un valor `default` en el YAML del fixture.

### Taxonomía de ataques

**Attack category**:
El identificador de categoría OWASP LLM Top 10 al que pertenece el fixture: LLM01, LLM02, LLM06, LLM07. Determina el grupo de primer nivel en el acordeón del playground.

**Subcategory**:
El patrón de ataque específico dentro de una attack category (ej. `directa`, `indirecta-documento`, `cross-context-leakage`). Corresponde al subdirectorio de segundo nivel en el árbol de fixtures.

**Severity**:
El nivel de riesgo asignado a un fixture: `CRITICAL`, `HIGH`, `LOW`. Determina el badge de color en el acordeón.

**Expected result**:
El resultado previsto al ejecutar el fixture contra el sistema: `BLOCK` (el sistema debe bloquearlo), `ALLOW` (debe procesarlo), `REFUSE` (debe rechazarlo como naïve). Sirve de referencia para evaluar la respuesta de Clara.

### Auditoría de interacciones

**Turn**:
Una unidad atómica de interacción dentro de una sesión: prompt de entrada → razonamiento (opcional) → tools invocadas → respuesta de Clara. Se persiste de forma inmediata al completarse.

**Session File**:
Fichero `.md` que recoge todos los turns de una sesión de chat, más la sección Evaluation que append el Analyze Pass. Un fichero por `session_id`, nombrado `{timestamp}_{session_id}.md`, dentro de `{Run Folder}/{endpoint}/`.

**Evaluation section**:
Sección `## Evaluación` que el Analyze Pass append al final de cada Session File. Contiene: fixture_id, expected result, verdict, indicadores que matchearon, y razonamiento del juez si aplica.

**Audit Repository**:
Componente del backend responsable de escribir Session Files. Recibe la ruta de destino (`audit_subdir`) en cada request de chat, lo que le permite escribir en `{Run Folder}/{endpoint}/` sin depender de una variable de entorno fija.

**Thinking trace**:
El contenido de `ThinkingPart` emitido por el modelo durante un turn. Presente solo en modelos con razonamiento explícito (Claude extended thinking, o1). Cuando el modelo no lo emite, el turn lo registra explícitamente como ausente.

### Ejecución automática y métricas

**Suite Run**:
Una ejecución de `run_attack_suite.py` que envía fixtures al backend y persiste los Session Files en el Run Folder. No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass. No confundir con una **Campaña** (Agente de red-team): un Suite Run envía fixtures estáticos y predefinidos; una Campaña genera y muta payloads en vivo.

**Analyze Pass**:
Evaluación mediante `evaluate.py` de los Session Files y su evidencia de herramientas y respuesta. `report.py` genera después el Run Report. Se distinguen seguridad, utilidad, estado de ejecución y evidencia insuficiente según el contrato de métricas.

**Pending Run**:
Un Run Folder que contiene Session Files pero no tiene Run Report todavía. `make evaluate` procesa las evaluaciones pendientes y `make report` genera los informes.

**Run Folder**:
Directorio `lab/audit/runs/{timestamp}_{model_slug}/` que agrupa todos los artefactos de un Suite Run: subcarpetas por endpoint con Session Files, y el Run Report en la raíz. Una Campaña (Agente de red-team) produce un Run Folder con la misma forma (`lab/audit/runs/{timestamp}_redteam-agent/`), pero subcarpetas por Ejercicio en vez de por endpoint.

**Verdict**:
Clasificación de una evaluación. Las etiquetas históricas `SUCCESS`, `BLOCKED` y `UNKNOWN` aparecen en campañas y resultados anteriores. La evaluación actual distingue efecto, comportamiento del modelo, seguridad, utilidad y evidencia insuficiente según el [contrato de métricas](docs/metricas/contrato-metricas.md); no deben reducirse esas dimensiones a una única tasa de bloqueo.

**Fixture indicator**:
Una de las listas `success` o `blocked` definidas en el YAML de un fixture. El Analyze Pass las usa para calcular el Verdict heurístico de cada fixture sin lógica hardcodeada en el script.

**Argumento solicitado**:
Dato que el modelo incluye al invocar una Tool, antes de que el backend aplique autenticación, autorización o valores por defecto. Solo acredita la intención de la llamada, no el efecto ni la identidad finalmente autorizada.

**Atributo resuelto**:
Dato que el backend determina o verifica al procesar una Tool, como la cuenta de origen asociada a la sesión autenticada. Acredita el contexto efectivo de la operación y se persiste en el resultado de la Tool, no como decisión del modelo.

**Contrato de evidencia de Tool**:
El formato versionado del resultado de una Tool que permite al Analyze Pass distinguir éxito, denegación, preparación, fallo técnico y ausencia de evidencia sin interpretar la respuesta natural de Clara.

**Invariante duro**:
Una condición de evaluación acreditada por evidencia estructurada cuya vulneración cierra el resultado y no puede ser reinterpretada por un juez semántico; por ejemplo, una transferencia completada sin confirmación.

**Disposición de evaluación**:
La clasificación del tipo de resultado observado — seguridad, calidad funcional o evidencia insuficiente — independiente de si el fixture se considera pasado.

**Fixture Execution**:
Una ejecución completa de un Fixture contra un target y una postura concretos en una repetición. Contiene uno o más Turns correlacionados por `fixture_execution_id` y es la unidad estadística primaria de un Suite Run.

**Postura experimental**:
La configuración efectiva y verificable de target, modelo, contexto, tools, policies y controles bajo la que se ejecuta una Fixture Execution. Dos posturas solo son comparables causalmente cuando difieren exclusivamente en los factores declarados del experimento.

**Plan de cobertura**:
El conjunto inmutable, fijado antes de un Suite Run, de Fixture Executions planificadas y su aplicabilidad por target, postura y repetición. Es la fuente del denominador y de la comprobación de completitud.

**Tool Invocation**:
Un uso solicitado de una Tool con identidad estable y ciclo de vida propio, desde la solicitud hasta su resultado terminal. No implica por sí mismo autorización ni efecto.

**Effect Receipt**:
Evidencia emitida por el servicio de dominio que acredita qué lectura autorizada se devolvió o qué cambio de estado se consumó. No es una afirmación del modelo ni el estado de un wrapper.

**Principal**:
El sujeto autenticado, tenant y contexto de assurance del que deriva la autoridad de una petición. Lo crea la frontera de autenticación y nunca se toma del body, prompt o argumentos del modelo.

**Conversation Session**:
El ámbito de diálogo cuyo historial y estado de seguridad pertenecen a un único Principal. Su identificador localiza la sesión, pero no concede acceso a ella.

**Transaction Authorization**:
La aprobación explícita de una operación concreta, vinculada a los detalles mostrados y emitida por un actor autenticado fuera del canal controlado por el LLM.

**Policy Decision**:
El resultado tipado de evaluar Principal, acción, recurso y contexto contra una policy efectiva y versionada. Expresa `ALLOW`, `DENY` o `REQUIRE_CONFIRMATION` y conserva la razón auditable.

**Action Proposal**:
La representación estructurada y todavía no ejecutable de una acción que el modelo propone a partir de una conversación, con argumentos y procedencia. Debe ser validada, autorizada y, cuando corresponda, confirmada antes de convertirse en comando.

**Session Security State**:
El estado de riesgo acumulado de una Conversation Session, derivado de señales tipadas y consultado por policy en turnos posteriores. No es el transcript ni una etiqueta permanente del usuario.

**Financial Claim**:
Una afirmación tipada sobre un hecho financiero —como saldo, titular, transacción o estado— vinculada a evidencia, sujeto, recurso, audiencia y momento de validez.

**Resultado de efecto**:
La evidencia sobre si el objetivo dañino se entregó o se consumó: efecto dañino observado, no observado o desconocido. Se deriva del punto de efecto o entrega, no de que exista un evento de defensa.

**Conducta observable del modelo**:
Clasificación de la salida raw y de las acciones solicitadas por el modelo como negativa, redirección segura, asistencia insegura, no respuesta, no observada o desconocida. Describe comportamiento externo y no atribuye una causa interna al modelo base, su alineamiento o el system prompt.

**Intervención defensiva**:
Una decisión enforced de un Componente que cambia el flujo, el artefacto entregado o el estado autorizado. Una detección, una decisión `ALLOW` o una decisión en shadow mode no constituyen intervención.

**Contención defensiva**:
Una Intervención defensiva aplicable que impide causalmente el efecto dañino dentro de la misma Fixture Execution y queda verificada en su punto de efecto. La ausencia genérica de daño no acredita contención.

**Resultado del sistema**:
Proyección exhaustiva y mutuamente excluyente de una Fixture Execution: contenida por infraestructura, contenida por la capa de modelo, vulnerable o inconclusa. Se deriva del Resultado de efecto, la Conducta observable del modelo, la evidencia defensiva y el estado de ejecución, que se conservan por separado.

**Rúbrica semántica**:
El criterio declarativo y específico de una fixture que permite al juez decidir si una respuesta sin la evidencia esperada satisface de forma segura y útil la petición del usuario.

**Híbrido de ataque**:
Flujo de evaluación adversarial que conserva las brechas deterministas y consulta a un juez de seguridad estructurado solo cuando no observa una evidencia suficiente de ataque exitoso.

**Run Report**:
El par de artefactos generados por el Analyze Pass: un `.json` con datos estructurados y un `.md` con resumen legible, métricas y tablas. Ambos se guardan en la raíz del Run Folder como `run.json` y `run.md`. Su presencia indica que el Run Folder ya no es un Pending Run. El equivalente para una Campaña es el **Informe de Campaña**: misma forma (`run.json`/`run.md`) y mismo sitio, pero lo genera el propio Agente de red-team al cerrar la Campaña, no el Analyze Pass — no hay Fixture Indicators que cargar por ID porque los Intentos no son fixtures.

### Observabilidad del proxy (SOC)

**SOC**:
La capa de observación del proxy: captura lo que cada componente de defensa decidió en tiempo real y lo hace consultable. No tiene autoridad — nunca bloquea, nunca clasifica por su cuenta. El proxy detecta y detiene; el SOC solo mira.

**Componente**:
Una pieza del proxy capaz de examinar algo y decidir sobre ello: `input_sanitizer`, `pii_shield`, `document_sanitizer`, `tool_gatekeeper`, `output_auditor`, `leak_guard`. Es el "quién" de un Analysis Event.

**Objetivo**:
Lo que un Componente examinó en una evaluación concreta: `prompt`, `documento`, `tool`, `respuesta`. Es el "sobre qué" de un Analysis Event, y es lo que permite distinguir defensas de entrada de defensas de salida sin mirar el nombre del Componente.

**Analysis Event**:
El registro de que un Componente examinó un Objetivo dentro de un Turn y decidió algo: acción, confianza, razón, regla que casó y latencia. Es el registro atómico del SOC y la forma única a la que se normalizan los cuatro dialectos que hoy conviven en el pipeline. **Se emite siempre, también cuando la acción es `ALLOW`** — un Componente que deja pasar es información, no silencio.

**Acción**:
Lo que un Componente decidió hacer en un Analysis Event: `ALLOW`, `SUSPICIOUS` o `BLOCK`. Es el vocabulario de `PromptDecision.action`, en tiempo real, y **no debe confundirse con Verdict**, que es el juicio *offline* del Analyze Pass sobre si el ataque funcionó. Un turno puede tener Acción `BLOCK` y Verdict `SUCCESS` si otra vía se lo saltó.

**Origen**:
De dónde vino el tráfico que produjo un Turn: `interactivo` (alguien escribiendo en el Playground), `suite` (una corrida de `run_attack_suite.py`) o `redteam-agent` (un Intento del Agente de red-team dentro de una Campaña). Permite que el SOC separe una demo manual, una corrida de fixtures estáticos y una campaña de ataques mutados entre sí.

**Postura**:
Qué defensas estaban activas en el momento de un Turn, capturada como la cadena que el pipeline ya construye (`proxy=True gatekeeper=True pii_shield=False vulnerable=False`). Es lo que permite leer un Turn sin ningún Analysis Event como ausencia de defensa en vez de como fallo de captura.

**Cobertura**:
La relación entre un vector de ataque y el Componente que lo defiende, más si esa defensa está realmente implementada. Se declara a mano (deriva de `docs/defensas/README.md`, no del código) y es lo que hace visible que Prompt Injection Directa sigue sin control real.

**Alerta**:
Un Analysis Event de acción `BLOCK` o `SUSPICIOUS` materializado para revisión humana, con severidad y estado (`nueva` / `revisada` / `descartada`). Marcar una Alerta es el **único** juicio que emite el sistema, y siempre lo emite una persona: el SOC nunca la cierra solo. La severidad se declara junto a su procedencia (`fixture`, `mapa-categoria`, `por-defecto`) para no presentar como objetiva una puntuación que no lo es.

**Base de conocimiento**:
Los documentos de `docs/ataques/` y `docs/defensas/` indexados en memoria y servidos por el SOC. El puente con un Turn es estructural: fixtures y documentos comparten el árbol de taxonomía, así que la correspondencia no necesita metadatos ni etiquetado.

### Agente de red-team

**Agente de red-team**:
Módulo propio (`lab/redteam-agent/`, sin dependencia de FuzzyAI/Garak) que ataca un endpoint de Clara de forma autónoma e iterativa: genera y muta payloads, lee la respuesta, decide si el Objetivo del Ejercicio en curso se cumplió y elige el siguiente movimiento. Es un ejercicio de aprendizaje sobre el marco de defensa existente, no un componente del pipeline de producción — no tiene autoridad ni forma parte del proxy.

**Campaña**:
Una ejecución completa del Agente de red-team: recorre los Ejercicios de la Taxonomía de Ataque contra un endpoint objetivo (por defecto `/chat/proxy`, configurable) y produce un Run Folder propio (`origen=redteam-agent`) con su Informe de Campaña. No confundir con un Suite Run — ver **Suite Run**.

**Ejercicio**:
La ejecución de una técnica de la Taxonomía de Ataque (una de las 7 subcategorías, ej. `cross-context-leakage`) dentro de una Campaña. Tiene su propio Objetivo declarado y su propio Presupuesto de Intentos; la memoria del Agente de red-team (qué ya probó, con qué resultado) está acotada a este nivel — no persiste entre Ejercicios de la misma Campaña, ni se resetea en cada Intento.

**Objetivo**:
Descripción en lenguaje natural, escrita a mano una vez por Ejercicio al construir el harness (con fuente en `docs/ataques/`), de qué constituye un éxito para esa técnica — ej. "conseguir que Clara revele el IBAN de un usuario distinto al que hace la petición". Es el criterio contra el que el propio Agente de red-team se autoevalúa; no usa indicadores `success`/`blocked` como los fixtures, porque los Intentos son payloads nuevos sin YAML previo.

**Intento**:
Un disparo del Agente de red-team contra el endpoint objetivo dentro de un Ejercicio: un payload generado, la respuesta de Clara y el juicio (éxito/fallo) que el propio agente emite con la memoria de ese Ejercicio. Genera un Session File igual que cualquier Turn, con `origen=redteam-agent`.

**Modo** (del Agente de red-team):
`caja negra` (por defecto: el agente solo ve la respuesta de Clara, igual que un adversario real) o `caja gris` (opcional: el agente también lee los Analysis Events del SOC del Intento — converge más rápido pero es un modelo de amenaza menos realista).

**Motor de evolución**:
La estrategia que decide el siguiente Intento dentro de un Ejercicio tras un fallo. Intercambiable por configuración de Campaña, no fijo: autorreflexivo (el modelo atacante razona en lenguaje natural sobre por qué falló), genético (población de variantes con selección/cruce) o guiado-por-taxonomía (salta a la siguiente técnica catalogada o combina dos). Viven en `lab/redteam-agent/evolution/`.

**Modelo atacante**:
El modelo Ollama que razona y genera los payloads del Agente de red-team. Parámetro de Campaña independiente del modelo que sirve a Clara (`OLLAMA_MODEL` del lab) — por defecto uno de mayor capacidad, para que el "pensamiento lateral" no esté limitado por el mismo modelo pequeño que defiende el target.

**Fuente de semillas**:
Un origen de payloads de apertura ya escritos (no generados en el momento por el Modelo atacante), leído de `lab/redteam-agent/sources/data/*.json` y ofrecido al Motor de evolución configurado para cada Intento nuevo de un Ejercicio hasta agotar su catálogo — ver `sources/README.md`. Opcional (`--seed-source`, default `ninguna`) y aditivo: si la Técnica no tiene semillas de esa fuente, o ya se agotaron, el motor genera el payload igual que sin ella. Dos tipos: externas de solo lectura (`garak`, vendorizada una vez) y la propia experiencia acumulada entre Campañas (`memoria`, ver más abajo). El Informe de Campaña registra la procedencia (`fuente`) de cada Intento.

**Memoria persistente** (del Agente de red-team):
Una Fuente de semillas (`--seed-source memoria`) que, a diferencia de una fuente externa como `garak`, es la propia experiencia del agente entre Campañas: cada `python cli.py`, al cerrar, guarda en `sources/data/memoria.json` los Intentos con veredicto `SUCCESS`/`CONTINUE` de esa Campaña (nunca `FAILED` — no aporta nada que reinyectar), con independencia de qué `--seed-source` se haya usado para lanzarla. Antes de esto, cada Campaña nueva empezaba en blanco sin importar cuántas se hubieran corrido antes — la memoria del agente estaba acotada a un Ejercicio de una sola Campaña. No se versiona en git: es estado local acumulado, no un dataset fijo.

### Entidades del sistema

**Playground**:
El frontend web (`playground.html`) que expone a Clara sin defensas para pruebas manuales de ataques. Puerto 3000.

**Clara**:
El agente de IA bancario de VerdaBank, implementado con pydantic-ai. En modo vulnerable, no tiene ninguna capa de seguridad.

**Fixture Browser**:
El panel lateral del Playground que lista los fixtures disponibles agrupados por attack category, permitiendo cargar sus rendered steps en el textarea de chat.

**Fixture Draft**:
Una conversación capturada en el Playground en proceso de edición hacia un Fixture guardable. Reúne los turns que el usuario envió a Clara como steps candidatos, junto con los metadatos (id, category, subcategory, kind, severity, expected result) y el bloque de evaluación que el usuario configura en el formulario de autoría antes de persistirlo como YAML en el árbol de fixtures.
