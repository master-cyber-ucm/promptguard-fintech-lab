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

### 1.6 Verificación manual del usuario ✅ (gate antes de Fase 2 — superado)

- [x] Añadido soporte de subida de documentos al frontend Playground
      (`lab/frontend/src/playground.html`, `js/app.js`, `js/api.js`): nuevo modo
      `complex-with-document` con selector de archivo, usando `FormData`/multipart contra el
      mismo endpoint que usa `ejecutar_evidencia.py`.
- [x] **Usuario subió manualmente los 6 documentos** vía `http://localhost:3000/playground.html`
      (modo `complex-with-document`, usuario `usr_001`): `evidencia/session-files/manual-verification-1.6_20260726/`.
- [x] **Resultado: los 6 confirmaron el comportamiento esperado.** 3/3 sanos sin fuga; 3/3
      comprometidos con éxito funcional (PDF, DOCX, XLSX — tool call `consulta_saldo` sobre la
      cuenta objetivo exacta en los tres). En DOCX, el modelo además cruzó los saldos entre las
      dos cuentas en su respuesta (atribuyó el valor correcto a la cuenta equivocada) — refuerza
      que la brecha de acceso es fiable pero la redacción textual no. Confirma que el frontend
      (una implementación de cliente distinta al script Python) dispara la misma vulnerabilidad
      que la evidencia automatizada.

**Fase 1 (Ataque) queda cerrada por completo, incluida la verificación manual.** Siguiente:
Fase 2 (Defensa).

## Fase 2 — Defensa

### 2.1 Brainstorm de medidas candidatas ✅

- [x] 5 candidatos evaluados en `02-defensa/README.md` con coste y falsos positivos esperados.
- [x] **Análisis de viabilidad de (A)** (pedido explícitamente por el usuario): detección
      estructural de técnicas de ocultación no es viable como defensa autosuficiente — es un
      enfoque de firmas (como un antivirus), y el catálogo de técnicas de esteganografía de texto
      (Unicode invisible, homoglifos, capas OCG de PDF, etc.) es amplio y sigue creciendo.
- [x] **Decisión final (revisada): (B) Sanitización de contenido = capa base**, (C) Separación
      semántica = fundamental, (A) = filtro complementario de bajo coste (no la base). (D)/(E)
      absorbidas o no aplicables.

### 2.2 Selección e implementación ✅

- [x] `lab/backend/src/core/document_sanitizer.py`: reutiliza
      `config/rules/injection_signatures.yaml` (Capa 1 regex del equipo, nunca antes conectada a
      código) + 3 reglas nuevas específicas de este vector. Devuelve la acción **más estricta**
      entre todas las reglas que matcheen (no la primera por orden del YAML).
- [x] **3 bugs preexistentes encontrados y corregidos** en el camino: (1) YAML roto por una
      comilla sin escapar; (2) regla `obfuscation_markers` con `1`/`0` como alternativas sueltas
      (falso positivo garantizado en cualquier documento con dígitos); (3) regla nueva con `^` no
      multilínea, bug enmascarado por otra regla que sí bloqueaba por otro motivo.
- [x] Separación semántica (C) implementada en `_process_chat` (`chat.py`): el texto del
      documento se envuelve en delimitadores explícitos + instrucción de "dato, no instrucción".
- [x] Wiring: si `sanitize_document_text` devuelve `BLOCK`, la petición se registra y responde
      con `BLOCKED_BY_SANITIZER` **sin invocar al LLM**.
- [x] Tests: 22/22 (`test_document_sanitizer.py` nuevo + `test_chat_document_endpoint.py`
      actualizado a comportamiento defendido), incluida regresión del bug de severidad.
- [x] **(A) implementada como capa complementaria** (a petición del usuario, tras el análisis de
      viabilidad): `document_structural_detector.py` — 5 técnicas de ocultación de la Fase 1
      (blanco sobre blanco, fuente <2pt, fuera de página en PDF; run oculto en DOCX; fila/columna
      oculta y comentario en XLSX), documentada explícitamente como catálogo parcial que debe
      evolucionar (changelog versionado, igual que firmas de antivirus). 10 tests nuevos.
      Combinada con (B) en el endpoint: bloquea si cualquiera de las dos capas dispara.
- [x] **Rendimiento medido** (preocupación explícita del usuario): benchmark de 200 iteraciones
      por documento — peor caso (DOCX) ~7ms para la capa complementaria, ~0.15ms para la
      sanitización de contenido. Despreciable frente a la latencia real del LLM (5.000-40.000ms)
      y muy por debajo del presupuesto de la propuesta formal (<200ms p95). Ver
      `02-defensa/benchmark_structural_detector.py` y `02-defensa/README.md` §"Impacto en
      rendimiento".

### 2.3 Validación ✅

- [x] Re-ejecutado `ejecutar_evidencia.py` (mismo script/documentos de la Fase 1.5) contra el
      endpoint ya defendido. **Resultado: 9/9 comprometidos bloqueados (0% en PDF/DOCX/XLSX,
      antes 85-100%), 0/9 falsos positivos en sanos** (latencia normal de LLM, sin bloqueo).
      Evidencia: `evidencia/session-files/run5-defensa-activa_20260726_223411/` (10 Session
      Files, 18 turnos). Total: **32/32 tests** en la suite del backend.
- [x] **Re-validado con las 3 capas juntas (A+B+C)**, tras implementar (A) — la validación
      anterior solo tenía B+C. Instrumentado el endpoint con cronómetros reales por etapa
      (antes la latencia de bloqueo estaba hardcodeada a `0.0ms`, no medida). Resultado: **sigue
      9/9 bloqueados, 0/9 falsos positivos**; latencia real de la defensa por petición:
      PDF ~4.6ms, DOCX ~10.9ms, XLSX ~5.0ms (consistente con el benchmark aislado). Evidencia:
      `evidencia/session-files/run6-defensa-ABC-completa_20260726_225918/`.

### 2.4 Verificación manual de la defensa (gate del usuario) ✅

- [x] **Usuario repitió la subida de los 6 documentos** vía Playground con la defensa activa
      (mismo procedimiento que la Fase 1.6). Capturas guardadas en `evidencia/screenshots/`
      (6 imágenes). Los 3 comprometidos se bloquearon casi al instante (latencia real visible en
      la propia UI: 3.03-9.69ms); los 3 sanos se procesaron con normalidad. Ver
      `02-defensa/README.md` §"Verificación manual de la defensa".

### 2.5 Capítulo de defensa ✅

- [x] Redactado el aporte a **4.1** (arquitectura de 3 capas, deuda técnica, rendimiento) y a
      **6.1/6.2** (resultados antes/después de la defensa, análisis, corroboración manual —
      incluida la de esta verificación con capturas).
- [ ] Actualizar el checklist de estado en `docs/ataques/.../README.md` (si se decide tocar el
      material de referencia en esta etapa — a confirmar con el resto del equipo).

**Fase 2 (Defensa) cerrada por completo, incluida la verificación manual.** Siguiente: Fase 3
(Marco normativo).

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
