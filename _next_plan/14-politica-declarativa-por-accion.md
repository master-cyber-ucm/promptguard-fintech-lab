# Gatekeeper con política declarativa por acción

## Descripción del problema

Las comprobaciones de titularidad, límites, aprobación y parámetros prohibidos están repartidas entre tools. Esto facilita inconsistencias: una herramienta nueva puede olvidar un control o usar estados no interpretados por el evaluador.

## Evidencia observada

Las brechas de `proxy-full` se concentran en acciones y cadenas: excessive agency 48,9% y chained attacks 57,1% en el [informe de la run](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md). Los casos [`atk_006`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_182419_ses_a653c278f005_1788027836.md) y [`navi_002`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260830_011043_ses_cba9361f389b_1788052238.md) muestran requisitos distintos y no centralizados.

## Explicación técnica

Una política segura necesita declarar para cada acción: recurso, titularidad, parámetros permitidos, límites, confirmación, alcance y efecto. Si ese conocimiento queda en condicionales locales, resulta difícil revisarlo, probarlo y aplicarlo uniformemente.

## Alternativas de mejora

### A. Archivo de políticas versionado + motor común (recomendada)

Definir por tool reglas declarativas y evaluar todas antes de ejecutar. El motor devuelve `denied`, `pending_confirmation` o autorización, con un motivo estructurado.

### B. Continuar con lógica en cada tool

Es flexible al inicio, pero duplica reglas y aumenta superficie de omisiones.

## Solución propuesta

Introducir una política con: `resource_ownership`, `allowed_args`, `max_amount`, `daily_limit`, `requires_approval_above`, `scope`, `new_beneficiary_policy` y `effect_class`. Las tools sólo ejecutan tras una decisión positiva del motor.

## Pruebas de aceptación

1. Toda tool de escritura tiene política declarada; si falta, falla cerrada.
2. Cambiar un límite no exige modificar código de la tool.
3. La decisión persistida identifica regla y parámetros evaluados.
