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
      que la evidencia automatizada. Capturas de pantalla en
      `evidencia/screenshots/ataque-*.png` (6 imágenes, prefijo `ataque-` para distinguirlas de
      las de la Fase 2 — prefijo `defensa-`).

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

### 2.6 (D) Tool Gatekeeper — RBAC determinista ✅

- [x] Propuesto por el usuario: verificación de autorización **después** de que el LLM decide
      invocar una tool, ortogonal a (A)/(B)/(C) (que actúan antes, sobre el canal de entrada).
      Corresponde al módulo "Tool Gatekeeper" ya descrito en la propuesta formal del proyecto.
- [x] Implementado con `RunContext[Deps]` de PydanticAI: el `user_id` autenticado viaja por
      `deps` (canal que el LLM no controla), no por el prompt. Las 4 tools que operan sobre un
      recurso identificable (`consulta_saldo`, `transferencia_nacional`, `bloquear_tarjeta`,
      `abrir_reclamacion`) verifican propiedad contra `ctx.deps.user_id`.
- [x] Cerrado de paso un segundo vector de Confused Deputy: `abrir_reclamacion` aceptaba un
      `user_id` que el LLM podía rellenar libremente — ya no acepta ese parámetro.
- [x] Añadido `MOCK_CARDS` a `banking.py` (no existía tabla de tarjetas — necesaria para que la
      verificación de `bloquear_tarjeta` fuera real). Bug propio encontrado y corregido:
      mayúsculas/minúsculas inconsistentes entre el mock y la normalización.
- [x] 9 tests nuevos (`test_tool_gatekeeper.py`). Suite completa: **41/41**.
- [x] **Validación end-to-end real** vía `/chat/complex-with-context` (endpoint sin ninguna de
      las capas A/B/C, solo protege el canal documental): una inyección **directa** (no vía
      documento) engañó al LLM para que invocara `consulta_saldo` sobre la cuenta objetivo — el
      Tool Gatekeeper lo denegó en la propia tool. Control con la cuenta propia: permitido, sin
      falso positivo. Evidencia: `evidencia/session-files/tool-gatekeeper-validacion_20260727/`.
      **Mitiga también los ataques #2 (inyección directa) y #4 (Confused Deputy) del catálogo**,
      no solo el #7.

### 2.7 Selector de defensas por petición — estudio de ablación ✅

- [x] Propuesto por el usuario: parámetro para elegir qué combinación de las 4 capas (A/B/C/D)
      va activa en cada petición — todas, ninguna, o cualquier subconjunto — para poder medir el
      efecto aislado de cada una contra el mismo ataque.
- [x] 4 `Form()` booleanos nuevos en `/chat/complex-with-document` (`defensa_estructural`,
      `defensa_sanitizer`, `defensa_separacion_semantica`, `defensa_tool_gatekeeper`), todos
      `true` por defecto (seguro por defecto). `defensa_tool_gatekeeper` se propaga a las tools
      vía `Deps.enforce_gatekeeper`.
- [x] 6 tests nuevos (`test_ablacion_defensas.py`) cubriendo: las 4 off reproducen el
      comportamiento vulnerable de Fase 1; cada capa aislada basta (o no) según el caso de prueba
      diseñado específicamente para ella. Suite completa: **47/47**.
- [x] `ejecutar_evidencia.py --defensas <spec>` (`ABCD`/`none`/subconjunto) para automatizar la
      evidencia de cualquier combinación, sin sobreescribir los resultados ya consolidados.
- [x] Checkboxes de las 4 capas en el Playground (visibles solo en modo
      `complex-with-document`), para reproducir manualmente cualquier combinación.
- [x] **Ejecución real del estudio contra el LLM** (`none`, `A`, `B`, `C`, `D` — 3 repeticiones,
      6 casos cada una, 90 llamadas). Primera versión con un defecto de métrica: contaba como
      "éxito" la mera invocación de `consulta_saldo`, no si la tool devolvía el dato — válido
      para `none`/`A`/`B`/`C` (el mock no verificaba nada) pero incorrecto para `D`, donde la
      tool puede denegar la llamada. Corregido capturando el resultado real de la tool
      (`ToolReturnPart.content`, antes descartado) y exigiendo `"status": "ok"` para contar
      éxito; la tanda con el criterio incorrecto se descartó por completo y se repitió. Resultado
      final agregado (9 documentos comprometidos por combinación): `none`=8/9 (89%, baseline
      vulnerable), `A` sola=0/9, `B` sola=0/9 (ambas bastan solas para bloquear el 100% de los
      payloads reales), `C` sola=6/9 (67% — no bloquea, el LLM sigue obedeciendo la instrucción
      inyectada pese a la delimitación), `D` sola=**0/9** (el LLM sigue siendo engañado e invoca
      la tool, pero esta deniega el acceso en el 100% de los casos — 0% de éxito real), `ABCD`=0/9
      (ya documentado en Fase 2.3). 0 falsos positivos en sanos en las 6 combinaciones. Ver
      `02-defensa/README.md` §"Resultados del estudio de ablación" para el análisis completo y la
      nota metodológica sobre la corrección.
- [x] Etiqueta de bloqueo diferenciada por capa (`BLOCKED_BY_STRUCTURAL_DETECTOR` vs
      `BLOCKED_BY_SANITIZER`, antes ambas decían "SANITIZER") — necesario para que las pruebas
      manuales de (A) y (B) por separado sean legibles a simple vista en el Playground.
