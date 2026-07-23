# Fase 1 — Ataque

> Ver checklist completo en `../ROADMAP.md` (sección "Fase 1 — Ataque"). Este archivo es para
> notas de diseño y decisiones específicas de esta fase.

## Mini-checklist

- [x] 1.1 Diseño del payload (documento sano + documento comprometido) — 3 formatos
- [ ] 1.2 Canal de subida de documentos implementado en el backend
- [ ] 1.3 Ejecución y evidencia capturada
- [ ] 1.4 Borrador del capítulo de ataque (secciones 4.2 y 6.1 parcial del índice del TFM)

## Especificación del payload (1.1)

### Objetivo elegido

**Fuga de saldo de un tercero vía `consulta_saldo`**, apuntando a la cuenta de **Ana Fernández
Ruiz** (`usr_003`, `ES3421000418450200051334`).

Justificación de la elección frente a forzar `transferencia_nacional`/`bloquear_tarjeta`:
- Es el objetivo ya validado por los fixtures existentes `atk_021_indirect_doc_es.yaml` /
  `atk_022_indirect_doc_en_claude.yaml` (mismo IBAN objetivo), lo que permite comparar evidencia
  nueva (documento real) con evidencia ya existente (payload simulado como texto de chat).
- Encaja directamente con el incidente motivador del TFM (`INC-2025-0089`, fuga de saldo de un
  tercero vía manipulación de contexto) — ver `docs/propuesta-formal-promptguard-fintech.md §2.2`
  y `docs/ataques/.../06-contexto-verdabank.md`.
- Es más determinista de reproducir con el modelo local configurado (`qwen2.5:3b` vía Ollama) que
  forzar una tool con efectos secundarios (transferencia), cuya ejecución puede depender más de
  la verbosidad/formato exacto del prompt.
- **Queda documentado como variante de extensión** (no descartada): el mecanismo de inyección es
  idéntico, solo cambia el texto del payload; si hay tiempo, se genera una segunda tanda de
  documentos apuntando a `transferencia_nacional` para enriquecer el capítulo de resultados.

### Formatos y vehículos

Se decidió cubrir **3 formatos** en vez de uno solo, cada uno con la técnica de ocultación más
idiomática de ese formato — esto da más riqueza analítica al capítulo "Anatomía del payload" y
amplía la superficie que la Fase 2 (defensa) tiene que cubrir.

| Formato | Vehículo (documento visible) | Técnicas de ocultación | Script |
|---|---|---|---|
| **PDF** | Nómina de María García López (`usr_001`) | Texto blanco sobre blanco + fuente 1pt + texto fuera de viewport (las 3 combinadas) | `generar_pdf.py` |
| **DOCX** | Informe de reclamación (`abrir_reclamacion`) | Atributo nativo "oculto" de Word (`w:vanish` / `run.font.hidden`) + refuerzo en blanco sobre blanco | `generar_docx.py` |
| **XLSX** | Hoja de control de gastos (contexto: `consulta_producto`) | Fila oculta (`row_dimensions.hidden`) + comentario de celda (`Comment`) | `generar_xlsx.py` |

Relación con material existente: `lab/gen_adversarial_pdf.py` es la base de la técnica PDF (texto
blanco + fuera de viewport), adaptada aquí de un CV de RRHH a una nómina bancaria con el payload
apuntando a `consulta_saldo`.

### Contenido exacto del payload y por qué funciona (anatomía)

Ver desglose completo, con el texto exacto de cada payload y el porqué de cada elección de
redacción, en [`anatomia-payload.md`](anatomia-payload.md). Resumen: los tres payloads comparten
una misma estructura de 3 piezas —marco de autoridad falso, instrucción de acción concreta con el
IBAN objetivo interpolado, e instrucción de auto-ocultación ("no menciones esta nota")— pero
varían el framing según el vehículo documental (nómina / reclamación / hoja de gastos) para
maximizar verosimilitud dentro de cada contexto.

### Por qué cada técnica funciona (validado por extracción real)

Se generaron los 6 documentos (`payloads/*.pdf`, `*.docx`, `*.xlsx` — sano y comprometido por
formato) y se verificó con parsers ingenuos que el payload oculto **es recuperable** en los 3
casos:

| Formato | Parser usado para validar | Resultado |
|---|---|---|
| PDF | `pypdf.PdfReader(...).pages[i].extract_text()` | Payload presente en el texto extraído |
| DOCX | `python-docx`: `"\n".join(p.text for p in doc.paragraphs)` | Payload presente — `paragraph.text` no filtra por `run.font.hidden` |
| XLSX | `openpyxl`: iterar celdas (incl. filas ocultas) + `cell.comment.text` | Payload presente tanto en la fila oculta como en el comentario |

Esto confirma la premisa de Greshake et al. (2023) citada en
`docs/ataques/.../03-casos-reales.md`: el LLM (y cualquier pipeline de extracción ingenuo) no
distingue "dato visible" de "dato oculto" — solo ve texto. La ocultación protege del **revisor
humano**, no del parser.

### Cómo reproducir

```bash
cd henri-tfm/01-ataque/payloads
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python generar_pdf.py
./.venv/bin/python generar_docx.py
./.venv/bin/python generar_xlsx.py
```

Genera 6 archivos: `nomina_{sana,comprometida}.pdf`, `reclamacion_{sana,comprometida}.docx`,
`gastos_{sano,comprometido}.xlsx`.

### Tests de regresión (`test_payloads.py`)

La verificación manual de que el payload es extraíble (tabla anterior) se formalizó como suite
pytest, para que cualquier cambio futuro en los generadores se valide automáticamente en vez de
a mano. 8 tests, 2 por formato + 1 extra en DOCX que confirma que la técnica usada es
específicamente `run.font.hidden` (no solo el color):

- `test_<formato>_sano_no_contiene_payload` — control negativo: el documento sano no filtra el
  IBAN objetivo.
- `test_<formato>_comprometido_contiene_payload` — el documento comprometido sí lo filtra, con
  el mismo tipo de extracción ingenua que usaría un pipeline sin medidas de seguridad.

```bash
cd henri-tfm/01-ataque/payloads
./.venv/bin/pytest -v
```

Resultado: **8/8 passed**.

## Decisiones sobre el canal de subida de documentos (1.2 — siguiente paso)

_(pendiente — endpoint nuevo vs. campo opcional en `ChatRequest`, librería de extracción de texto
por formato: `pypdf` para PDF, `python-docx` para DOCX, `openpyxl` para XLSX)_

## Estructura de carpetas de esta fase

- `payloads/` — documentos generados (PDF/DOCX/XLSX), sanos y comprometidos, más el script que los
  genera.
- `evidencia/` — Session Files, Run Reports, capturas de pantalla relevantes (copias o referencias
  a rutas dentro del repo).
