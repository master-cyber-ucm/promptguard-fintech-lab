# Fase 1 — Ataque

> Ver checklist completo en `../ROADMAP.md` (sección "Fase 1 — Ataque"). Este archivo es para
> notas de diseño y decisiones específicas de esta fase.

## Mini-checklist

- [ ] 1.1 Diseño del payload (documento sano + documento comprometido)
- [ ] 1.2 Canal de subida de documentos implementado en el backend
- [ ] 1.3 Ejecución y evidencia capturada
- [ ] 1.4 Borrador del capítulo de ataque (secciones 4.2 y 6.1 parcial del índice del TFM)

## Notas de diseño del payload

_(pendiente)_

- Objetivo del payload: ¿filtrar saldo/IBAN de un tercero, o forzar una tool (`transferencia_nacional`
  / `bloquear_tarjeta`)?
- Técnica(s) de ocultación elegidas y por qué.
- Relación con `lab/gen_adversarial_pdf.py` y con los fixtures `atk_021`/`atk_022`.

## Decisiones sobre el canal de subida de documentos

_(pendiente — endpoint nuevo vs. campo opcional en `ChatRequest`, librería de extracción de texto)_

## Estructura de carpetas de esta fase

- `payloads/` — documentos generados (PDF/DOCX/XLSX), sanos y comprometidos, más el script que los
  genera.
- `evidencia/` — Session Files, Run Reports, capturas de pantalla relevantes (copias o referencias
  a rutas dentro del repo).
