# Índice de reportes — suite final 3 / Qwen 2.5 3B

Este archivo es solo un índice. Cada PR tiene un reporte técnico autocontenido para entregar y revisar por separado.

## Orden y dependencias

```text
PR 1 Evaluador y trazas ──┬──> PR 3 Reanálisis y métricas
                          ├──> PR 4 Cobertura y denominadores
                          ├──> PR 5 Baseline/full y ablaciones
                          └──> PR 6 Utilidad, resiliencia y rendimiento

PR 2 Autorización financiera (P0 independiente)
```

PR 1 y PR 2 son críticas e independientes. PR 3 depende estrictamente de PR 1. PR 4, PR 5 y PR 6 pueden desarrollarse en paralelo después de PR 1, coordinando sus contratos de datos.

## Reportes individuales

1. [PR 1 — Corregir el evaluador y la deduplicación de trazas](./pr-01-evaluador-y-deduplicacion-de-trazas.md)
2. [PR 2 — Endurecer la autorización de operaciones financieras](./pr-02-autorizacion-operaciones-financieras.md)
3. [PR 3 — Reanalizar y unificar métricas y tablas heredadas](./pr-03-reanalisis-y-unificacion-de-metricas.md)
4. [PR 4 — Corregir cobertura, aplicabilidad y denominadores](./pr-04-cobertura-y-denominadores.md)
5. [PR 5 — Diseñar baseline/full comparables y añadir ablaciones](./pr-05-baseline-full-y-ablaciones.md)
6. [PR 6 — Mejorar utilidad, resiliencia y rendimiento](./pr-06-utilidad-resiliencia-y-rendimiento.md)

## Fuentes comunes

- [Análisis maestro](./analisis-suite-final-3-qwen2.5-3b.md)
- [Run Report](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.md)
- [Run JSON](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.json)
- [Coverage Plan](../../lab/audit/runs/20260831_193511_qwen2.5-3b/coverage-plan.json)
- [Execution Ledger](../../lab/audit/runs/20260831_193511_qwen2.5-3b/execution-ledger.jsonl)
- [Provenance](../../lab/audit/runs/20260831_193511_qwen2.5-3b/provenance.json)
- [Log](../../lab/audit/logs/suite-final.3.log)

## Puerta de implementación

Los documentos proponen alcance y solución; no modifican producto ni artefactos del run. Antes de implementar, el líder técnico debe aprobar al menos la precedencia del reductor de PR 1, el límite de autorización de PR 2 y la matriz experimental de PR 5.

