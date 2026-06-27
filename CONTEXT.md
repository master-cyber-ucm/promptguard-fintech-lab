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
