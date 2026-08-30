# Golden set manual para validar evaluación y defensas

## Descripción del problema

No existe una referencia humana compacta con veredictos confiables para comprobar si el evaluador y las métricas están bien calibrados. Sin ella, una mejora puede cambiar números sin saber si se acerca a la realidad.

## Evidencia observada

La run mezcla casos mitigados que se contabilizan como brecha y fallos reales de utilidad; por ejemplo [`atk_017`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_183718_ses_a1f5c4f57f6b_1788028626.md) y [`leg_021`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_233901_ses_783104617691_1788046741.md). Un conjunto revisado por humanos permite separar ambas clases.

## Explicación técnica

El golden set es un subconjunto pequeño, estable y versionado de sesiones con salida entregada, efectos de tools y etiqueta humana. No sustituye la suite completa: sirve como oráculo de regresión de la instrumentación.

## Alternativas de mejora

### A. 40–60 sesiones estratificadas (recomendada)

Incluir 20 bloqueos correctos, 20 permitidos correctos y 10–20 ambiguos, cubriendo cada defensa, acciones y multi-turno. Dos revisores etiquetan los ambiguos y documentan desacuerdos.

### B. Revisar toda la suite manualmente

Da más cobertura, pero es demasiado costoso para iterar con frecuencia.

## Solución propuesta

Versionar las sesiones y etiquetas con criterios explícitos: exposición al cliente, efecto ejecutado y utilidad. No modificar etiquetas para perseguir una métrica; toda revisión requiere changelog.

## Pruebas de aceptación

1. El golden set se ejecuta antes de publicar cambios del evaluador.
2. Cada etiqueta enlaza a evidencia y criterio.
3. Los desacuerdos humanos se conservan, no se silencian.
