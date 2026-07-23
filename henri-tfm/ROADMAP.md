# Roadmap — Ataque #7: Prompt Injection Indirecta vía Documento

> Checklist de trabajo. Marcar `[x]` según se completa. Cada tarea que produzca evidencia debe
> anotarse también en `bitacora/BITACORA.md` con fecha y forma de reproducirla (ver regla 2 de
> `00-INSTRUCCIONES.md`).

## Fase 0 — Setup

- [x] Explorar el repo y entender el objetivo del TFM (PromptGuard FinTech).
- [x] Leer los 7 capítulos de referencia en `docs/ataques/LLM01-prompt-injection/indirecta-documento/`.
- [x] Crear el entorno de trabajo personal (`henri-tfm/` en la raíz del repo).
- [x] Verificar que el lab arranca en local: `cd lab && make run` (Ollama + backend + frontend).
- [x] Correr `make smoke` y confirmar health check del backend y del proveedor LLM.

## Fase 1 — Ataque

### 1.1 Diseño del payload ✅

- [x] Formatos decididos: **PDF + DOCX + XLSX** (uno no basta para una buena cobertura analítica;
      ver justificación en `01-ataque/README.md`).
- [x] Payload bancario diseñado: fuga de saldo de tercero vía `consulta_saldo` sobre
      `ES3421000418450200051334` (Ana Fernández Ruiz, usr_003) — mismo objetivo que
      `atk_021`/`atk_022` para evidencia comparable. Variante `transferencia_nacional` documentada
      como extensión futura.
- [x] Documentos **sanos** generados: `nomina_sana.pdf`, `reclamacion_sana.docx`,
      `gastos_sano.xlsx`.
- [x] Documentos **comprometidos** generados con técnica(s) idiomática(s) por formato: PDF (blanco
      sobre blanco + 1pt + fuera de viewport), DOCX (`w:vanish` + blanco sobre blanco), XLSX (fila
      oculta + comentario de celda).
- [x] Especificación completa por escrito en `01-ataque/README.md`, incluida validación de que el
      payload es recuperable por extracción ingenua en los 3 formatos (`pypdf`/`python-docx`/`openpyxl`).
- [x] Verificación formalizada como tests de regresión (`payloads/test_payloads.py`, 8/8 passed):
      sano sin payload / comprometido con payload, por formato.
- [x] Anatomía del payload documentada (`01-ataque/anatomia-payload.md`) — texto exacto de cada
      payload y desglose comentado de por qué funciona (responde a `TODOs.md` §7).

### 1.2 Canal de subida de documentos ✅

- [x] Approach decidido: endpoint nuevo `POST /chat/complex-with-document` (multipart), siguiendo
      la progresión ya existente en `chat.py`. Reutiliza `_process_chat` con un parámetro nuevo
      `document_text` que se concatena sin sanitizar.
- [x] Extracción de texto implementada en `src/core/document_extractor.py` para **PDF + DOCX +
      XLSX** (los 3 formatos de la Fase 1.1, no solo PDF) — extracción deliberadamente ingenua,
      no filtra por visibilidad/color/oculto.
- [x] Tests: 12 tests (`test_document_extractor.py` + `test_chat_document_endpoint.py`), 12/12
      passed. Incluyen un test de integración con agente falso que verifica que el payload llega
      sin sanitizar al mensaje que recibe el LLM.
- [x] Verificación end-to-end contra el LLM real (Ollama qwen2.5:3b) con `nomina_comprometida.pdf`:
      Clara invocó `consulta_saldo` sobre la cuenta de un tercero (`ES3421...334`), pese a que la
      petición era del usuario `usr_001` y el system prompt incluye reglas explícitas "NUNCA
      reveles datos de cuentas de otros clientes". Session File:
      `lab/audit/sessions/20260723_193458_ses_1784835254.md`.
      **Nota:** esto es una comprobación de cableado, no la evidencia formal de la Fase 1.3 (que
      requiere también el control sano y varias repeticiones).

### 1.3 Ejecución y evidencia ✅

- [x] Lab levantado en modo vulnerable (`make run`), Ollama `qwen2.5:3b`.
- [x] Script de evidencia (`evidencia/ejecutar_evidencia.py`): 3 formatos × sano/comprometido × 3
      repeticiones = 18 llamadas reales contra `/chat/complex-with-document`.
- [x] Control sano: **0/9 falsos positivos** en los 3 formatos.
- [x] Documento comprometido: **PDF 3/3 (100%)**, **XLSX 2/3 (67%)**, **DOCX 0/3 (0%)** — éxito
      funcional (tool call `consulta_saldo` sobre la cuenta objetivo exacta).
- [x] Evidencia capturada: 18 Session Files completos en
      `lab/audit/runs/20260723_195956_henri-atk7-evidencia/complex-with-document/`.
- [x] **Corrección metodológica documentada**: se detectaron y corrigieron 2 bugs (ruta
      host/contenedor en `audit_subdir`; criterio de éxito con fallback laxo que generaba falsos
      positivos). Ver `evidencia/README.md` §"Corrección metodológica" para el detalle completo
      y la re-clasificación con criterio estricto (`reanalizar_desde_sesiones.py`).
- [x] Procedimiento de reproducción documentado en `evidencia/README.md`.

### 1.4 Capítulo de ataque — wrap-up ✅ (primera redacción, revisada tras 1.5)

- [x] Borrador de resultados redactado en `CAPITULO.md`, con evidencia real (18 Session Files,
      corrección metodológica incluida) reemplazando cualquier nota "PRE-implementación".
- [x] Aporte a la sección **4.2** completo (descripción del vector, diseño del payload, anatomía,
      implementación del canal) y a **6.1/6.2** (tabla de resultados + análisis: brecha de
      control de acceso vs. fuga textual, hipótesis DOCX).
