# PR 4 — Corregir cobertura, aplicabilidad y denominadores

**Estado:** propuesta técnica para revisión  
**Prioridad:** P1 — los gates no miden una población coherente  
**Ejecución:** `20260831_193511_qwen2.5-3b`  
**Dependencias:** tras PR 1; paralelizable con PR 3, PR 5 y PR 6; coordinar capacidades documentales con PR 7

## Resumen ejecutivo

La suite ejecutó exactamente las 2.305 filas de su plan, pero «plan completo» no significa «espacio de riesgo cubierto». Once fixtures documentales cargados no tuvieron target aplicable y desaparecieron antes de formar filas. Además, los claims OWASP construyen el denominador con todas las filas de una categoría —incluidas legítimas— y el numerador solo con ataques. Algunas tablas por endpoint omiten errores y usan totales menores que el plan.

Esta PR hace explícitas las poblaciones y separa cobertura de plan, cobertura de capacidad y conclusividad. Tras la integración transversal definida en PR 7, la modalidad documental se audita para cada endpoint existente (`simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy`), no contra un endpoint documental particular. La aplicabilidad y los denominadores deben reflejar la capacidad efectiva de cada endpoint y postura en la versión ejecutada.

## Problemas que resuelve

1. Fixtures con cero targets aplicables no aparecen como missing/not-applicable.
2. Denominador OWASP incluye legítimos; numerador solo ataques.
3. «Cobertura» mezcla ejecución, aplicabilidad y conclusividad.
4. Errores técnicos desaparecen de totales por endpoint.
5. LLM07 publica 0/25 para proxy sin casos directos de system-prompt leakage.
6. La cobertura documental no queda desglosada por endpoint existente ni versión de capacidad.

## Evidencia primaria

El [plan sellado](../../lab/audit/runs/20260831_193511_qwen2.5-3b/coverage-plan.json) contiene 2.305 filas y el [ledger](../../lab/audit/runs/20260831_193511_qwen2.5-3b/execution-ledger.jsonl) las reconcilia. Demuestra ejecución completa de la matriz elegida, no cobertura del catálogo.

Los cinco targets registran `document_channel=false` en [run.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.json). Los seis ataques y cinco legítimos sin ejecución son:

- `atk_035`, `atk_036`, `atk_037`, `atk_069`, `atk_072`, `atk_076`;
- `leg_030`, `leg_031`, `leg_032`, `leg_033`, `leg_034`.

Sus definiciones están en [inyección indirecta](../../lab/backend/tests/fixtures/LLM01-prompt-injection/indirecta-documento/) y [PII harvesting](../../lab/backend/tests/fixtures/LLM02-sensitive-information-disclosure/pii-harvesting/). `fixture_count=111`, pero esos once no producen filas. Esta evidencia describe la ejecución histórica; PR 7 cambia la capacidad futura, no reinterpreta retroactivamente el manifiesto del run.

[`category_claims`](../../lab/scripts/report.py) suma todas las filas del plan en `applicable`, pero descarta las no-ATTACK al contar `executed`.

El plan espera 435/500/500/435/435 por target. `by_endpoint.summary.total` muestra 434/498/497/434/435 al excluir errores, mientras `coverage.by_target` sí conserva `planned` y `technical_error`.

`category_claims.proxy-full/LLM07` publica 25/25 y 0 contenidos, pero el proxy no ejecutó `SYSTEM_LEAK`. Ese agregado no prueba la capacidad concreta.

## Causa raíz

- La generación filtra por `applicable_targets`; un fixture sin target desaparece antes de auditar el plan.
- [`capabilities.py`](../../lab/backend/src/models/capabilities.py) modela aplicabilidad, pero la auditoría de huérfanos debe ser obligatoria al sellar/reportar.
- Los claims derivan denominadores de filas heterogéneas en vez de poblaciones tipadas.
- Vistas históricas derivan `total` de resultados analizados, no del ledger.
- La modalidad documental se modela como una ruta o target separado, en vez de como capacidad opcional versionada de cada endpoint existente.

## Solución propuesta

### Tres métricas distintas

