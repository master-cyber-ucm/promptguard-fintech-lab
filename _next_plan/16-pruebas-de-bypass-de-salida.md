# Suite de bypass para defensas de salida

## Descripción del problema

El Output Auditor y PII Shield deben validar que ningún secreto o dato sensible llegue al cliente bajo transformaciones comunes. Las pruebas actuales pueden usar salida cruda de auditoría, por lo que primero debe corregirse la separación entre raw y delivered response.

## Evidencia observada

[`atk_046`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_210543_ses_9f292e9541d5_1788037537.md) contiene un marcador de sustitución seguido de texto crudo sensible, y hoy el evaluador lo interpreta como fuga. Este caso demuestra que la prueba debe inspeccionar la salida entregada, no el log forense.

## Explicación técnica

Los detectores normalizan algunas variantes, pero los secretos pueden aparecer troceados, codificados, traducidos o mezclados con caracteres invisibles. Un test de literal exacto no cubre equivalencia legible para un humano.

## Alternativas de mejora

### A. Matriz generativa de transformaciones (recomendada)

Para cada secreto canónico, generar espacios, guiones, Unicode invisible, Base64, fragmentación, mayúsculas, traducción y referencias parciales. Verificar `client_response` y registrar la capa que intervino.

### B. Fixtures manuales aislados

Son fáciles de leer, pero dejan huecos al crecer el conjunto de evasiones.

## Solución propuesta

Combinar fixtures nombrados de regresión con generadores deterministas de variantes. Añadir contraejemplos legítimos (importes, IDs y texto técnico permitido) para vigilar FP.

## Pruebas de aceptación

1. Ninguna variante sensible aparece en `delivered_response`.
2. La salida cruda puede contenerla sin afectar la métrica de exposición.
3. Cada nueva evasión reproducible se convierte en fixture permanente.
