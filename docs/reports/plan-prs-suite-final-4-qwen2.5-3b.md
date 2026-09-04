# Índice de reportes — suite final 4 / Qwen 2.5 3B

Este archivo es solo un índice. Cada PR tiene un reporte técnico autocontenido para
entregar y revisar por separado. Sigue la misma disciplina que
[plan-prs-suite-final-3](./plan-prs-suite-final-3-qwen2.5-3b.md): documento de diseño
(`pr-NN-*.md`) + evidencia de validación (`pr-NN-validacion.md`) por cada PR, un commit
por PR, sin avanzar al siguiente hasta validar el anterior.

## Origen

Análisis de la ejecución `20260901_190305_qwen2.5-3b`
([run.md](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.md),
[run.json](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.json),
[log](../../lab/audit/logs/suite-final.4.log)), cruzado contra el código de evaluación
(`lab/scripts/evaluations/*.py`). PR 1–7 (suite final 3) ya corrigieron precedencia del
reductor, autorización financiera, cobertura y ablaciones; este ciclo ataca defectos
nuevos, encontrados sobre datos posteriores a esos fixes.

## Backlog de problemas (orden de trabajo)

| # | Problema | Evidencia primaria | Estado |
|---|----------|---------------------|--------|
| PR 8 | El evaluador determinista de ataque no tiene red de seguridad semántica: cuando ningún evento de brecha dispara, declara `EVIDENCE_INSUFFICIENT` sin que un juez revise el texto de la respuesta. | 1.172/2.305 ejecuciones inconclusas; 1.167 de ellas (99,6%) vienen de `method=deterministic`; solo 5 de 1.172 llegaron al juez. `scripts/evaluations/deterministic.py::_no_effect`. | ✅ resuelto |
| PR 9 | *(descubierto validando PR 8, no estaba en el análisis original)* `fixture_loader.py` calcula `FIXTURES_DIR` por defecto asumiendo el layout del host; en el contenedor resuelve a una ruta inexistente y `load_prompts()` devuelve **0 fixtures en silencio** en vez de fallar. Varias aserciones sobre el catálogo completo pasan en falso. Ninguna de las tres formas de arrancar la suite (`make test`, `pytest lab/` documentado en el CLAUDE.md raíz, `cd backend && pytest tests/`) funciona sin conocer manualmente el `PYTHONPATH`/env correcto. | `test_aplicabilidad_por_capacidades.py` ya tenía una aserción de guarda (`len(fixtures) == 11`) que atrapó el 0 silencioso; las demás aserciones sobre catálogo no tienen guarda y pasan vacías. | ✅ resuelto |
| PR 10 | 11 fixtures (`atk_035`, `atk_036`, `atk_037`, `atk_069`, `atk_072`, `atk_076`, `leg_030`–`leg_034`) no tienen ningún target aplicable: cobertura cero, ningún claim sobre su familia es sostenible. | Aviso al inicio de `suite-final.4.log`: "FIXTURES SIN NINGÚN TARGET APLICABLE"; `test_aplicabilidad_por_capacidades.py::test_la_matriz_actual_ejecuta_todos_los_fixtures_cargados` ya especifica la solución objetivo (targets `proxy-document-*`). | ✅ resuelto |
| PR 11 | Reproducibilidad: el run se ejecutó con árbol de trabajo sucio (`GIT_DIRTY=true`); el commit no identifica el código que corrió y el propio run se autodescalifica para agregación. | `run.md` §Procedencia: "árbol sucio ⚠ sí"; `suite-final.4.log` cabecera. | ↩️ revertido 2026-09-02 — ver [pr-11 § Corrección posterior](./pr-11-gate-de-arbol-limpio-por-defecto.md#corrección-posterior-2026-09-02--el-gate-se-retira): el gate bloqueaba `make suite` real por ficheros sucios ajenos al código; se decidió que no aporta valor a este proyecto. Queda solo el aviso pasivo. |
| PR 12 | Confusión entre incapacidad del modelo base y contención defensiva: `SAFE_BUT_UNHELPFUL` domina el fallo funcional (44–49 casos/endpoint) y el éxito legítimo cae al 24–57%, sin que el informe distinga "el modelo no sabe" de "la defensa contuvo". | `run.md` §Utilidad legítima por causa del fallo. | ✅ resuelto |
| PR 13 | Agujeros reales de la defensa `proxy-full`: 0/25 en `OBFUSCATION`, 0/25 en `LLM07` (fuga de system prompt), 7,2% de falsos positivos de defensa. | `run.md` §Incertidumbre por familia, §Utilidad legítima por causa del fallo. | ✅ resuelto parcialmente — ver documento (5/16 fixtures de las dos familias, resto declarado como bloqueador) |

## Fuentes comunes

- [Run Report](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.md)
- [Run JSON](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.json)
- [Suite config](../../lab/audit/runs/20260901_190305_qwen2.5-3b/suite-config.json)
- [Log](../../lab/audit/logs/suite-final.4.log)
- [Catálogo de rúbricas de seguridad](../../lab/backend/config/security-rubrics.yaml)

## Cierre del ciclo

Los seis PR (8–13) están implementados, validados con evidencia real (tests
unitarios + reanálisis contra `evaluate.py`/`report.py`/el backend en marcha, sin
mocks donde fue posible) y commiteados uno a uno, sin avanzar al siguiente sin
cerrar el anterior. PR 13 queda con alcance parcial explícitamente declarado
(5/16 fixtures de OBFUSCATION+LLM07; el resto son bloqueadores anotados, no
adivinados) — es el único de los seis que no cierra el problema al 100%, por
diseño: forzar el resto sin la misma solidez de validación habría repetido el
patrón que PR 8/PR 9 corrigieron en otra capa.

## Nota de alcance

PR 8 es un cambio de datos (configuración de fixtures), no de arquitectura: reutiliza
`HybridAttackEvaluator` y el catálogo de rúbricas ya validados por
`test_security_rubrics.py` y `test_hybrid_attack_evaluator.py`.
