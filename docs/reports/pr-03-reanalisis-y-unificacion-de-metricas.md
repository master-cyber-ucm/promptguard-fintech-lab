# PR 3 — Reanalizar y unificar métricas y tablas heredadas

**Estado:** propuesta técnica para revisión  
**Prioridad:** P1 — evita publicar cifras incompatibles  
**Ejecución:** `20260831_193511_qwen2.5-3b`  
**Dependencia obligatoria:** PR 1

## Resumen ejecutivo

La ejecución puede reanalizarse sin invocar de nuevo el modelo, pero hoy ofrece dos narrativas incompatibles. El reporte nuevo distingue resultados, evidencia, utilidad y falsos positivos de defensa; una tabla legacy llama «bloqueo» a cualquier ausencia de brecha y «FP histórico» a todo fallo funcional. En `proxy-full`, esa tabla muestra 99,3 % de bloqueo y 57,1 % de falsos positivos, mientras el falso positivo defensivo nuevo es 5/70, o 7,1 %.

Esta PR regenera los derivados después de PR 1 y asegura que cada métrica tenga nombre, unidad, denominador y fuente únicos. No cambia fórmulas de cobertura —PR 4— ni respuestas del modelo.

## Problemas que resuelve

1. Agregados construidos con clasificaciones afectadas por PR 1.
2. Métricas legacy y nuevas con etiquetas aparentemente equivalentes.
3. Mezcla de unidades: 121 evaluaciones de fuga no son 121 sesiones.
4. Siete errores en consola frente a once en Analyze Pass.
5. El log contiene salida posterior ajena al run.

## Evidencia primaria

- Derivados actuales: [run.md](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.md) y [run.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.json).
- Fuentes para reanálisis: [ledger](../../lab/audit/runs/20260831_193511_qwen2.5-3b/execution-ledger.jsonl), [plan](../../lab/audit/runs/20260831_193511_qwen2.5-3b/coverage-plan.json) y 2.305 Session Files.
- El [log](../../lab/audit/logs/suite-final.3.log) cierra con `2198 correctos · 100 bloqueados · 7 errores técnicos`; el Analyze Pass registra **11**: cuatro `ReadTimeout` y siete `BackendError`.
- El mismo log imprime después `proxy-full = 99,3 % / 0,7 % / 57,1 %` y texto sobre commits posteriores, evidencia de que su cola no pertenece solo a esta ejecución.
- `run.json` registra 35 `SAFE_BUT_UNHELPFUL`, 5 `DEFENSE_FALSE_POSITIVE` y 30 éxitos de 70 legítimos. El 57,1 % es 40/70 fallos funcionales, no FP defensivos.
- Las 121 fugas de baseline son assessments correspondientes a 64 ejecuciones y 22 fixtures; la unidad cambia el significado.

## Causa raíz

- [`report.py`](../../lab/scripts/report.py) conserva una «Comparación de seguridad (legacy)»: `attack_block_rate` es ausencia de breach y `legitimate_fp_rate` se etiqueta «FP% histórico».
- El runner cuenta errores HTTP/backend; el análisis incorpora además timeouts del modelo. No comparten taxonomía visible.
- Los campos permiten presentar assessment, ejecución y fixture sin unidad explícita.
- El log es append-only y no queda sellado al acabar cada fase.

## Solución propuesta

### Reanalizar, no reejecutar

Después de PR 1:

1. verificar hashes de plan, ledger y sesiones;
2. ejecutar Analyze Pass sobre la misma carpeta;
3. registrar versión/hash del evaluador;
4. revisar manualmente los tres `atk_057` parciales;
5. generar nuevos `run.json`/`run.md`;
6. conservar derivados previos o un diff auditable, sin sobrescritura opaca.

### Contrato de métricas

Cada métrica publicada declara nombre canónico, definición, numerador, denominador, unidad, población, exclusiones, tratamiento de errores/inconclusos, naturaleza descriptiva/causal y versión.

No colapsar `functional_failure_rate`, `defense_false_positive_rate`, `harmful_effect_rate`, `containment_rate`, `leak_assessment_count`, `leaking_execution_count` y `leaking_fixture_count`.

NIST exige TEVV objetivo y documentado, métricas apropiadas, incertidumbre, benchmarks y límites de generalización ([AI RMF — Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)).

### Retirar la tabla legacy de la vista principal

Recomendación: eliminarla. Si se necesita continuidad histórica, moverla a un apéndice, renombrar «FP» a «fallo funcional histórico» y prohibir que alimente titulares/gates.

### Unificar errores y fuentes

Consola y reporte usan `MODEL`, `BACKEND`, `REQUEST_NOT_PROCESSED` y `JUDGE` si aplica, mostrando total y desglose. La carpeta del run es autoritativa. El log incorpora marcadores inicio/fin con `run_id`; cualquier salida posterior queda fuera.

## Alternativas descartadas

- Editar solo Markdown: se desincroniza de JSON.
- Mantener ambos juegos con los mismos nombres: perpetúa ambigüedad.
- Volver a ejecutar el modelo: mezcla corrección con nueva muestra.

## Pruebas requeridas

- Golden tests del contrato y renderizado.
- Reconciliación assessment → ejecución → fixture.
- Snapshot que prohíba `FP` sin definición/denominador.
- Igualdad de errores/desglose entre consola y reporte.
- Idempotencia del Analyze Pass.
- Diff de clasificaciones antes/después con razón.

## Criterios de aceptación

- Un único valor canónico por métrica.
- `57,1 %` no se presenta como FP defensivo; `5/70 (7,1 %)` sí.
- `121` se etiqueta como assessments y se acompaña de 64 ejecuciones/22 fixtures al resumir.
- Consola y reporte explican los mismos 11 errores.
- Derivados trazables al evaluador, plan, ledger y sesiones.
- No se publica causalidad mientras `causal_comparison.comparable=false`.

## Fuera de alcance

Aplicabilidad y denominadores son PR 4; nueva ejecución comparable, PR 5; comportamiento de defensas, PR 2/6.

