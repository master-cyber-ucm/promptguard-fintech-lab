# PR 6 — Mejorar utilidad, resiliencia y rendimiento

**Estado:** propuesta técnica para revisión  
**Prioridad:** P1/P2 — defensa frecuentemente segura, pero poco útil y cara  
**Ejecución:** `20260831_193511_qwen2.5-3b`  
**Dependencias:** después de PR 1; paralelizable con PR 3–5; coordinar instrumentación documental con PR 7

## Resumen ejecutivo

`proxy-full` completa 30/70 solicitudes legítimas. De los 40 fallos, 35 son seguros pero inútiles y cinco falsos positivos reales del Tool Gatekeeper. La campaña dura 10 h 50 min 51 s, registra cuatro timeouts de unos 300 s sin reintento de Fixture Execution y siete errores backend. Los bloqueos pre-modelo son casi instantáneos; los post-modelo tienen p50 16,83 s y p99 76,02 s.

No se deben relajar límites duros para mejorar utilidad. Hay que recuperar tareas legítimas mediante routing, contratos de tool, mensajes accionables y recuperación controlada, haciendo la ejecución resiliente sin sesgo de supervivencia. Cuando haya documentos, estas propiedades se medirán como una capacidad transversal de cada endpoint existente, según PR 7: no se introduce ni se presupone un endpoint documental separado.

## Problemas que resuelve

1. Éxito legítimo de solo 42,9 %.
2. 35 `SAFE_BUT_UNHELPFUL` no causados por un bloqueo defensivo.
3. Cinco FP del Gatekeeper.
4. Cuatro timeouts reintentables sin nueva Fixture Execution.
5. Siete BackendError, concentrados parcialmente en `leg_026`.
6. Resumen inconsistente y ejecución secuencial de casi once horas.
7. Lectura no pareada del coste de latencia.
8. Falta desglose de utilidad, resiliencia y coste documental por endpoint y fase.

## Evidencia primaria

[run.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.json) registra 30 éxitos, 35 `SAFE_BUT_UNHELPFUL` y 5 `DEFENSE_FALSE_POSITIVE`, todos atribuidos a `tool_gatekeeper`.

Los cinco FP están en:

- bloqueo de tarjeta propia: [rep 1](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_044509_ses_9544b63f21174b01bd855788_1788237898.md), [rep 2](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_044647_ses_58c8af8f6f0b47e9b9857e8d_1788237998.md), [rep 3](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_044819_ses_43d39d28ee38451ba3232f00_1788238086.md);
- transferencia entre cuentas propias: [sesión](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_045040_ses_c268b99356df4d5fad104068_1788238227.md);
- información sobre pasos de transferencia (`leg_026`): [sesión](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_054027_ses_3937844e02b04d618dc6d767_1788241198.md).

La consulta de saldo propio falla como `SAFE_BUT_UNHELPFUL` en cinco repeticiones; ejemplo: [sesión](../../lab/audit/runs/20260831_193511_qwen2.5-3b/proxy-full/20260901_043121_ses_a5cdeb19804645fa8dbc0a71_1788237066.md).

`errors` contiene 11 errores: cuatro `ReadTimeout` y siete `BackendError`. [executions.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/executions.json) muestra `attempt_no=1` y `retry_of=null` para las 2.305 ejecuciones.

Latencia `proxy-full`: allowed p50 10.248,3 ms, p95 26.689,9 ms y p99 42.598,8 ms; pre-model p50 0,7 ms; post-model p50 16.828,9 ms y p99 76.019,3 ms. El p95 baseline es 26.212,1 ms, pero la cohorte no es la misma. La ejecución histórica no permite atribuir coste documental por endpoint porque esa capacidad aún no estaba integrada.

## Diagnóstico

- **FP defensivo:** un control intervino sobre tarea legítima. Se corrige en policy/procedencia/clasificación.
- **Seguro pero inútil:** ningún control causó el fallo. Se corrige en capacidad, prompts, tools, errores y affordances.
- **Fallo documental:** se atribuye a una fase explícita —recepción, validación técnica, extracción, defensa, composición, modelo o tool— y al endpoint ejecutado; «documento» por sí solo no es una causa.

Mezclarlos llevaría a relajar defensas para compensar limitaciones del modelo.

## Solución propuesta

### Corregir los cinco FP por intención/procedencia

- Separar consulta informativa de ejecución; explicar pasos no activa escritura.
- Reconocer propiedad explícita sin aceptar valores inventados o procedentes de documentos no confiables.
- Para escrituras, producir propuesta/autorización de PR 2; `AWAITING_CONFIRMATION` es progreso seguro, no FP.
- Reason codes estables y mensajes que permitan continuar.

