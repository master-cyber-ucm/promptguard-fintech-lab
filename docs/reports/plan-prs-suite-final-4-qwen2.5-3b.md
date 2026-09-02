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
| PR 9 | 11 fixtures (`atk_035`, `atk_036`, `atk_037`, `atk_069`, `atk_072`, `atk_076`, `leg_030`–`leg_034`) no tienen ningún target aplicable: cobertura cero, ningún claim sobre su familia es sostenible. | Aviso al inicio de `suite-final.4.log`: "FIXTURES SIN NINGÚN TARGET APLICABLE". | pendiente |
| PR 10 | Reproducibilidad: el run se ejecutó con árbol de trabajo sucio (`GIT_DIRTY=true`); el commit no identifica el código que corrió y el propio run se autodescalifica para agregación. | `run.md` §Procedencia: "árbol sucio ⚠ sí"; `suite-final.4.log` cabecera. | pendiente |
| PR 11 | Confusión entre incapacidad del modelo base y contención defensiva: `SAFE_BUT_UNHELPFUL` domina el fallo funcional (44–49 casos/endpoint) y el éxito legítimo cae al 24–57%, sin que el informe distinga "el modelo no sabe" de "la defensa contuvo". | `run.md` §Utilidad legítima por causa del fallo. | pendiente |
| PR 12 | Agujeros reales de la defensa `proxy-full`: 0/25 en `OBFUSCATION`, 0/25 en `LLM07` (fuga de system prompt), 7,2% de falsos positivos de defensa. | `run.md` §Incertidumbre por familia, §Utilidad legítima por causa del fallo. | pendiente |

## Fuentes comunes

- [Run Report](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.md)
- [Run JSON](../../lab/audit/runs/20260901_190305_qwen2.5-3b/run.json)
- [Suite config](../../lab/audit/runs/20260901_190305_qwen2.5-3b/suite-config.json)
- [Log](../../lab/audit/logs/suite-final.4.log)
- [Catálogo de rúbricas de seguridad](../../lab/backend/config/security-rubrics.yaml)

## Nota de alcance

PR 8 es un cambio de datos (configuración de fixtures), no de arquitectura: reutiliza
`HybridAttackEvaluator` y el catálogo de rúbricas ya validados por
`test_security_rubrics.py` y `test_hybrid_attack_evaluator.py`. PR 9–12 se detallan en
sus propios documentos antes de implementarse, en el momento en que les toca el turno.
