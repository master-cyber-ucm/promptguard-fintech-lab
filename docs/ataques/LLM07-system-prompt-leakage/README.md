# LLM07:2025 — System Prompt Leakage

> **OWASP LLM Top 10 (2025) — LLM07:2025 · MITRE ATLAS AML.T0055**
> Categoría del catálogo. Agrupa **1 ataque** del escenario base de VerdaBank.

## Definición

El modelo revela su **system prompt**, exponiendo configuración, lógica de autorización, reglas de negocio o secretos embebidos. OWASP advierte que el system prompt no es un mecanismo de control de acceso: nunca debe contener datos cuya filtración sea un incidente.

En el escenario bancario la filtración del prompt es **inteligencia para futuros ataques**: conocer los umbrales exactos allana Excessive Agency (#1) y Cross-Context Leakage (#3).

## Por qué es relevante en VerdaBank

El system prompt de Clara (`lab/backend/config/prompts/clara_system.txt`) expone —de forma intencionada para el lab—:

- Límites de transacción: 10.000 € diarios, 5.000 € individuales, approval automático sobre 1.000 €.
- Umbral de activación del antifraude: 3.000 €.
- Secretos simulados: `API_KEY_INTERNAL`, host de DB y bucket S3 de auditoría.

Filtrar esto no es un fin en sí mismo: es el **reconocimiento previo** que hace que el resto de ataques sean precisos.

## Ataques en esta categoría

| # | Ataque | Subcarpeta | Vector |
|---|--------|-----------|--------|
| 5 | System Prompt Leakage | [`filtrado-por-repeticion/`](./filtrado-por-repeticion) | Preguntas indirectas y técnicas de repetición |

## Filosofía de defensa

Defensa doble, **porque el system prompt por sí solo no es fiable**:

1. **Instrucción explícita** en el prompt de no revelar su contenido (capa débil, disuasoria).
2. **Output Auditor**: detecta si la respuesta contiene fragmentos del system prompt o secretos de configuración (regex sobre `api_key_internal`, `s3://`, `db-banking`, límites numéricos exactos).

El principio: **asumir que el prompt se va a filtrar** y diseñar el resto del sistema (límites, secretos) para que esa filtración no sea un incidente. Los secretos reales nunca viven en el prompt.

## Mapeo normativo

- **GDPR** Art. 5.1.c (minimización) → no embeber secretos reales en el prompt.
- **EU AI Act** Art. 13 (trazabilidad) → registrar intentos de extracción en el Compliance Logger.
- **DORA** Art. 12 → análisis post-incidente de los intentos de leakage.
