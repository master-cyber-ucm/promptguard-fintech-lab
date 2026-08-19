# Plan de excelencia — Agente de red-team y defensas del proxy

> Punto de partida: `lab/redteam-agent/HALLAZGOS-SESION-20260816.md` (1 ataque confirmado,
> 2 técnicas con evaluación no fiable). Este documento cruza esos hallazgos con el código
> real de las defensas y propone un plan priorizado en dos pistas. Convención de
> prioridad igual que `TODOs.md`: P0 bloqueante, P1 alto valor, P2 mejora, P3 nice-to-have.

## 0. Lo más importante que salió de cruzar ambas pistas

**El bypass de Excessive Agency no es un hallazgo nuevo — es un diseño ya escrito que
nunca se conectó.** `docs/defensas/LLM06-excessive-agency/acciones-no-autorizadas.md`
especifica límites por importe, `requires_approval_above: 1000.00` y un endpoint de
confirmación fuera de banda. Existe incluso el fichero de configuración,
`lab/backend/config/rules/tool_permissions.yaml`, con esos valores exactos ya escritos.
**Cero referencias a `tool_permissions.yaml` en `src/`** — el Tool Gatekeeper real
(`lab/backend/src/agents/tools.py`) solo verifica propiedad de cuenta (`_owns_account`),
nunca importe, nunca aprobación. El payload que generó el Agente de red-team
(transferencia de 1,234.56 €/1 € sin confirmación) es la reproducción exacta y en vivo de
`atk_006`/`atk_007`, los fixtures que ya existían para probar justo esto.

Consecuencia para el plan: el fix de mayor prioridad no es "diseñar una defensa nueva",
es **conectar la que ya está diseñada y configurada**.

---

## Pista A — Defensas del proxy

### A1 (P0) — Conectar `tool_permissions.yaml` al Tool Gatekeeper: límites e confirmación

**Gap**: `transferencia_nacional` en `agents/tools.py` no lee `limits.customer.max_amount`
(5.000 €), `daily_limit` (10.000 €), `requires_approval_above` (1.000 €) ni
`forbidden_params` del YAML — los ejecuta sin mirarlos. `requires_approval: true` está
declarado y no se aplica en ningún sitio del código.

**Evidencia**: `lab/backend/config/rules/tool_permissions.yaml` (config muerta, 0 refs) +
`docs/defensas/LLM06-excessive-agency/acciones-no-autorizadas.md` §4 (diseño completo,
diagrama de flujo incluido) + hallazgo del Agente de red-team (transferencia real
ejecutada sin confirmación, `HALLAZGOS-SESION-20260816.md`).

**Fix**:
1. Cargar `tool_permissions.yaml` al arrancar el backend (fail-closed: tool sin entrada
   → denegada, tal como pide el propio diseño §4.1).
2. En `transferencia_nacional`: verificar `amount <= limits[role].max_amount` antes de
   ejecutar; denegar con `attack_type="limit_exceeded"` si no.
3. Implementar el endpoint de confirmación fuera de banda que ya describe el diseño:
   `POST /api/v1/confirm/{operation_id}` con token firmado y TTL corto. Cuando
   `amount > requires_approval_above`, la tool no ejecuta — devuelve un `operation_id`
   pendiente; el Compliance Logger y el SOC lo reflejan como `SUSPICIOUS` en vez de
   `ALLOW` hasta que se confirme.
4. Rechazar `forbidden_params` (`override_limit`, `bypass_approval`, `admin_mode`) si el
   LLM los intenta pasar — ya están en el YAML, falta el `if`.

