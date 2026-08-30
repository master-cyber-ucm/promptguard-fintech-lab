# Preservar la procedencia real del modelo en `run.json` y `run.md`

## Descripción del problema

La configuración de la suite declara `qwen2.5:3b`, pero el `run.json` regenerado identifica el modelo como `proxy-input_sanitizer`. El informe toma el último valor de modelo encontrado al recorrer Session Files; ese valor puede ser una etiqueta de pipeline y no el modelo de inferencia.

## Evidencia observada

El [`suite-config.json`](../lab/audit/runs/20260829_151324_qwen2.5-3b/suite-config.json) de la ejecución declara `model: qwen2.5:3b`; el [`run.json`](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.json) y el [informe](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md) muestran una procedencia distinta. Esto impide atribuir las métricas al modelo correcto.

## Explicación técnica

1. El runner persiste el modelo solicitado en `suite-config.json`.
2. Cada sesión también contiene un campo de modelo.
3. `report.py` actualiza la variable `model` mientras recorre sesiones.
4. La última sesión procesada gana, incluso si representa una capa del proxy.

Se mezclan el modelo configurado, el modelo efectivo y el nombre de una defensa.

## Alternativas de mejora

### A. Manifiesto inmutable de la run (recomendada)

Usar `suite-config.json` como fuente de verdad para `requested_model`, conservar por endpoint un `effective_model` obtenido de la respuesta del proveedor y rechazar discrepancias no explicadas.

### B. Elegir el primer/último Session File

Es frágil: el orden de directorios vuelve a decidir una propiedad experimental.

### C. Eliminar el modelo del informe

Evita mentir, pero destruye reproducibilidad.

## Solución propuesta

Versionar un manifiesto con `requested_model`, `provider`, `effective_model`, versión de defensas y hash de fixtures. `report.py` debe leer ese manifiesto, validar coherencia de las sesiones y mostrar discrepancias como error de instrumentación.

## Pruebas de aceptación

1. Regenerar el informe no altera el modelo declarado.
2. Dos endpoints con modelos distintos se informan por separado.
3. Una sesión con etiqueta de defensa no puede sobrescribir el modelo efectivo.

## Implementación realizada — 2026-08-30

Se corrigió la atribución del informe para que el modelo de la run no dependa del
último Session File recorrido.

### Manifiesto y procedencia

Las nuevas suites escriben `suite-config.json` con `schema_version: 2`,
`requested_model`, `provider`, `defense_version` y `fixtures_sha256`. El campo
histórico `model` se conserva durante la transición para lectores anteriores.

`report.py` toma el modelo principal exclusivamente de `requested_model` (o del
campo histórico cuando evalúa una run antigua). Nunca lo reemplaza mientras
recorre sesiones.

Para cada endpoint, el informe recoge los modelos de inferencia observados en sus
Session Files. Las etiquetas de pipeline usadas por bloqueos tempranos —por
ejemplo `proxy-input_sanitizer` o `document-sanitizer`— se excluyen de esa
observación: son componentes defensivos, no modelos.

### Detección de discrepancias

Si un modelo efectivo observado no coincide con el solicitado, `run.json` añade
un elemento a `model_provenance.instrumentation_errors`. `run.md` muestra una
tabla de modelos efectivos por endpoint y enumera estas discrepancias como
errores de instrumentación, sin alterar el modelo declarado de la campaña.

## Estado del fix

**Estado: implementado y validado.**

- Una etiqueta de defensa no puede sobrescribir `requested_model`.
- Endpoints con modelos efectivos distintos quedan desglosados por endpoint y la
  diferencia se registra explícitamente.
- Validación focal: 16 pruebas aprobadas; `py_compile` y `git diff --check` sin
  errores.

Pendiente operativo: ejecutar una suite nueva para materializar el manifiesto v2
y la procedencia por endpoint en evidencia de ejecución real. Las runs antiguas
siguen siendo legibles mediante el campo `model` histórico, pero no disponen del
hash de fixtures ni de la versión de defensas.