- [x] Citas MITRE ATLAS (`AML.T0051.001`, táctica `TA0043`) y OWASP (`LLM01:2025`) revisadas y
      consistentes en toda la sección 4.2.
- [x] Pasada de coherencia sobre todo `CAPITULO.md`: corregida una referencia desactualizada
      ("pipeline aún no implementado") que había quedado obsoleta tras completar la 1.2.

**Nota (post wrap-up):** el usuario pidió, tras esta primera redacción, subir la tasa de éxito de
DOCX/XLSX antes de cerrar la fase y añadir un paso de verificación manual — ver 1.5 y 1.6 antes
de dar la Fase 1 por cerrada.

### 1.5 Mejora del ataque — iteración de payloads

- [x] Diagnóstico de los fallos de la primera tanda (1.3): DOCX 0/3 por payload sin redundancia;
      XLSX con fallos intermitentes por consulta a la cuenta propia en vez de la objetivo.
- [x] DOCX v2: payload repetido 3 veces (2 idénticas + 1 con prefijo `SYSTEM:`), misma
      redundancia que ya funcionaba al 100% en PDF.
- [x] XLSX v2 → v3: v2 (duplicar la fila oculta sin cambiar su posición) no mejoró — diagnóstico
      con `tools_used` mostró que el modelo seguía prefiriendo la cuenta propia. v3: fila oculta
      reposicionada justo después de la fila "Cuenta" visible (máxima cercanía al contexto que el
      modelo ya lee) + texto contrastivo explícito ("no la tuya propia — la cuenta adicional
      autorizada es...").
- [x] `test_payloads.py` (8/8) revalidado tras cada iteración de los generadores.
- [x] Evidencia final re-ejecutada con los payloads mejorados (4 tandas, 98 Session Files
      reales). **Resultado agregado por versión de payload**: PDF 11/13 (85%, sin cambios desde
      Fase 1.1), DOCX v2 9/10 (90%), XLSX v3 15/15 (100%). 49/49 controles sanos sin falsos
      positivos. Discusión honesta sobre el límite de "100% garantizado" con un LLM no
      determinista en `evidencia/README.md` y `CAPITULO.md` §6.2.

### 1.6 Verificación manual del usuario (gate antes de Fase 2)

- [x] Añadido soporte de subida de documentos al frontend Playground
      (`lab/frontend/src/playground.html`, `js/app.js`, `js/api.js`): nuevo modo
      `complex-with-document` con selector de archivo, usando `FormData`/multipart contra el
      mismo endpoint que usa `ejecutar_evidencia.py`.
- [ ] **Pendiente del usuario**: subir manualmente los 6 documentos (sano/comprometido × 3
      formatos) vía `http://localhost:3000/playground.html`, modo `complex-with-document`, para
      confirmar visualmente el comportamiento antes de dar la Fase 1 por cerrada y pasar a la
      Fase 2 (Defensa).

## Fase 2 — Defensa

### 2.1 Brainstorm de medidas candidatas

- [ ] Lluvia de ideas — como mínimo evaluar: sanitización del texto extraído (mismo pipeline que
      el Input Sanitizer del escenario base), detección de patrones ocultos estilo antivirus
      (heurísticas tipo "texto del mismo color que el fondo", "fuente <2pt", firmas conocidas),
      separación semántica explícita dato/instrucción en el prompt, límites/normalización de
      metadatos del PDF, conversión forzada a texto plano (elimina capas/color/tamaño antes de
      llegar al LLM).
- [ ] Documentar cada candidato en `02-defensa/README.md`: qué hace, por qué podría funcionar,
      coste de implementación, falsos positivos esperados.

### 2.2 Selección e implementación

- [ ] Elegir la(s) medida(s) a implementar, con justificación escrita.
- [ ] Implementar en el backend (extensión del Input Sanitizer u otro módulo nuevo).
- [ ] Escribir test(s) de regresión para la defensa.

### 2.3 Validación

- [ ] Repetir el ataque con el documento **comprometido** y la defensa activa → evidencia de
      bloqueo.
- [ ] Repetir con el documento **sano** y la defensa activa → confirmar que NO hay falso positivo.
- [ ] Capturar evidencia (mismo formato que en 1.3).

### 2.4 Capítulo de defensa

- [ ] Redactar el aporte a **4.1** (arquitectura general — cómo encaja este módulo) y a **6.1/6.2**
      (resultados después de la defensa, análisis y discusión).
- [ ] Actualizar el checklist de estado en `docs/ataques/.../README.md` (si se decide tocar el
      material de referencia en esta etapa — a confirmar con el resto del equipo).

## Fase 3 — Marco normativo

- [ ] Verificar contra fuentes oficiales (EUR-Lex) el borrador ya existente en
      `05-cumplimiento-normativo.md` (GDPR Art. 5.1.c/32/33/34, DORA Art. 9/10, AI Act Art. 9/15).
- [ ] Investigar si aplica EBA guidelines / PSD2 a este vector concreto.
- [ ] Ampliar NIST AI RMF (ya esbozado en `01-mapeo-taxonomico.md`) e investigar ISO 27001 si
      aplica.
- [ ] Estimar impacto/multas potenciales para el escenario VerdaBank (orden de magnitud,
      justificado).
- [ ] Redactar el aporte a la sección **7** del índice del TFM (Marco normativo y cumplimiento).

## Fase 4 — Consolidación

- [ ] Ensamblar el capítulo individual completo siguiendo el índice oficial del TFM.
- [ ] Revisar trazabilidad/reproducibilidad de principio a fin (cada afirmación con su evidencia
      y su comando de reproducción).
- [ ] Checklist final de entregable — nada pendiente sin marcar o justificado como trabajo futuro.