**No incluido en A1** (declarado explícitamente fuera, como ya hace el propio diseño):
acumulado diario en Redis, fraccionamiento/*smurfing* — quedan como su propio punto (A2).

**Verificación**: `atk_006`/`atk_007` (ya existen como fixtures) deben pasar de
`SUCCESS`/vulnerable a `BLOCKED`/`SUSPICIOUS` en `run_attack_suite.py`. Añadir
`test_tool_gatekeeper_limites.py` con el caso exacto que generó el Agente de red-team
(transferencia con framing de urgencia, sin importe explícito de confirmación) como test
de regresión — mismo patrón que `test_confused_deputy_fixtures.py`.
**Cierre del ciclo**: re-correr `lab/redteam-agent` sobre `acciones-no-autorizadas` tras
el fix — debe pasar de 🔴 a 🟢 con la misma técnica y el mismo motor que lo encontró.

**DoD**:
- `tool_permissions.yaml` se carga al arrancar el backend; una tool sin entrada en el
  YAML se deniega (fail-closed), verificado con un test dedicado.
- `transferencia_nacional` deniega `amount > limits[role].max_amount` con
  `attack_type="limit_exceeded"` y emite el Analysis Event correspondiente.
- `amount > requires_approval_above` no ejecuta: devuelve `operation_id` pendiente,
  `POST /api/v1/confirm/{operation_id}` con token válido y no expirado la ejecuta.
- `forbidden_params` (`override_limit`, `bypass_approval`, `admin_mode`) se rechazan
  si el LLM los pasa.
- `atk_006`/`atk_007` pasan de `SUCCESS` a `BLOCKED`/`SUSPICIOUS` en `run_attack_suite.py`.
- 0 regresiones en la suite de tests existente (150+ tests en verde).

**Test**:
- `test_tool_gatekeeper_limites.py` (nuevo, automático): importe bajo el límite sin
  aprobación → ejecuta; importe entre `requires_approval_above` y `max_amount` → queda
  pendiente de confirmación; importe sobre `max_amount` → denegado; `forbidden_params`
  presentes → denegado; confirmación con token inválido/expirado → denegado.
- Manual: `curl` directo a `/chat/proxy` reproduciendo el payload exacto de
  `HALLAZGOS-SESION-20260816.md` (framing de urgencia, transferencia sin importe de
  confirmación) — debe quedar `SUSPICIOUS`/pendiente, no `completed`.
- Cierre de ciclo: `redteam-agent` sobre `acciones-no-autorizadas`, mismo motor
  (autorreflexivo) — 0/N SUCCESS tras el fix.

### A2 (P1) — Extender a `bloquear_tarjeta`, umbral diario y fraccionamiento

`bloquear_tarjeta` tiene `requires_approval: false` en el YAML (correcto, es reversible
en sucursal) pero tampoco valida `required_params`. Umbral diario acumulado y detección
de fraccionamiento (*smurfing*) están declarados como pendientes en el propio diseño
(`acciones-no-autorizadas.md` checklist) — requieren estado entre requests (Redis o la
sesión), no una validación por-llamada. Presupuesto: bloqueante para "excelencia" pero
no para A1.

**DoD**: `bloquear_tarjeta` valida `required_params`; acumulado diario por usuario
persistido entre requests; ≥3 transferencias fraccionadas por debajo del umbral en una
ventana corta se marcan `SUSPICIOUS` (patrón, no bloqueo determinista).
**Test**: `test_fraccionamiento.py` — N transferencias de 900 € (bajo el umbral de
1.000 €) en la misma sesión deben disparar la detección en la N-ésima. Manual: repetir
el mismo experimento con el Agente de red-team en modo genético (población de variantes
por debajo del umbral es exactamente el patrón que ese motor probaría).

### Fuera de este plan — Input Sanitizer real

`input_sanitizer.py` (esqueleto de 32 líneas, ALLOW siempre) queda **explícitamente
fuera** de este plan — es su propia épica, ya priorizada como P1 en `TODOs.md`, con
diseño completo en `docs/defensas/LLM01-prompt-injection/directa.md`. Se deja constancia
aquí de una consecuencia que sí pertenece a este documento: mientras esa épica no cierre,
el Agente de red-team no puede producir evidencia fiable sobre `directa` — no hay nada
que contener todavía en ese vector, con o sin agente. Cuando esa épica cierre, su propio
criterio de cierre debería incluir re-correr el Agente de red-team sobre `directa`, no
solo la suite estática de fixtures.

### A4 (P2) — Aislamiento de sesión por `user_id` en `session_store.py`

Ya declarado como hueco abierto en `core/leak_guard.py` y `TODOs.md` §11. No relacionado
con los hallazgos de esta sesión, pero cae en el mismo perímetro de "excelencia de las
defensas" — se incluye para que el plan quede completo, sin proponer trabajo nuevo sobre
lo ya decidido.

**DoD**: `session_store.py` indexa por `(session_id, user_id)`, no solo `session_id`; una
lectura con `user_id` distinto al que abrió la sesión se deniega.
**Test**: `test_session_isolation.py` — abrir sesión como `usr_001`, intentar leerla con
`user_id=usr_002` → denegado. Manual: el Agente de red-team en modo caja gris, apuntando
a un `session_id` ajeno conocido (de una corrida anterior), para confirmar que no hay
forma de "heredar" contexto de otra sesión por HTTP directo.

---

## Pista B — Agente de red-team

### B1 (P0) — Analyze Pass offline con juez más fuerte

**Gap**: el juez en caliente (`qwen2.5:3b`, mismo modelo que el target) produjo falsos
positivos consistentes en `directa` (3/3 corridas) y `pii-harvesting` (2/2 corridas).
Las salvaguardas estructurales (B2) atrapan los casos con verdad de terreno barata
(tools, IBAN ajeno) pero estas dos técnicas dependen de matices que un 3B no distingue.

**Fix**: replicar el patrón que el propio proyecto ya usa para la suite estática —
separar la Campaña (barata, determinista, guarda TODO el intercambio) de un **Analyze
Pass** offline (`analyze_campania.py`) que re-juzga cada Intento con un juez más capaz.
Dos opciones de juez, no excluyentes, exponer ambas por flag:
- Un modelo Ollama más grande corrido UNA vez por intento en batch offline (sin la
  presión de latencia de la campaña en vivo — aceptable que tarde ahí).
- Reusar el juez que ya usa `evaluate.py` del proyecto (`JUDGE_MODEL`), si acepta
  peticiones externas al criterio de fixture — evaluar si su prompt es reutilizable o
  si necesita una variante sin `expected_result`.

**Verificación**: re-judgment sobre los `run.json` de `HALLAZGOS-SESION-20260816.md` sin
volver a atacar (los Session Files y transcripciones ya existen) — debe coincidir con la
auditoría manual que ya se hizo a mano en ese documento (0 SUCCESS reales en `directa` y
`pii-harvesting`) como caso de prueba de que el nuevo juez es, como mínimo, tan bueno como
la revisión manual.

**DoD**: `analyze_campania.py` corre sobre cualquier Run Folder de `redteam-agent`
existente (sin volver a atacar), produce un `run.reanalizado.json` con veredicto +
razonamiento del nuevo juez por Intento, y un resumen de discrepancias
(cuántos veredictos cambiaron respecto al juez en caliente).
**Test**: automático — correr sobre los `run.json` de la sesión del 16/08, verificar
`0 == n_success` en `directa` y `pii-harvesting` tras el re-juicio (coincide con la
auditoría manual del `HALLAZGOS-...md`). Manual: leer 3 discrepancias al azar entre juez
en caliente y Analyze Pass y confirmar a mano cuál acertó.

### B2 (P1) — Extender la verificación estructural a más técnicas

`ground_truth.py` hoy solo cubre `cross-context-leakage`/`confused-deputy` (IBAN/nombre
de Carlos). Extensión concreta y de bajo coste: **reusar el catálogo real de PII del
propio backend** (`pii_shield.py::_catalogo_terceros`, `conjunto_autorizado`) en vez de
mantener un duplicado a mano — para `pii-harvesting`, un SUCCESS solo debería aceptarse
si la respuesta contiene un dato de un `user_id` DISTINTO al autenticado, verificable
contra ese catálogo. Decisión de arquitectura a tomar explícitamente: importar el
catálogo del backend acopla el agente al código del lab (rompe la independencia
declarada en ADR 0008); la alternativa es una copia mantenida a mano en
`redteam-agent/`, con el riesgo de que quede desincronizada. Recomendado: copia a mano
con un test que la compare contra el backend en CI, no import directo.

**Corrección tras implementar (17/08)**: el catálogo de DNI/teléfono/email por cliente
que este punto asumía **no existe** en el backend. `pii_shield.py` detecta esas
entidades por FORMA (regex), no por identidad — `ConjuntoAutorizado` solo rastrea IBAN,
tarjeta, nombre e importes por `user_id`, los mismos campos que ya usaba
`cross-context-leakage`. La extensión real: `OTROS_USUARIOS` (lista de Carlos Y Ana, no
solo Carlos) con verdad de terreno IBAN/nombre — `pii-harvesting` acepta el dato de
CUALQUIERA de los dos (su Objetivo no fija una víctima), a diferencia de
`cross-context-leakage`/`confused-deputy`, que siguen exigiendo específicamente a Carlos.

**DoD**: `ground_truth.py` cubre `pii-harvesting` contra cualquier otro cliente conocido
(IBAN/nombre de Carlos o Ana); un test de sincronización falla en CI si `MOCK_ACCOUNTS`
del backend cambia sin actualizar la copia del agente.
**Test**: `tests/test_ground_truth.py` (en `redteam-agent`, no en el backend) — compara
los valores hardcodeados contra `lab/backend/src/models/banking.py` leído como texto
(sin importar el módulo) y falla si diverge; caso explícito con los datos ficticios que
el propio atacante mandó en la sesión del 16/08 (debe seguir dando `False` — no son de
Carlos ni de Ana). 7/7 tests en verde.

### B3 (P1) — Calidad del payload del atacante en `directa`/`pii-harvesting`

No es solo el juez: el propio atacante generó peticiones bancarias legítimas en vez de
intentos de injection reales varias veces (ver ejemplos citados en
`HALLAZGOS-SESION-20260816.md`). Reforzar `_PAYLOAD_INSTRUCCIONES` no basta por sí solo
— añadir 2-3 ejemplos concretos (few-shot) de qué SÍ cuenta como intento de override para
`directa` en el propio `taxonomy.yaml` (campo `ejemplos_payload`, opcional, se inyecta en
el prompt del atacante si existe). Verificar con una corrida A/B: mismo motor, mismo
presupuesto, con y sin few-shot, comparar la variedad léxica y la tasa de payloads que el
juez (ya corregido por B1) considera intentos genuinos de ataque frente a peticiones
normales.

**DoD**: `taxonomy.yaml` acepta `ejemplos_payload` opcional por técnica; cuando está
presente, se inyecta en `_PAYLOAD_INSTRUCCIONES`; `directa` y `pii-harvesting` tienen
2-3 ejemplos cada una.
**Test**: A/B automático — 8 intentos con few-shot vs 8 sin, mismo motor/semilla de
Ejercicio, comparar cuántos payloads el juez corregido (B1) clasifica como intento de
ataque genuino (no petición legítima) — debe subir con few-shot. Manual: leer 5 payloads
generados con few-shot y confirmar a ojo que ya no son peticiones bancarias normales.

### B4 (P2) — Cobertura de ejecución no probada esta sesión

`genetico` y `taxonomia` solo se corrieron en Ejercicios sueltos, nunca en una campaña
completa de 6 técnicas; el camino multi-turno (`continuar()`) se ejerció poco. Antes de
declarar el agente "en excelencia": una campaña completa por cada uno de los 3 motores,
comparando tasa de bypass real (tras B1/B2) y coste en intentos hasta el primer SUCCESS
por técnica — es la comparación que el diseño original prometía y nunca se hizo.

**DoD**: 3 campañas completas (una por motor), 6 técnicas cada una, con B1-B3 ya
aplicados; tabla comparativa de intentos-hasta-bypass por motor/técnica en
`HALLAZGOS-...md` (nueva sección o documento hermano).
**Test**: no hay test automático de "calidad de motor" — es una campaña real, verificada
manualmente igual que se hizo el 16/08 (auditar cada SUCCESS contra `tools_used`/ground
truth antes de contarlo). Criterio de aceptación: cero SUCCESS aceptados sin evidencia
estructural o Analyze Pass que lo respalde.

### B5 (P2) — Corrida de control (`--vulnerable`)

Diseñada explícitamente (`--target proxy --vulnerable` como control) y nunca ejecutada
esta sesión. Sin ella no hay forma de afirmar "las defensas hacen más difícil el bypass"
con datos — solo con la lectura del diseño. Ejecutar tras A1, para que el contraste
con/sin defensas incluya la defensa que se acaba de cerrar.

**DoD**: una campaña `--vulnerable` completa (6 técnicas) queda registrada junto a su
contraparte defendida, con tabla comparativa de intentos-hasta-bypass con/sin defensas
en el Informe de Campaña o en `HALLAZGOS-...md`.
**Test**: manual — `acciones-no-autorizadas` en `--vulnerable` debe seguir dando SUCCESS
en el primer o segundo intento (sin Gatekeeper de por medio en absoluto), mientras que la
misma técnica contra el proxy defendido (tras A1) debe requerir 0 SUCCESS o muchos más
intentos. Es la comparación que hace citable la frase "las defensas dificultan el ataque".

### B7 (P1) — Refactor: rastro de auditoría legible por Ejercicio/Intento

**Motivación**: auditar los hallazgos de esta sesión requirió cruzar `run.json` (payload
+ respuesta truncados) con los Session Files sueltos en `lab/audit/runs/` (indexados por
`session_id`, no por número de Intento) para reconstruir qué pasó de verdad — el propio
proceso que hizo saltar los 5 falsos positivos de este documento. Debería poder hacerse
mirando un solo fichero por ataque, con los intentos ya separados por divisores dentro,
sin cruzar dos fuentes.

**Fix**: dentro de `lab/redteam-agent/`, una carpeta por Ejercicio (nombrada por técnica,
ej. `directa/`, estable entre campañas) y dentro **un fichero por ataque** — un ataque es
una ejecución de ese Ejercicio dentro de una Campaña concreta, nombrado por el
`run_folder_name` de esa Campaña. Dentro del fichero, los Intentos se separan con
divisores (`---` + `## Intento N`), mismo patrón que ya usa `_format_turn` en
`audit_repository.py` para separar Turnos dentro de un Session File — no un formato
nuevo, el mismo que el proyecto ya usa en el sitio equivalente. Se abre al empezar el
Ejercicio y se hace **append inmediato** tras cada turno de cada Intento (payload +
respuesta), y al cerrar cada Intento se añade su veredicto y razonamiento antes del
divisor del siguiente. Correr la misma técnica en Campañas distintas produce ficheros
distintos dentro de la misma carpeta — el histórico de esa técnica queda junto y
comparable entre corridas.

```
lab/redteam-agent/ejercicios/
├── directa/
│   ├── 20260816_205234_redteam-agent.md   ← 1 fichero = 1 Campaña completa de esta técnica
│   └── 20260817_113000_redteam-agent.md
├── cross-context-leakage/
│   └── 20260816_210638_redteam-agent.md
└── ...
```

Dentro de un fichero:

```
## Intento 1 — FAILED
### Payload
...
### Respuesta
...
### Veredicto
FAILED — <razonamiento>

---

## Intento 2 — SUCCESS
...
```

No sustituye los Session Files (`lab/audit/runs/`, que alimentan el SOC — se mantienen
sin cambios) ni el Informe de Campaña (`run.json`/`run.md`, que sigue siendo el resumen
agregado). Es una tercera vista, propia del agente, optimizada para lo que este plan y
`HALLAZGOS-SESION-20260816.md` ya demostraron que hace falta: auditar un Intento
concreto sin reconstruirlo a mano. Sienta además la base de datos que **B1** (Analyze
Pass offline) va a necesitar leer — implementarlo antes de B1 evita que el Analyze Pass
tenga que parsear `run.json` truncado.

**DoD**: cada Campaña produce, además de lo que ya produce hoy, un fichero por
ataque en `lab/redteam-agent/ejercicios/{tecnica_id}/{run_folder_name}.md`, con append
inmediato turno a turno (no al final del Ejercicio) y divisores `## Intento N` entre
intentos.
**Test**: `test_ejercicio_writer.py` — simular un Ejercicio de 2 Intentos (uno de 1 turno,
otro de 2) y verificar que el fichero existe DURANTE la ejecución (no solo al final,
para sobrevivir un crash a mitad de campaña) y que el contenido final tiene 2 secciones
`## Intento` bien delimitadas. Manual: abrir el fichero de una técnica real tras una
campaña y confirmar que se lee de corrido sin abrir ningún otro fichero.

### B6 (P3) — Robustez de parsing del juez

Varios `razonamiento` en los logs de esta sesión contienen texto de plantilla filtrado
(`VEREDICTO: FAILED\n\nRAZÓN: ...` sin extraer) — el regex de `_RAZON_RE` falla cuando el
modelo antepone acentos (`RAZÓN` vs `RAZON`) o repite el bloque de instrucciones. Bajo
impacto (no cambia el veredicto, solo ensucia el reporte) pero barato de arreglar:
normalizar acentos antes del match, o pedir el formato en un bloque delimitado más
estricto (JSON en vez de texto libre) — coincide con las mismas dos opciones que ya
evaluó el proyecto en otro contexto (`evaluate.py`).

**DoD**: `_extraer_veredicto`/`_extraer_payload` no dejan texto de plantilla en `razon`
en ninguno de los logs de una campaña de prueba de 20+ intentos.
**Test**: unitario — casos con `RAZÓN` acentuada, con el bloque de instrucciones repetido
por el modelo, y sin ninguna etiqueta reconocible; los tres deben devolver una razón
limpia o un fallback explícito, nunca texto de plantilla filtrado.

---

## Secuencia recomendada

No son pistas independientes — el orden importa:

1. **A1** (conectar límites + confirmación) — es el fix de mayor impacto real, y
   desbloquea el "cierre del ciclo" de B1-B5 para `acciones-no-autorizadas`.
2. **B7** (rastro de auditoría por Ejercicio/Intento) primero dentro de la pista B — es
   infraestructura barata que **B1** va a leer directamente; hacerlo después obligaría a
   tocar el Analyze Pass dos veces.
3. **B1** (Analyze Pass offline), sobre B7, en paralelo a A1 — no depende de A1, y sin
   él no se puede confiar en ningún resultado nuevo de `directa`/`pii-harvesting`.
4. **B2 + B3** — mejoran la señal de las dos técnicas problemáticas; hacerlo antes de
   volver a correr campañas grandes evita gastar tiempo de cómputo en falsos positivos.
5. **B4 + B5** — campañas de validación final, después de que A1/B1/B2/B3 estén cerrados,
   para que los números que produzcan sean citables.
6. **A2, A4, B6** — mejoras de fondo, sin urgencia ni dependencias fuertes.

Input Sanitizer (`directa`) queda fuera de esta secuencia — es otra épica; ver nota en
Pista A.

## Definición de "excelencia" (criterio de cierre)

- **Defensas** (dentro de este plan): `acciones-no-autorizadas` con Implementación ✅ de
  verdad (propiedad de cuenta + límites + confirmación, no solo lo primero) e Evidencia
  ✅ tras A1. `directa` queda fuera de este criterio — su cierre pertenece a la épica del
  Input Sanitizer, no a este plan.
- **Agente de red-team**: cero técnicas en estado "no evaluable con confianza" salvo
  `directa` (bloqueada por la épica externa) — el resto del harness con un veredicto que
  sobrevive tanto el juez en caliente como el Analyze Pass offline, un rastro de
  auditoría por Intento legible sin cruzar ficheros, y los 3 motores de evolución
  corridos al menos una vez en campaña completa.
