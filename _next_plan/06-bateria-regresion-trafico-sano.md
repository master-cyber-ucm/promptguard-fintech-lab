# Batería de regresión de tráfico sano por defensa

## Descripción del problema

Las defensas se prueban principalmente contra ataques. Cuando bloquean una petición legítima, el informe final sólo muestra un FP agregado y no identifica la capa responsable. Falta una batería estable que proteja la utilidad del producto durante cada cambio.

## Evidencia observada

`proxy-full` rechaza 38 de 70 prompts legítimos. El conjunto contiene bloqueos reales y errores funcionales, visibles en la [sección de detalle de la run](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md). El caso [`leg_021`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_233901_ses_783104617691_1788046741.md) muestra que una petición sana puede ser interceptada antes del modelo.

## Explicación técnica

Una métrica posterior a la suite no evita regresiones: para saber qué cambió hay que reconstruir logs, modelo y perfil. Cada defensa debe tener contraejemplos legítimos que cubran su frontera semántica y una decisión atribuible.

## Alternativas de mejora

### A. Suite de regresión por capa (recomendada)

Etiquetar fixtures legítimos por defensa que no debe bloquearlos: `input_sanitizer`, `gatekeeper`, `pii_shield`, `output_auditor`. Ejecutarlos en CI y persistir `matched_rule`/decisión de cada capa.

### B. Sólo tasa FP global

Detecta una degradación tardía, pero no su causa ni el caso que debe repararse.

## Solución propuesta

Crear un conjunto versionado de tráfico sano con expected result, expectativa de acción y capa permitida. Fallar CI ante cualquier nuevo bloqueo determinista y mandar los casos LLM a revisión de calibración.

## Pruebas de aceptación

1. Cada defensa tiene al menos cinco contraejemplos legítimos.
2. El fallo nombra fixture, capa, regla y respuesta entregada.
3. Se ejecuta con los perfiles `output` y `full` antes de fusionar cambios.