- [x] Documentado como limitación explícita del lab (no recomendación de producción): el `error`
      devuelto al cliente expone regla/capa/latencia — deliberado para verificación visual en el
      lab, pero sería un oráculo de evasión en un sistema real. Detalle en `02-defensa/README.md`
      §"Nota de diseño" y `CAPITULO.md` §4.1.
- [x] **Verificación manual capa por capa (gate del usuario)**: 33 turnos reales vía Playground —
      3 documentos comprometidos × 4 capas en solitario, y 3 documentos sanos con `ABCD` activo.
      (A)/(B) 100% consistentes (3/3 bloqueados cada una). (C) confirma manualmente su baja
      fiabilidad (8/9 fugas reales). **(D) documentado con sus fallos reales, no solo sus
      éxitos**: cuando la verificación de propiedad se ejecuta contra la cuenta correcta, deniega
      siempre — pero (1) no cubre al LLM alucinando un saldo falso cuando invoca una tool distinta
      o ninguna (3 ocurrencias, cifras inventadas sin relación con ningún dato real), y (2) genera
      falsos positivos en documentos sanos cuando el LLM transcribe mal el IBAN propio del usuario
      (2/7 intentos, ≈29%) — el Gatekeeper deniega correctamente por no-coincidencia exacta, pero
      el titular real es quien queda bloqueado. Ninguno de los dos fallos es un defecto del código
      del Gatekeeper; ambos son limitaciones estructurales de delegar en un LLM pequeño la
      construcción exacta del argumento de una tool call. Capturas renombradas (`-pdf`→`-docx`
      para los ficheros de reclamación, error de nomenclatura). Detalle completo en
      `02-defensa/README.md` §"Verificación manual del estudio de ablación".

### 2.8 Robustecer (D) antes de cerrar Fase 2 — a petición explícita del usuario ✅

El usuario pidió explícitamente no dar la Fase 2 por cerrada hasta abordar los fallos reales, no
solo documentarlos: *"no quiero cerrarla hasta que cada defensa no sea lo completamente robusta
como para evitar los 3 ataques"*. Dos arreglos concretos para (D):

- [x] **Cuenta/tarjeta propia por defecto** — `account_id`/`card_id`/`from_account` opcionales en
      `consulta_saldo`/`bloquear_tarjeta`/`transferencia_nacional`; si se omiten, se resuelven
      desde `ctx.deps.user_id` sin que el LLM tenga que transcribir el identificador. Cierra el
      falso positivo. 3 tests nuevos + **validación en vivo: 0/9 falsos positivos** (antes 2/7).
- [x] **Guardia de salida determinista** (`_confidential_leak_guard` en `chat.py`) — sustituye la
      respuesta si menciona un IBAN ajeno no respaldado por una tool call real de ese turno.
      Cierra la alucinación de saldos cuando el LLM invoca una tool equivocada o ninguna. 6 tests
      nuevos + **validación en vivo: 0/7 con IBAN ajeno visible** (antes 3 saldos inventados en la
      misma tanda de 7 intentos).
- [x] Suite completa del backend: **56/56**. Detalle en `02-defensa/README.md` §"Mejoras
      aplicadas tras la verificación manual", incluida la sección "Alcance — qué queda sin
      resolver" (ninguno de los dos arreglos es una garantía absoluta).
- [x] **Experimento de (C)**: framing del documento como resultado de una tool
      (`document_reader` sintético vía `message_history` de pydantic_ai) en vez de texto plano
      delimitado. **Mejora real y sustancial, no elimina el problema**: 22% (2/9) de éxito real
      aislado de (D), frente al 67-89% de la (C) actual — reducción de 3-4 veces. Con (D) también
      activo (condición realista): 0/9 fugas reales (4/9 denegadas por D, 5/9 el LLM ni lo
      intentó). Sigue siendo una técnica de prompt sin mecanismo de código que la haga cumplir —
      no llega a 0% ni se esperaba que lo hiciera. Evidencia completa en
      `henri-tfm/01-ataque/evidencia/experimento_c_tool_framing/`. Detalle en
      `02-defensa/README.md` §"Experimento (C)".
- [x] **Llevado a producción como variante seleccionable** (no reemplazo, decisión del usuario):
      nuevo parámetro `defensa_separacion_tool_framing` (default `False`, no cambia el
      comportamiento de (C) ya documentado) en `/chat/complex-with-document`, expuesto también en
      `ejecutar_evidencia.py --c-tool-framing` y como checkbox en el Playground. 3 tests nuevos +
      validación end-to-end contra el backend real. Suite completa: **59/59**.
- [x] **Verificación manual final (gate del usuario, 20 turnos reales)**: comparación directa de
      (C) con/sin tool_framing (2/3 fugas en esta muestra puntual — coherente con el 22% agregado,
      esperable con muestra pequeña); (C)+tool_framing sobre sanos, 0/3 falsos positivos (completa
      la matriz); (D) sobre comprometidos deniega y la guardia de salida actúa cuando el texto
      cita el IBAN (4/4); (D) sobre sanos, 0/3 falsos positivos tras el arreglo; `ABCD`+tool_framing
      completo, 6/6 correctos (comprometidos bloqueados antes de llegar al LLM, sanos limpios).
      Detalle en `02-defensa/README.md` §"Verificación manual final — cierre de Fase 2".

**Fase 2 (Defensa) cerrada por completo**: implementación de las 4 capas, validación
automatizada, estudio de ablación, verificación manual capa por capa (con sus fallos encontrados
Y arreglados, no solo documentados), y el experimento de (C) con resultado honesto (mejora, no
solución completa). Ninguna defensa se declaró "robusta" sin evidencia empírica que lo respalde.

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
