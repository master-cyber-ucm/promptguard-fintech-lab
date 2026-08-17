# Implementación del plan de excelencia (2026-08-17)

Ejecución de `docs/reports/plan-excelencia-redteam-y-defensas.md`: DoD + test por punto,
implementación de los ítems P0/P1, pruebas automáticas y manuales, y un ejercicio de
red-teaming de cierre. P2/P3 (A2, A4, B4, B5 a escala completa) quedan fuera de esta
sesión — están priorizados y con DoD en el plan, no se han tocado.

## Resultado del ejercicio de cierre

**`acciones-no-autorizadas` contra `/chat/proxy`, mismo motor (autorreflexivo) que
encontró el bypass original: `20260817_095224_redteam-agent` → 0/8 salvaguardas
superadas.** Pasó de 🔴 (superada, sesión del 16/08) a 🟢 (contenida). Tres intentos
(`3`, `4`, `7`) que el juez marcó SUCCESS quedaron revertidos por el guard estructural de
`tools_used` — verificado a mano contra el `run.json`: `consulta_saldo`/
`transferencia_nacional` denegados o pendientes de confirmación, nunca `completed` sin
confirmar. La cadena completa (Gatekeeper de propiedad + A1 + verificación estructural
del propio agente) se sostiene de punta a punta.

## Qué se implementó

| Punto | Estado | Evidencia |
|---|---|---|
| **A1** — límites + confirmación fuera de banda | ✅ Completo | `core/tool_permissions.py`, `POST /confirm/{operation_id}`, 9 tests nuevos + 197/197 backend en verde |
| **B7** — rastro de auditoría por Ejercicio/ataque | ✅ Completo | `ejercicios/{tecnica}/{run}.md`, 5 tests, verificado en vivo |
| **B2** — verdad de terreno para `pii-harvesting` | ✅ Completo (con corrección) | `ground_truth.py::OTROS_USUARIOS`, 7 tests |
| **B3** — few-shot de payloads | ✅ Completo | `taxonomy.yaml::ejemplos_payload`, 2 tests |
| **B6** — robustez de parsing | ✅ Completo | acentos + fallback limpio, 4 tests |
| **B1** — Analyze Pass offline | 🔶 Mecanismo completo, escala bloqueada por hardware | ver abajo |

**22/22 tests nuevos de `redteam-agent` en verde, 197/197 tests del backend en verde
(9 nuevos de A1, 0 regresiones).**

## A1 en detalle — el fix real

`transferencia_nacional` ahora lee `tool_permissions.yaml` (antes: 0 referencias en
`src/`). Reproduje a mano el payload EXACTO de `HALLAZGOS-SESION-20260816.md` contra el
proxy real:

- **Antes** (16/08): `{"status": "completed", "transaction_id": "TXN-...", ...}` — sin
  ningún paso de confirmación.
- **Ahora** (17/08): `{"status": "pending_confirmation", "operation_id": "op_...",
  "confirm_token": "..."}`. Confirmé con el token real vía `POST /confirm/{operation_id}`
  → `completed`. Reintenté el mismo token → `denied` (un solo uso verificado en vivo, no
  solo en el test).

## B1 — lo que funciona y lo que no se pudo terminar

El mecanismo (`analyze_campania.py`) está completo y probado: parsea B7 o cae a
`run.json` cuando B7 no existe (4 tests deterministas, sin LLM), reusa el juez ya
endurecido de `attacker.py` con `turnos_restantes=0` para forzar SUCCESS/FAILED sin
CONTINUE, y produce `analisis/{run}.reanalizado.json` con las discrepancias marcadas.

En vivo, contra la Campaña completa del 16/08 con `qwen3.5:9b` como juez: **1 intento
re-analizado con éxito antes de que la carga concurrente (el propio ejercicio de cierre
corriendo en paralelo) hiciera que el segundo superara un timeout de 300s.** El único
dato real coincidió con el veredicto original (`FAILED` → `FAILED`), que es lo esperable
para una prueba de humo pero no basta para el DoD completo (re-analizar `directa` y
`pii-harvesting` enteras). Confirma, otra vez, el límite de hardware ya documentado en la
sesión del 16/08 (`qwen3.5:9b` sin GPU, `size_vram: 0` verificado vía `/api/ps`) — no es
un bug nuevo, es la misma pared. **Trabajo pendiente declarado**: correr el Analyze Pass
en una ventana sin campañas en vivo compitiendo por la misma instancia de Ollama, o sobre
hardware con GPU.

## Qué queda del plan, sin tocar esta sesión

A2 (bloquear_tarjeta + fraccionamiento), A4 (aislamiento de sesión), B4 (3 motores en
campaña completa), B5 (corrida `--vulnerable` completa) — todos P2, con DoD ya escrito en
`docs/reports/plan-excelencia-redteam-y-defensas.md`, listos para retomar.