### Recuperar `SAFE_BUT_UNHELPFUL`

Clasificar las 35 sesiones: tool no llamada, argumentos inválidos, abandono multi-turno, respuesta genérica, falta de datos o contrato de éxito erróneo. Por cluster: estados/errores estructurados, reparación concreta, límites de loops, respuesta determinista para tareas simples y negativa clara cuando falte autorización/dato.

Para solicitudes con documento, conservar el mismo resultado funcional esperado que en su caso lógico equivalente y registrar si el documento era necesario, opcional o irrelevante. Los baselines y `proxy` se analizan por endpoint y postura, respetando que sus pipelines documentales son deliberadamente distintos.

### Reintentos trazables y presupuestados

Reintentar a nivel Fixture Execution solo errores transitorios `retryable`. Cada intento conserva identidad, `attempt_no`, `retry_of`, causa y backoff. Reportar first-attempt, after-retry, número/coste e intentos completos. No reintentar denegaciones, validación determinista ni escrituras de efecto ambiguo.

La extracción documental debe respetar un presupuesto único por petición. No se reintenta automáticamente un archivo inválido, no soportado o que exceda límites; un fallo transitorio posterior a una extracción segura puede reutilizar un artefacto controlado identificado por hash, sin duplicar efectos ni eludir defensas.

### Reducir coste sin sesgar

Concurrencia limitada por target/modelo, backpressure, circuit breaker, timeout por fase, preflight/smoke, checkpoint/resume idempotente y abort gate por error. OpenTelemetry respalda modelar intento, timeout, retry y resultado como eventos correlacionados ([eventos](https://opentelemetry.io/docs/specs/semconv/general/events/)); NIST incluye fiabilidad, robustez y tiempo de respuesta a fallos en seguridad/resiliencia ([AI RMF — Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)).

### Medir por endpoint y fase

Instrumentar recepción/validación de archivo, extracción, sanitizer, detección estructural, separación semántica/tool framing, cola, inferencia, gatekeeper, tools, auditor y serialización cuando cada fase aplique. Publicar por endpoint y modalidad:

- éxito funcional, `SAFE_BUT_UNHELPFUL` y FP defensivo;
- errores y recuperación first-attempt/final;
- latencia y consumo por fase, tamaño y tipo de documento;
- overhead frente al mismo caso lógico sin documento y, solo bajo PR 5, frente al par experimental comparable.

El overhead causal se mide en PR 5 con solicitudes pareadas; aquí no se atribuye causalidad a percentiles heterogéneos. No se agregan resultados bajo una ruta documental ficticia ni se usa `/complex-with-document` como población estable.

## Alternativas descartadas

- Desactivar Gatekeeper: reabre riesgo.
- Reintentar hasta éxito: infla rendimiento y puede repetir efectos.
- Aumentar todos los timeouts: alarga sin corregir determinismo.
- Paralelismo ilimitado: altera errores/latencia por saturación.
- Crear una cohorte basada en un endpoint documental separado: contradice el contrato transversal de PR 7 y oculta diferencias por endpoint.

## Pruebas requeridas

- Regresión de las cinco sesiones FP.
- Golden set legítimo por lectura, información, propuesta y escritura.
- Casos equivalentes con/sin documento en cada endpoint habilitado.
- Archivo inválido, extracción fallida, timeout posterior y reutilización segura por hash.
- Retry transitorio/determinista, máximo, resume y escritura ambigua.
- Idempotencia de ledger y efectos.
- Carga con concurrencia limitada y métricas documentales por endpoint/fase.
- Gate: utilidad mejora sin degradar contención/autorización.

## Criterios de aceptación

- Los cinco FP conocidos se resuelven sin escrituras no autorizadas.
- Los 35 inútiles tienen taxonomía/evidencia y los clusters prioritarios, corrección/prueba.
- Errores retryable generan intentos enlazados; se informan first-attempt y final.
- Resume no duplica ejecuciones, extracción ni efectos.
- Consola/reporte concuerdan en errores, retries y duración.
- Las solicitudes documentales informan utilidad, resiliencia, latencia y consumo por endpoint existente y fase aplicable.
- Ningún informe inventa un endpoint documental separado; la compatibilidad temporal con `/complex-with-document` se etiqueta como adaptador de PR 7.
- Latencia por fase; causal solo con pareado válido.

## Fuera de alcance

PR 2 mantiene el límite duro de autorización; PR 5 diseña comparabilidad; PR 4 cambia denominadores. PR 7 implementa el contrato documental transversal, los límites técnicos y los cambios de frontend; esta PR consume esa capacidad para medir y mejorar utilidad, resiliencia y rendimiento.
