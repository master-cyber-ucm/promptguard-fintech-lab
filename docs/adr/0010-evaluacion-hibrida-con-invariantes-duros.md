# Evaluación híbrida con invariantes duros

Estado: **aceptado**.

Las evaluaciones incorporan dos modos híbridos: `hybrid` para peticiones legítimas, donde un juez semántico revisa solo ausencia de evidencia declarada como recuperable, y `hybrid_attack` para ataques, donde un juez de seguridad revisa únicamente la ausencia de una brecha determinista. Las comprobaciones que prueban una vulneración o acción sensible son terminales en ambos modos. Se elige esta separación para evitar que un proxy de observabilidad incompleto convierta un defecto funcional o una respuesta válida en un falso positivo de seguridad, sin delegar en un LLM la autoridad de rebajar una violación verificable.

## Considered Options

- Mantener el evaluador binario: simple y reproducible, pero confunde mecanismo no observado con seguridad y funcionalidad.
- Reemplazar el determinismo por un juez para todos los fixtures: más flexible, pero introduce variabilidad y puede ocultar acciones peligrosas verificables.
- Evaluación híbrida explícita por fixture (elegida): incrementa el contrato y la calibración necesaria, pero conserva los controles fuertes y clasifica las ambigüedades de forma auditable.

## Consequences

- Los informes tendrán una disposición adicional a `passed`/`verdict` y dejarán de presentar indistintamente todos los fallos legítimos como falsos positivos de seguridad.
- Los fixtures que permitan una respuesta sin Tool deben declarar una rúbrica; no habrá relajación implícita global.
- La indisponibilidad, baja confianza o salida no válida del juez reduce cobertura y produce `INCONCLUSIVE`.
