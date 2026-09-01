# PR 3 — Evidencia de validación

## Reanálisis real (no reejecución)

1. Backup íntegro del run antes de tocar nada:
   `lab/audit/runs-saves/20260831_193511_qwen2.5-3b_pre-pr1-pr3/` (54 MB, no
   versionado en git — `lab/audit/` está en `.gitignore`, igual que el run original).
2. `docker compose exec backend python scripts/evaluate.py --run audit/runs/20260831_193511_qwen2.5-3b --force`
3. `docker compose exec backend python scripts/report.py --run audit/runs/20260831_193511_qwen2.5-3b --force`

Ningún paso reinvoca el modelo (`qwen2.5:3b`, servido por Ollama): ambos comandos leen
los Session Files ya existentes y re-derivan evaluación/informe.

## Tabla legacy retirada

`grep "Comparación de seguridad (legacy)" run.md` → sin resultados. La sección y las
cuatro filas duplicadas dentro de cada tabla de endpoint (`Bloqueo de ataques`, `Tasa
de brechas`, `Atención legítima`, `Falsos positivos (compatibilidad histórica)`) ya no
se publican. `attack_block_rate`/`legitimate_fp_rate` siguen en `run.json` por
continuidad histórica (documentado en `docs/metricas/contrato-metricas.md`).

## Las tres poblaciones de fuga (assessments / ejecuciones / fixtures)

Verificado contra el run real regenerado — coincide exactamente con el ejemplo que cita
el informe original:

```
| `proxy-baseline` | 121 / 64 / 22 | 50.7% | 33 | ❌ |
```

`121` assessments `CONFIRMED_LEAK`, `64` Fixture Executions distintas, `22` fixtures
distintos. Antes se publicaba solo "121" sin las otras dos poblaciones.

## Contrato de métricas

`docs/metricas/contrato-metricas.md`: nombre canónico, numerador, denominador, unidad,
población, tratamiento de errores/inconclusos y naturaleza descriptiva/causal para
cada métrica de `summary`. Declara explícitamente qué se retiró y por qué.

## Consola ⇄ reporte: mismos errores, misma taxonomía

`run_attack_suite.py` ahora imprime el desglose por fase (`ErrorPhase`:
`CONNECT`/`BACKEND`/`MODEL`/`PARSE`/`PERSIST`/`UNKNOWN`) al terminar, la misma
taxonomía que `error_breakdown()` deriva del ledger para `run.md`. Cada corrida emite
`=== RUN START run_id=... ===` / `=== RUN END run_id=... ===`: cualquier línea de un
log de shell fuera de ese rango no pertenece a la corrida (causa raíz del mismatch
7 vs. 11 del informe original — un log append-only ajeno al código, no un error de
conteo).

## Hallazgo honesto sobre el alcance real del reanálisis

Ver la corrección en `docs/reports/pr-01-validacion.md`: el reanálisis real de este
run concreto no reclasificó ninguna Fixture Execution (el bug de duplicación que PR1
corrige ya no se manifestaba en este dataset al empezar este trabajo). Las cifras de
`run.json`/`run.md` para `system_results` son las mismas antes y después del
reanálisis — lo que cambia es exclusivamente lo que corrige PR3: la tabla legacy
retirada y las tres poblaciones de fuga publicadas por separado.

## Tests

`test_report_resultado_del_sistema.py::test_el_markdown_publica_resultado_del_sistema_y_retira_la_tabla_legacy`
verifica que la sección legacy y el rótulo "FP% histórico" no aparecen en el Markdown
generado. Suite completa: 850/850 en verde.

## Fuera de alcance de este PR (anotado, no resuelto)

`scripts/final_report.py` (agregación entre modelos, `make final-report`) recomputa su
propia versión de `attack_block_rate`/`legitimate_fp_rate` de forma independiente a
`report.py`. No se toca en este PR — el informe original solo cita `report.py`/`run.md`
como superficie afectada; `final_report.py` queda como seguimiento.