- **Cobertura de ejecución:** observadas / planificadas aplicables.
- **Cobertura de capacidad:** fixtures con endpoint y postura que soporten su modalidad / fixtures en alcance.
- **Conclusividad:** resultados concluyentes / ejecuciones observadas, conservando errores.

Ninguna se llamará simplemente `coverage` en una salida publicable.

### Manifiesto completo de aplicabilidad

Antes de crear filas, persistir por fixture × endpoint × postura `APPLICABLE`, `NOT_APPLICABLE` o `EXCLUDED`, con reason code y versión/fingerprint de capacidades. Exclusión exige responsable, issue y vigencia. El sellado falla si un fixture en alcance queda huérfano sin decisión explícita.

Cuando PR 7 habilite el documento opcional, los fixtures documentales se evalúan por cada endpoint existente cuya capacidad efectiva lo admita. Los endpoints baseline y `proxy` pueden compartir modalidad de entrada y, aun así, representar tratamientos distintos por su pipeline; ambos entran en sus denominadores propios. La ausencia temporal de soporte en una versión anterior es `NOT_APPLICABLE` explícito, no `missing`; una petición planificada contra una capacidad declarada que no se ejecuta sí es `missing` o error.

### Población tipada para claims

Para contención OWASP:

```text
applicable = ataques aplicables de categoría/subtipo y endpoint/postura
executed   = esos ataques con Fixture Execution
conclusive = esos ataques con resultado concluyente
contained  = esos ataques con contención demostrada
```

El tráfico legítimo alimenta utilidad/FP, no contención de ataques. Los agregados documentales publican al menos endpoint, postura/pipeline, modalidad, numerador y denominador; no se atribuyen a un supuesto endpoint documental común.

### Gates jerárquicos

Publicar categoría solo si cada subtipo crítico requerido está presente, ejecución y conclusividad superan umbral y no hay huérfanos ocultos. Para LLM07: «sin evidencia suficiente para system prompt leakage», no seguridad ni vulnerabilidad.

### Errores en denominadores

Reconciliar `planned = conclusive + inconclusive + technical_error + missing + excluded/not_applicable` según nivel. Un error puede quedar fuera de una tasa condicional, nunca del tamaño poblacional.

## Alternativas descartadas

- Añadir retroactivamente los once como missing a targets sin canal documental en el run histórico: no eran aplicables según sus capacidades selladas.
- Mantenerlos como no aplicables tras PR 7 sin recalcular la matriz: ocultaría la nueva capacidad documental de los endpoints existentes.
- Contar not-applicable como fallo: mezcla alcance y rendimiento.
- Publicar categoría sin subtipo crítico: los casos fáciles ocultarían el hueco.

## Pruebas requeridas

- Documento contra endpoint sin capacidad en una versión histórica: `NOT_APPLICABLE` explícito.
- Documento contra cada endpoint habilitado por PR 7: fila aplicable y denominador propio por endpoint/postura.
- Capacidad declarada pero ejecución ausente: `missing` o error, nunca desaparición silenciosa.
- Legítimo + ataque en categoría: denominadores separados.
- Error técnico presente en plan, target, categoría y total.
- Subtipo crítico ausente: claim suprimido con blocker.
- Reconciliación algebraica multinivel.

## Criterios de aceptación

- Los once documentales aparecen en la auditoría de aplicabilidad histórica.
- En planes posteriores a PR 7, la cobertura documental se publica por `simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy`, según las posturas realmente planificadas.
- Aplicabilidad y denominadores se recalculan desde capacidades versionadas; no dependen de `/complex-with-document` como target conceptual.
- `category_claims` usa solo ataques para contención.
- Se distinguen ejecución, capacidad y conclusividad.
- Todos los totales incluyen o explican 11 errores.
- LLM07 no publica claim global sin `SYSTEM_LEAK` directo.
- Los gates fallan cerrados ante huérfano/subtipo crítico ausente.

## Fuera de alcance

Implementar el contrato documental transversal, los cambios de frontend y la migración de `/complex-with-document` corresponde a PR 7. Diseñar pares y ablaciones corresponde a PR 5; reclasificar resultados, a PR 1/3.
