# LLM06:2025 — Excessive Agency

> **OWASP LLM Top 10 (2025) — LLM06:2025**
> Categoría del catálogo. Agrupa **2 ataques** del escenario base de VerdaBank.

## Definición

El LLM ejecuta **acciones (vía tools/plugins) más allá de su autoridad prevista**. OWASP destaca el riesgo de *consequential actions*: operaciones con impacto real e irreversible (transferencias, bloqueos) realizadas sin la validación adecuada. La categoría incluye tanto la ejecución de acciones no autorizadas como el patrón *confused deputy*.

Es la categoría de **mayor impacto económico directo**: en banca, la agency delegada a Clara toca dinero.

## Por qué es relevante en VerdaBank

- Clara tiene acceso directo a tools **irreversibles**: `transferencia_nacional` y `bloquear_tarjeta`.
- En el lab vulnerable, las tools (`lab/backend/src/agents/tools.py`) **no validan propiedad de cuenta, límites ni requieren aprobación**.
- Mayor **ROI** para el atacante: impacto financiero inmediato y cuantificable, sin necesidad de comprometer credenciales.

## Ataques en esta categoría

| # | Ataque | Subcarpeta | Distinción |
|---|--------|-----------|------------|
| 1 | Excessive Agency | [`acciones-no-autorizadas/`](./acciones-no-autorizadas) | Ejecuta una **acción** de alto impacto sin permiso/confirmación (transferencia, bloqueo) |
| 4 | Confused Deputy Attack | [`confused-deputy/`](./confused-deputy) | Abusa de la **sesión legítima delegada** para acceder a datos o actuar sobre terceros |

Ambos abusan de la agency delegada, pero #1 ataca la **acción** (hacer algo que no se debe) y #4 ataca la **delegación** (usar el acceso propio para favorecer a un tercero). En la práctica se solapan, pero el ángulo y los payloads de prueba difieren.

## Filosofía de defensa

**Principio:** el LLM **nunca** decide si puede ejecutar una tool. Esa decisión es **determinista y externa al modelo**.

**Módulo:** **Tool Gatekeeper** (validación RBAC fuera del LLM):

- Compara el `user_id` autenticado con el identificador de cuenta de **cada llamada a tool**.
- Las tools críticas validan `require_own_account: true` y límites por rol (`lab/backend/config/rules/tool_permissions.yaml`).
- Operaciones irreversibles o superiores a un umbral monetario requieren **confirmación humana explícita**.

La clave es **sacar la decisión de autorización del LLM**: por muy convencido que esté el modelo de que la situación es "urgente", el gatekeeper aplica la regla.

## Mapeo normativo

- **EU AI Act** Art. 14 (supervisión humana) → confirmación para operaciones críticas.
- **DORA** Art. 9 → Tool Gatekeeper.
