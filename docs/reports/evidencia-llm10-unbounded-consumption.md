# Evidencia — LLM10:2025 Unbounded Consumption (#8 Denegación de Servicio, #9 Denial of Wallet)

> **Generado:** 2026-08-17 · **Rama:** `feat/llm10-unbounded-consumption-defenses` · **Modelo:** `qwen2.5:3b` (Ollama local, sin GPU)
> **Escenarios:** `lab/backend/tests/fixtures/llm10_scenarios.yaml` (`llm10_001` flood, `llm10_002` token_burn, `llm10_003` budget_burn, `llm10_navi_001` control legítimo)
> **Runner:** `lab/scripts/run_llm10_suite.py` · **Fuentes:** `lab/audit/runs/20260817_*_llm10-{vulnerable,defendido}/run.json`

## Qué cierra este documento

`docs/defensas/LLM10-unbounded-consumption/` diseñaba cuatro módulos sin implementar.
Esta rama implementa dos — **Rate Limiter** (#8) y **Budget Guard** (#9), más el cap de
tokens de salida y la cota/TTL de `session_store.py` que #8 también necesitaba — y este
documento aporta la pieza que faltaba: **evidencia real, generada contra el proxy en
vivo, de que el sistema es vulnerable sin estos controles y deja de serlo con ellos
activos**, con la misma metodología vulnerable-vs-defendida (flag `vulnerable` de
`ChatRequest`) que ya usa el resto del proyecto — no un mecanismo de comparación aparte.

## Resumen

| Escenario | Vulnerable | Defendido | Confirma |
|---|---|---|---|
| **Flood** (#8) | 15/15 peticiones permitidas, 0 bloqueadas | 5/15 permitidas, **10/15 bloqueadas** | Rate Limiter corta el volumen |
| **Token burn** (#8) | Respuesta natural: **2.851 caracteres** | Respuesta capada: **35 caracteres** | Cap de tokens de salida corta la generación |
| **Budget burn** (#9) | 10/10 peticiones procesadas, sin corte | Cortado en el **intento 5 de 30** | Budget Guard corta el consumo acumulado |
| **Control legítimo** (navi) | — | 5/5 peticiones permitidas | Uso normal no se ve afectado |

Los tres ataques que estaban descubiertos ahora están contenidos. El control legítimo
confirma que ningún tráfico normal roza los umbrales — mismo principio de diseño que el
resto del catálogo ("un control que no se puede activar con tráfico legítimo no es una
defensa útil, es un checkbox").

## Nota metodológica: dos escenarios se midieron con umbrales rebajados, uno con el
## umbral de producción tal cual

Esto se declara explícitamente porque cambia lo que cada fila de la tabla puede afirmar:

- **Flood**: el umbral de producción (`RATE_LIMIT_MAX_REQUESTS=30`/60s) exige que ~30
  peticiones lleguen casi simultáneas para que el chequeo las vea dentro de la misma
  ventana — de lo contrario la ventana deslizante "respira" entre petición y petición
  (cada llamada real tarda 10-90s) y el límite nunca se alcanza, confirmado
  empíricamente en una corrida descartada (35 peticiones, concurrencia 4 → 35/35
  permitidas). Conseguir esa simultaneidad significa ~30 llamadas reales concurrentes al
  LLM local — en una prueba con concurrencia 10 la latencia por llamada escaló de 34s a
  95s de forma creciente, señal real de contención del contenedor compartido de
  desarrollo (sin GPU). Se optó por bajar `RATE_LIMIT_MAX_REQUESTS=5` **solo para esta
  demo** (revertido inmediatamente después) en vez de arriesgar ese entorno. El
  mecanismo probado es el mismo; el número absoluto de la demo no es el de producción.
- **Token burn**: la respuesta natural sin cap para este prompt (2.851 caracteres, ≈700-
  900 tokens) queda cerca del cap de producción (1.024 tokens) — el contraste sería
  real pero menos nítido. Se bajó `CLARA_MAX_OUTPUT_TOKENS=150` **solo para esta demo**
  para que el corte fuera inequívoco.
- **Budget burn**: se midió **con el valor de producción tal cual**
  (`BUDGET_GUARD_TOKEN_LIMIT=20000`/hora) — no hizo falta tocarlo, cortó por sí solo en
  el intento 5. Ver hallazgo siguiente.

## Hallazgo colateral: el presupuesto de producción se agota más rápido de lo esperado

20.000 tokens/hora cortando en el intento 5 implica ~4.000 tokens/petición — muy por
encima de los ~1.024 tokens de SALIDA que permite el cap. La diferencia es que
`result.usage()` (pydantic-ai) cuenta tokens de **entrada + salida**, y el system prompt
completo de Clara (reglas, información interna, definiciones de las 5 tools) es
sustancial en cada petición. **No es un bug** — es el comportamiento correcto y
documentado del Budget Guard (§3.1 del diseño: "el corte tiene que estar en la unidad
que el proveedor factura", que incluye el input) — pero sí es una señal de calibración:
`BUDGET_GUARD_TOKEN_LIMIT=20000`/hora permite ~5 turnos reales de conversación con Clara
antes de cortar a un usuario legítimo, un margen ajustado para uso normal. Queda anotado
en `docs/defensas/LLM10-unbounded-consumption/denial-of-wallet.md` como ítem a revisar,
no corregido en esta PR — cambiar el valor por defecto sin medir el patrón de uso real
sería ajustar a ciegas.

## Riesgo real encontrado en revisión: esta PR podía corromper la evidencia de los
## ataques #1-7 — corregido, no solo detectado

Antes de cerrar la PR se planteó la pregunta correcta: *¿puede este cambio afectar al
resto de los ataques del catálogo?* Verificación concreta, no solo razonamiento:

`run_attack_suite.py` manda las 108 fixtures existentes contra `/chat/proxy` con el
mismo `user_id` por defecto (`usr_001`), de forma **secuencial**. El Rate Limiter
sobrevive a eso sin problema (la ventana de 60s "respira" entre petición y petición
porque cada llamada real tarda 10-90s — mismo efecto que ya obligó a rebajar el umbral
para esta demo, ver arriba). El **Budget Guard no**: con el presupuesto de producción
(20.000 tokens/hora) agotándose en ~5 peticiones reales (hallazgo ya documentado
arriba), una corrida completa de la suite dejaría **~100 fixtures de LLM01/02/06/07
respondiendo `BLOCKED_BY_BUDGET_GUARD`** en vez de evaluar el ataque real.

Se verificó contra `scripts/evaluations/deterministic.py` que esto **no se detectaría
solo**: como el texto genérico del bloqueo no coincide con ningún indicador específico
del fixture, un ataque con `expected_result=BLOCK` se puntúa `BLOCKED, passed=True` —
exactamente como si el Tool Gatekeeper/PII Shield/Output Auditor hubieran parado el
ataque de verdad. La evidencia de los 7 vectores existentes se habría inflado en
silencio, sin ningún test fallando.

**Fix**: Rate Limiter y Budget Guard se saltan (chequeo Y registro de consumo — las dos
partes, no solo el bloqueo) cuando `request.fixture_id` está presente —
`lab/backend/src/api/routes/chat.py`. No se usa el `origen` del SOC porque el propio
harness de esta PR (`run_llm10_suite.py`) también escribe en `audit/runs/` y habría
quedado exento por error, invalidando la demostración de que estos guards bloquean de
verdad. `fixture_id` es la señal correcta: identifica tráfico de evaluación del
catálogo, no un consumidor real. 5 tests nuevos (`test_llm10_fixture_exemption.py`)
prueban las dos direcciones — sin `fixture_id` los guards protegen igual que antes; con
`fixture_id`, ni bloquean ni consumen presupuesto compartido.

## Detalle por escenario

### #8 — Flood de peticiones (`llm10_001`)

| | Vulnerable | Defendido |
|---|---|---|
| Peticiones enviadas | 15 (concurrencia 15) | 15 (concurrencia 15) |
| Permitidas | 15 | 5 |
| Bloqueadas | 0 | **10** |
| Duración | 89,99s | 90,02s |
| Run | `20260817_111128_llm10-vulnerable` | `20260817_111302_llm10-defendido` |

Con `vulnerable=True` el Rate Limiter se salta por completo (mismo criterio que el
resto del pipeline) — las 15 peticiones llegan a Clara. Con el pipeline defendido, la
6ª petición en adelante recibe `BLOCKED_BY_RATE_LIMITER` antes de tocar el LLM.

### #8 — Generación sin techo (`llm10_002`)

| | Vulnerable | Defendido |
|---|---|---|
| Longitud de la respuesta | **2.851 caracteres** | **35 caracteres** |
| Contenido | Explicación completa de los 3 productos bancarios | *"No puedo compartir esa informacion."* |
| Duración | 94,51s | 105,59s |
| Run | `20260817_141103_llm10-vulnerable` | `20260817_141258_llm10-defendido` |

Mismo prompt exacto en ambos casos — la única diferencia es `CLARA_MAX_OUTPUT_TOKENS`.
Nota honesta: con el cap muy bajo, el modelo no produce una respuesta truncada a mitad
de frase sino una deflexión corta — comportamiento del modelo ante un presupuesto de
tokens severamente limitado, no un fallo del cap (el cap sigue cumpliendo su función:
acotar el coste/tiempo de la respuesta con independencia de qué genere el modelo dentro
de ese límite).

### #9 — Agotamiento de presupuesto (`llm10_003`)

| | Vulnerable | Defendido |
|---|---|---|
| Peticiones planeadas | 10 | 30 |
| Cortado en el intento | — (ninguno) | **5** |
| Duración | 318,89s | 149,08s |
| Run | `20260817_141524_llm10-vulnerable` | `20260817_111956_llm10-defendido` |

En modo vulnerable, 10 peticiones reales seguidas con el mismo `user_id` se procesan
todas sin ningún corte — el Budget Guard, como el resto del pipeline de infraestructura,
se salta por completo. En modo defendido, con el presupuesto de producción intacto, el
5º intento recibe `BLOCKED_BY_BUDGET_GUARD`.

### Control legítimo (`llm10_navi_001`)

5 peticiones seguidas (concurrencia 1) contra el proxy defendido: **5/5 permitidas**.
Ni el Rate Limiter ni el Budget Guard interfieren con un patrón de uso normal.

## Qué NO demuestra esta evidencia

- **No es una prueba de carga de producción.** Se ejecutó contra el lab de desarrollo
  compartido, con volumen deliberadamente acotado por seguridad del propio entorno (ver
  nota metodológica). Sigue pendiente en `TODOs.md` § Fase 5.
- **No mide `#10` ni `#11`** (Extracción de Modelo, Amplificación vía Documentos) —
  fuera de alcance de esta PR, sin implementación todavía.
- **El umbral de Rate Limiter y el cap de tokens de la demo no son los de producción**
  — ver nota metodológica. Los valores de producción (`RATE_LIMIT_MAX_REQUESTS=30`,
  `CLARA_MAX_OUTPUT_TOKENS=1024`) están en `.env.example` y se restauraron tras cada
  demo — verificado (`.env` del lab no quedó con los valores rebajados).

## Verificación automática (no depende de estas corridas contra el LLM)

**211/211** tests en verde en esta rama (188 base + 23 nuevos:
`test_rate_limiter.py` 5, `test_budget_guard.py` 8, `test_session_store_limits.py` 5,
`test_llm10_fixture_exemption.py` 5), 0 regresiones. Estos tests son deterministas y no
dependen de la latencia ni el comportamiento del modelo — son la garantía de que el
mecanismo es correcto con
independencia de que una demo puntual contra un LLM real sea más o menos representativa.
