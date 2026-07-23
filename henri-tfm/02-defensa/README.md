# Fase 2 — Defensa

> Ver checklist completo en `../ROADMAP.md` (sección "Fase 2 — Defensa"). Este archivo es para el
> brainstorm de medidas candidatas y la justificación de la(s) elegida(s).

## Mini-checklist

- [ ] 2.1 Brainstorm de medidas candidatas documentado
- [ ] 2.2 Medida(s) elegida(s) e implementada(s)
- [ ] 2.3 Validación (ataque repetido con documento sano y comprometido, defensa activa)
- [ ] 2.4 Borrador del capítulo de defensa (secciones 4.1 y 6.1/6.2 del índice del TFM)

## Brainstorm de medidas candidatas

| Candidato | Qué hace | Por qué podría funcionar | Coste / falsos positivos esperados |
|---|---|---|---|
| Sanitización del texto extraído (mismo pipeline del Input Sanitizer) | Pasa el texto extraído del documento por regex → DistilBERT → LLM Guard, igual que el input directo | Trata el documento como no confiable, igual que ya se hace con el chat | _(pendiente de evaluar)_ |
| Detección de patrones ocultos estilo antivirus | Heurísticas: texto del mismo color que el fondo, fuente <2pt, coordenadas fuera de viewport, firmas conocidas | Ataca directamente el mecanismo de ocultación, no solo el contenido | _(pendiente)_ |
| Separación semántica dato/instrucción | Marca explícitamente en el prompt qué es "documento del usuario" (dato) vs. instrucción del sistema | Reduce la confusión instrucción/dato que describe Greshake et al. (2023) | _(pendiente)_ |
| Conversión forzada a texto plano | Elimina capas, color y tamaño antes de que el texto llegue al LLM (normaliza el documento) | Destruye técnicamente el vehículo de ocultación visual | _(pendiente — no cubre metadatos ni fuera de viewport)_ |
| Normalización/límite de metadatos del PDF | Descarta o trunca `/Title`, `/Subject`, `/Keywords` antes de indexarlos en el contexto | Cierra el vector de metadatos específicamente | _(pendiente)_ |

## Decisión final

_(pendiente — se rellena tras evaluar los candidatos)_

## Estructura de carpetas de esta fase

- `evidencia/` — Session Files, Run Reports, capturas mostrando el ataque bloqueado (y el
  documento sano seguir funcionando sin falsos positivos).
