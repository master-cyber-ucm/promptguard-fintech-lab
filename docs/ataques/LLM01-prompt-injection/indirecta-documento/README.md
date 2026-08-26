# Prompt Injection Indirecta — Documento

> Ataque **#7** del catálogo — Escenario Base.
> **OWASP LLM01:2025 · MITRE ATLAS AML.T0051.001** — Indirect Prompt Injection

## Resumen

Los clientes de VerdaBank suben **documentos financieros** (nóminas, extractos) con frecuencia. Este vector permite **inyectar instrucciones sin escribir nada sospechoso en el chat**, evadiendo la vigilancia visual del Input Sanitizer sobre el texto del usuario.

Es la variante **indirecta** de Prompt Injection: el payload no viene del mensaje del usuario, sino de un contenido que el sistema procesa como dato.

## Vector de ejecución

El atacante prepara un documento con instrucciones ocultas:

- Texto en **color blanco sobre fondo blanco**.
- Fuente a **tamaño 1pt**.
- Instrucciones embebidas en metadatos o en capas del PDF.

El sistema extrae el texto del documento y lo **inyecta en el contexto del LLM** junto con el documento legítimo. El modelo procesa el texto extraído como una instrucción más.

## Relevancia en VerdaBank

- Flujo realista: los clientes ya suben nóminas y extractos a Clara.
- Evade la supervisión humana del mensaje de chat (no hay nada sospechoso a la vista).
- Punto de entrada para Excessive Agency (#1) o Leakage (#3, #5) sin tocar el input de texto.

## Defensa que lo mitiga

**Principio**: el texto extraído de cualquier documento pasa por el **mismo pipeline del Input Sanitizer** que el texto directo.

- **Los documentos de usuarios nunca se consideran contexto de confianza.**
- El Input Sanitizer trata el texto extraído del PDF como input no confiable (regex + ML + LLM Guard).
- Separación semántica entre el contenido del documento y el prompt del usuario en el contexto del modelo.

> Nota de alcance: la extracción de texto del documento (PDF parsing) y los vectores vía imagen/EXIF/OCR se tratan en las **Extensiones 2 (Multimodal)** del catálogo. Aquí se cubre la inyección por **texto** embebido en documentos.

## Payloads disponibles en el lab

Fixture `lab/backend/tests/fixtures/attack_prompts.jsonl`:

- **Sin payload específico todavía.** Pendiente de diseñar (generación de PDF adversarial: `lab/gen_adversarial_pdf.py` ya existe como utilidad base).

## Estado

- [x] Definido en el catálogo
- [ ] Payloads diseñados (PDF con instrucciones ocultas)
- [ ] Pipeline de extracción de texto del documento implementado
- [ ] Ejecutado contra Clara (modo vulnerable)
- [ ] Evidencia capturada
- [ ] Defensa validada (Input Sanitizer sobre texto extraído)
