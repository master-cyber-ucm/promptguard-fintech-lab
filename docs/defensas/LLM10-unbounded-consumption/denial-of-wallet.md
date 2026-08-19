# Defensa — Denial of Wallet

> Contra el ataque **#9** del catálogo · [ficha del ataque](../../ataques/LLM10-unbounded-consumption/denial-of-wallet)
> **OWASP LLM10:2025** · **MITRE ATLAS AML.T0034**
> **Módulo principal:** Budget Guard · **Apoyo:** cap de tokens de salida (compartido con `denegacion-de-servicio.md`)

## 1. Qué hay que impedir

Que un volumen de peticiones —incluso por debajo de cualquier rate limit, sostenido en
el tiempo— genere un coste económico significativo en un proveedor de pago por token, o
un coste de cómputo sostenido en un despliegue local. El servicio puede seguir
respondiendo con normalidad; el daño es la factura, no la caída — por eso necesita su
propio control, distinto del Rate Limiter de `denegacion-de-servicio.md`.

| Invariante | Cómo se garantiza |
|-----------|-------------------|
| **I1** — Ningún usuario/sesión supera un presupuesto de tokens declarado | Acumulador con corte duro, verificado antes de cada llamada al proveedor |
| **I2** — El presupuesto se ajusta al coste real del proveedor activo | Tabla €/1M tokens por `LLM_PROVIDER`, no un número fijo agnóstico al proveedor |
| **I3** — Un gasto anómalo genera señal observable | Umbral de desviación sobre el consumo histórico, visible en el SOC |

## 2. Principio de diseño

> El presupuesto se mide en lo que cuesta, no en lo que "parece razonable".

Un límite de "100 peticiones al día" no protege nada si el proveedor cobra por token y
una sola petición puede pedir un resumen de 50 páginas. El corte tiene que estar en la
unidad que el proveedor factura — tokens de entrada + tokens de salida — no en un proxy
indirecto como el número de peticiones.

## 3. Diseño del control

### 3.1 Presupuesto por sesión/usuario/día

Acumulador (extensión de `session_store.py`, o un almacén propio si se necesita
persistencia entre reinicios — a diferencia del historial de conversación, perder el
contador de presupuesto al reiniciar el backend sería un bypass trivial). Corte duro:
al superar el presupuesto, la petición se rechaza ANTES de llamar al proveedor, con un
mensaje explícito (no un error genérico que un atacante confunda con un fallo transitorio
a reintentar).

### 3.2 Coste diferenciado por proveedor

`lab/README.md` documenta 5 configuraciones de proveedor. El Budget Guard necesita saber
cuál está activo (`LLM_PROVIDER`, ya en `.env`) y aplicar su tabla de coste — Ollama
local no tiene coste monetario (el control ahí es de tiempo/CPU, más cercano a
`denegacion-de-servicio.md`), OpenRouter/Groq/NIM sí. Un presupuesto fijo que no
distinga proveedor sobreprotege en local e infraprotege contra un cambio accidental de
`.env` hacia un proveedor de pago.

### 3.3 Alerta de gasto anómalo (integración con el SOC)

El SOC ya existente (`lab/backend/src/soc/`) observa Analysis Events de las defensas —
un Budget Guard encajaría con el mismo patrón (`componente="budget_guard"`, `objetivo=
"presupuesto"`, `accion=ALLOW/SUSPICIOUS/BLOCK`) en vez de crear un sistema de alertas
paralelo. Ver `docs/soc/README.md` — el SOC observa, no decide; el corte real lo hace
el propio Budget Guard antes de llamar al proveedor.

### 3.4 Excepción para el Agente de red-team

`lab/redteam-agent/` genera tráfico intenso y legítimo (una Campaña de varios
Ejercicios × varios Intentos). Un Budget Guard sin excepción lo bloquearía a mitad de
campaña. Diseño propuesto: un rol/flag análogo a `vulnerable=True` en `ChatRequest`
(`origen=redteam-agent` ya existe como valor de Origen, ver `CONTEXT.md`) que exime del
presupuesto pero queda igualmente registrado — no es invisible, es una excepción
declarada.

## 4. Qué NO cubre

- **Coste de tokens de entrada ya procesados en la petición que dispara el corte** — el
  corte protege la siguiente petición, no revierte el coste de la que lo hizo saltar
  (mismo límite que el README de la categoría ya declara).
- **Cambios de precio del proveedor** — la tabla €/1M tokens necesita mantenimiento
  manual; no hay mecanismo de sincronización automática con la API de precios del
  proveedor en este diseño.

## 5. Estado

- [x] Invariantes definidos
- [x] Diseño de los cuatro controles (presupuesto, coste por proveedor, alerta SOC,
  excepción para el Agente de red-team)
- [x] **Implementación del control I1** (presupuesto por usuario, corte duro) —
  `core/budget_guard.py` (20.000 tokens/hora por defecto), cableado en `/chat/proxy`,
  descuenta el consumo REAL tras cada respuesta (`result.usage()`), respeta el flag
  `vulnerable`. Emite Analysis Event `budget_guard` al SOC.
- [x] Tests automáticos — `test_budget_guard.py` (8 casos), 206/206 del backend en verde
- [x] Fixture/escenario de ataque — `llm10_003` (budget_burn) en
  `llm10_scenarios.yaml` + `run_llm10_suite.py`
- [x] Evidencia vulnerable-vs-defendida — ver
  `docs/reports/evidencia-llm10-unbounded-consumption.md`
- [ ] **I2 (coste diferenciado por proveedor) e I3 (alerta de gasto anómalo en el SOC)
  siguen sin implementar** — el guard actual cuenta tokens, no € — necesita la tabla de
  precios por proveedor para I2, y un consumidor en el panel SOC para I3.
- [ ] Tabla real de €/1M tokens por proveedor soportado — pendiente de investigar precios vigentes
- [ ] Extensión de `tool_permissions.yaml` o nuevo `budget.yaml` — decisión de diseño sin tomar (el límite actual vive en `BUDGET_GUARD_TOKEN_LIMIT`, una variable de entorno, no un fichero de config declarativo como el resto del proyecto)
- [ ] Excepción de presupuesto para el Agente de red-team (`origen=redteam-agent`) — diseñada, sin implementar; hoy una Campaña contra `/chat/proxy` consume del mismo presupuesto que un usuario real
