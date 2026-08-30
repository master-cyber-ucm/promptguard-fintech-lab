# Tratar los fallos del juez LLM como `INCONCLUSIVE`

## Descripción del problema

Cuando el juez LLM devuelve un error HTTP, timeout o una respuesta no interpretable, el evaluador actual devuelve `BLOCKED`. En fixtures legítimos (`expected_result: ALLOW`), esa decisión equivale automáticamente a un falso positivo. Un fallo de infraestructura termina alterando una métrica de seguridad o utilidad.

## Evidencia observada

En la run hay evaluaciones de prompts legítimos con `detail: judge error: HTTPStatusError ... 500 Internal Server Error`; por ejemplo, una repetición de [`leg_003_autorizar_apoderado`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260830_005513_ses_7e3465909e42_1788051311.md). El informe consolida estas respuestas como fallos dentro del FP de 54,3%. [Informe de la run](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md).

## Explicación técnica

1. `LLMEvaluator._call_judge()` captura cualquier excepción de red o HTTP.
2. Devuelve `BLOCKED` junto al detalle del error.
3. `evaluate()` compara ese veredicto con `expected_result`.
4. Si se esperaba `ALLOW`, `passed` queda en `false`.
5. `report.py` contabiliza el caso como falso positivo, aunque no hubo una decisión del juez.

La ausencia de una decisión no puede compartir semántica con una negativa de seguridad.

## Alternativas de mejora

### A. Estado explícito `INCONCLUSIVE` con reintentos (recomendada)

Extender `EvaluationResult` con `status: PASS | FAIL | INCONCLUSIVE`. Reintentar sólo errores transitorios (timeout, 429, 5xx) con backoff y límite fijo; si se agotan, conservar la evidencia y excluir el caso del denominador de la métrica principal, informándolo aparte.

### B. Fallar cerrado como ahora

Es conservador para bloquear tráfico en runtime, pero incorrecto para evaluación offline: no distingue indisponibilidad de fallo funcional.

### C. Reintentar indefinidamente

Mejora la cobertura, pero compromete reproducibilidad, duración y coste. Debe evitarse.

## Solución propuesta

Implementar A: tres intentos deterministas, `INCONCLUSIVE` persistido en el bloque `eval`, contador específico en `run.json` y aviso si supera un umbral. La tasa de FP debe mostrar tanto el valor excluyendo inconclusos como la cobertura evaluada.

## Pruebas de aceptación

1. Un 500 del juez tras tres reintentos queda `INCONCLUSIVE`, nunca `BLOCKED`.
2. Un fixture `ALLOW` inconcluso no incrementa FP ni aciertos.
3. El informe muestra número, porcentaje y enlaces de inconclusos.
4. Una respuesta válida `SI`/`NO` mantiene la semántica actual.

## Implementación realizada — 2026-08-30

Se implementó la alternativa A.

### Resultado explícito y reintentos

`EvaluationResult` incorpora `status: PASS | FAIL | INCONCLUSIVE`, además del
campo de compatibilidad `inconclusive`. El bloque `<!-- eval: ... -->` persiste
ambos valores y `run.json` los conserva por fixture.

El juez LLM realiza hasta **tres intentos**. Sólo reintenta errores transitorios:

- timeout y errores de red de `httpx`;
- HTTP `429`;
- HTTP `5xx`.

El backoff determinista es 250 ms y 500 ms antes del segundo y tercer intento.
Un error no transitorio, una respuesta JSON inválida o una salida que no contiene
un veredicto `SI`/`SÍ`/`YES` o `NO` termina como `INCONCLUSIVE` sin reintentos
adicionales.

### Informes y cobertura

Los inconclusos se excluyen de las tasas de bloqueo, brecha, atención legítima y
falsos positivos. El informe muestra el contador de inconclusos y la cobertura de
evaluación; los detalles de cada fixture —incluidos los inconclusos— enlazan su
Session File desde `run.md`.

## Estado del fix

**Estado: implementado y validado.**

- Un 500 simulado se reintenta tres veces y termina en `INCONCLUSIVE`.
- Una salida no interpretable termina en `INCONCLUSIVE` sin reintentos inútiles.
- `SI` y `NO` mantienen la semántica previa del juez.
- Un fixture legítimo inconcluso no aumenta FP y reduce la cobertura, validado
  sobre `_compute_stats()`.
- Suite completa del backend: **250 tests aprobados**; `py_compile` y
  `git diff --check` sin errores.
