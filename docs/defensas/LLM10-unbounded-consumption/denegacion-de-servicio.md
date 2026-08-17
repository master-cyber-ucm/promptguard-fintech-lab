# Defensa — Denegación de Servicio

> Contra el ataque **#8** del catálogo · [ficha del ataque](../../ataques/LLM10-unbounded-consumption/denegacion-de-servicio)
> **OWASP LLM10:2025** · **MITRE ATLAS AML.T0029**
> **Módulo principal:** Rate Limiter · **Apoyo:** cap de tokens de salida, cota de sesiones

## 1. Qué hay que impedir

Que el volumen, tamaño o repetición de peticiones agote cómputo o memoria hasta
degradar o tumbar el servicio — sin que ninguna petición individual sea, en sí misma,
un ataque de inyección o fuga. Ver `docs/ataques/.../denegacion-de-servicio/01-mapeo-
taxonomico.md` para los tres huecos concretos ya verificados en el código del lab.

| Invariante | Cómo se garantiza |
|-----------|-------------------|
| **I1** — Ninguna IP/usuario supera N peticiones/minuto | Rate limiter delante de `/chat/*`, fuera del código de negocio |
| **I2** — Ninguna generación produce más de M tokens | `num_predict`/`max_tokens` fijado en cada llamada al proveedor |
| **I3** — El número de sesiones vivas está acotado | `session_store.py` con cota + TTL por inactividad |

## 2. Principio de diseño

> El coste de rechazar una petición tiene que ser menor que el coste de procesarla.

Un rate limiter que primero deserializa el body, valida el `user_id` contra la base de
datos y SOLO ENTONCES comprueba la cuota ya perdió la carrera — el atacante consiguió
que el sistema gastara trabajo antes de decir que no. El orden importa tanto como la
regla: la comprobación de cuota va **antes** de tocar cualquier recurso caro (el
proveedor LLM, la base de datos mock, `session_store`).

## 3. Diseño del control

### 3.1 Rate limiting por origen

Ventana deslizante o token bucket sobre IP + `user_id` (ambos, porque un atacante
autenticado con múltiples IPs y un atacante no autenticado con un solo `user_id`
robado son amenazas distintas). Respuesta `429` con `Retry-After` — nunca un `200`
degradado que oculte al cliente legítimo que está siendo limitado.

### 3.2 Cap de tokens de salida

`num_predict` (Ollama) / `max_tokens` (proveedores OpenAI-compatible) en la llamada del
agente pydantic-ai, no como sugerencia en el system prompt — ver la nota de
`docs/defensas/LLM10-unbounded-consumption/README.md` sobre por qué un límite en
lenguaje natural no es un control real. Valor de referencia: el mensaje más largo que
Clara necesita legítimamente (una consulta de movimientos con contexto) más margen, no
"todo lo que el modelo quiera generar".

### 3.3 Cota y TTL de sesiones

`session_store.py::_store` necesita dos límites que hoy no tiene: número máximo de
entradas (LRU — la sesión más antigua sin actividad se descarta primero) y expiración
por inactividad (una sesión que no recibe un turno en N minutos se libera). Ninguno de
los dos rompe el comportamiento actual para tráfico legítimo: una conversación normal no
se acerca a esos límites.

## 4. Qué NO cubre

- **Ataques distribuidos** (ver limitación general en el README de la categoría).
- **Inputs "caros" pero de tamaño normal** — un prompt corto que fuerza un razonamiento
  largo (p. ej. pedir explícitamente "piensa paso a paso con el máximo detalle posible
  antes de responder") no lo detiene un límite de tamaño de INPUT, solo el cap de
  tokens de SALIDA (§3.2).

## 5. Estado

- [x] Invariantes definidos
- [x] Diseño de los tres controles (rate limit, cap de tokens, cota de sesiones)
- [x] **Implementación** — `core/rate_limiter.py` (token bucket por `user_id`,
  30 peticiones/60s por defecto), `agents/clara_base.py::_default_model_settings`
  (cap de 1024 tokens de salida vía `ModelSettings`), `agents/session_store.py`
  (cota LRU de 1000 sesiones + TTL de 30 min). Cableados en `/chat/proxy`, respetan el
  flag `vulnerable` (mismo mecanismo que el resto del pipeline de defensas).
- [x] Tests automáticos — `test_rate_limiter.py` (5), `test_session_store_limits.py`
  (5), 215/215 tests del backend en verde tras el cambio
- [x] Fixtures/escenarios de ataque — `lab/backend/tests/fixtures/llm10_scenarios.yaml`
  (`llm10_001` flood, `llm10_002` token_burn) + `lab/scripts/run_llm10_suite.py`
- [x] Evidencia vulnerable-vs-defendida — ver
  `docs/reports/evidencia-llm10-unbounded-consumption.md`
- [ ] Validación empírica bajo carga real de producción (esta corrida usa el lab de
  desarrollo con volumen acotado, no un entorno de carga dedicado)
