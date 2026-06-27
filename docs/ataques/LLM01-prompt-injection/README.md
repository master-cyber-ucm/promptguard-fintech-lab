# LLM01:2025 — Prompt Injection

> **OWASP LLM Top 10 (2025) — LLM01:2025 · MITRE ATLAS AML.T0051**
> Categoría del catálogo. Agrupa **2 ataques** del escenario base de VerdaBank.

## Definición

Un *prompt injection* ocurre cuando una entrada manipula el comportamiento del LLM de forma no intencionada, **sobrescribiendo restricciones, el rol asignado o las instrucciones del sistema**. Es la vulnerabilidad fundamental del canal conversacional y el **vector de entrada de la mayoría del resto del catálogo**.

OWASP distingue dos formas, **ambas presentes en este escenario**:

- **Inyección directa**: el payload lo escribe el propio usuario en el turno de conversación.
- **Inyección indirecta**: el payload viene oculto en un **contenido externo** que el sistema procesa (documento, imagen, output de una tool) y que el modelo trata como dato.

La distinción importa porque **evaden controles distintos**: la directa se caza en el mensaje del usuario; la indirecta exige sanitizar cualquier contenido no confiable antes de reaches el contexto del modelo.

## Por qué es relevante en VerdaBank

- **Barrera de entrada cero**: cualquier cliente autenticado puede intentarlo, sin herramientas ni conocimiento técnico.
- Es el **punto de partida** de Excessive Agency (#1), Leakage (#3, #5) y PII Harvesting (#6): casi todos los demás ataques del catálogo se apoyan en una inyección previa.
- Los clientes suben nóminas y extractos con asiduidad, lo que hace la variante **indirecta por documento** especialmente realista.

## Ataques en esta categoría

| # | Ataque | Subcarpeta | Vector |
|---|--------|-----------|--------|
| 2 | Prompt Injection Directa | [`directa/`](./directa) | Texto directo del usuario en el chat |
| 7 | Prompt Injection Indirecta — Documento | [`indirecta-documento/`](./indirecta-documento) | Instrucciones ocultas en un PDF/processado por el sistema |

## Filosofía de defensa

**Principio:** ninguna instrucción de usuario —ni ningún contenido externo— puede sobrescribir el system prompt.

**Módulo:** **Input Sanitizer**, clasificador multicapa:

1. Capa 1 — Regex (firmas de inyección conocidas).
2. Capa 2 — Clasificador ML (DistilBERT fine-tuned).
3. Capa 3 — LLM Guard vía PydanticAI.

El mismo pipeline se aplica al **texto extraído de documentos**: un contenido de usuario nunca se considera contexto de confianza.

## Mapeo normativo

- **DORA** Art. 9 (protección ICT) e Art. 15 (robustez) → Input Sanitizer.
- **EU AI Act** Art. 15 (robustez frente a manipulación).
