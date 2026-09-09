# El documento es una capacidad opcional de los endpoints existentes

Estado: **aceptado** (backend); **frontend/Playground diferidos** (ver Consequences).

## Contexto

Solo `/chat/complex-with-document` aceptaba `multipart/form-data`; el resto de
endpoints (`simple-prompt`, `complex-prompt`, `complex-with-context`, `proxy`) solo
aceptaban JSON. Esto convertía "usar un documento" en "elegir otro endpoint", con su
propio agente (`complex`), su propia inyección de contexto (siempre `True`) y su
propio conjunto de flags de ablación — imposible de comparar limpiamente contra
`proxy` sin documento, o contra `simple-prompt` con documento. Ver
[PR 7](../historial-desarrollo.md).

`_process_chat` (el orquestador compartido por los cinco endpoints) YA aceptaba un
parámetro `document_text: Optional[str]` y ya sabía componerlo de tres formas
(raw/ablación, delimitado con separación semántica, o vía tool sintética
`document_reader`) según los flags de defensa — sin usarlo nunca desde los cuatro
endpoints JSON. La pieza que faltaba no era el orquestador: era (a) una capa de
entrada que aceptase multipart en la misma ruta que JSON, y (b) decidir qué
defensas documentales aplican en cada postura.

## Decisión

1. **Capa de entrada única.** `_parse_chat_request(http_request: Request)` normaliza
   `application/json` y `multipart/form-data` al mismo `ChatRequest` antes de invocar
   el comportamiento del endpoint. Los cuatro endpoints cambian su firma de
   `request: ChatRequest` (bind automático de FastAPI) a `http_request: Request`
   (bind manual) — coste: se pierde la validación/documentación automática de
   OpenAPI para el cuerpo JSON en `/docs`; se acepta porque FastAPI no soporta de
   forma nativa "JSON o multipart en la misma ruta" con dos modelos de Pydantic.
2. **Baseline sin ninguna defensa documental.** `simple-prompt`/`complex-prompt`/
   `complex-with-context` llaman `_document_text_baseline()`: extracción acotada
   (`document_extractor.py`, ya "modo vulnerable" por diseño desde el ataque #7) sin
   `document_sanitizer` ni `document_structural_detector`, y `defensa_separacion_
   semantica=False` explícito. Es la ausencia deliberada que el informe exige que
   sea observable — mismo criterio que `_SIN_CONTROLES_EXTERNOS` ya aplicaba a los
   controles de prompt de estos tres endpoints.
3. **`proxy` con pipeline protegido reutilizado, no duplicado.** `_document_text_protected()`
   es la extracción de `chat_complex_with_document` factorizada en una función
   compartida: mismos componentes (`document_sanitizer`, `document_structural_detector`),
   mismas métricas por fase. Un bloqueo lanza `DocumentBlocked`, que el llamador
   convierte en respuesta con `_document_blocked_response()` — código compartido, no
   una segunda copia del `if decision.action == "BLOCK": ...` de 60 líneas.
   Las defensas documentales se gatean con `not request.vulnerable`, el mismo
   interruptor que ya apaga Input Sanitizer/PII Shield/Output Auditor — sin excepción
   oculta para el documento.
4. **`/complex-with-document` queda como adaptador fino, no se retira.** Llama a los
   mismos `_document_text_protected()`/`_document_blocked_response()` que `proxy`
   (deduplicado), pero conserva su firma `Form(...)` exacta y sus seis flags `defensa_*`
   individuales, con los mismos defaults. Motivo: `ejecutar_evidencia.py --defensas
   <combinación>` (henri-tfm/02-defensa/) depende de poder desactivar cada capa por
   separado, y esta PR no puede verificar "cero consumidores" del endpoint dentro de
   su ventana de trabajo — mapear silenciosamente su tráfico a `proxy` con perfiles
   fijos habría sido el "cambio incompatible silencioso" que el informe prohíbe
   explícitamente. Se marca deprecado (docstring + `logger.warning` en cada llamada)
   apuntando a `proxy`; la retirada queda pendiente de que se confirme cero uso.
5. **Límites técnicos mínimos, no la lista exhaustiva.** `MAX_DOCUMENT_BYTES`
   (10 MiB por defecto, configurable), comprobación de firma binaria por formato
   (`%PDF`, `PK\x03\x04` para DOCX/XLSX) y captura genérica de excepciones del parser
   como `EXTRACTION_FAILED` — antes no había NINGÚN límite. Páginas/hojas/celdas,
   ratio de expansión, timeout y memoria por petición quedan fuera de esta PR (ver
   Consequences): requieren decidir valores según capacidad operativa real, que el
   informe marca explícitamente como una decisión pendiente, no una omisión.

## Considered Options

- **Endpoint documental por endpoint (`/proxy-with-document`, etc.)**: descartada
  explícitamente por el informe (No objetivo #1) — multiplica superficies en vez de
  unificar el contrato.
- **Redirigir `/complex-with-document` a `proxy` con un perfil fijo**: cambia el
  pipeline observable (proxy corre Input Sanitizer sobre el prompt; `complex-with-
  document` nunca lo hizo) y rompe los flags de ablación por capa que
  `ejecutar_evidencia.py` necesita — descartada por el mismo motivo que el informe
  cita para prohibir un "cambio incompatible silencioso".
- **Adaptador fino que reutiliza los componentes compartidos de `proxy` sin cambiar
  su contrato observable** (elegida): conserva compatibilidad exacta con el
  consumidor conocido, elimina la duplicación de lógica documental, dejo trazabilidad
  de deprecación para decidir la retirada con evidencia de uso real.
- **Aceptar `application/x-www-form-urlencoded` como tercera representación**:
  descartada — el informe solo pide JSON (sin documento) y multipart (con
  documento); añadir una tercera forma no aporta valor y complica la capa de
  entrada sin necesidad.

## Consequences

- `ChatResponse.document` (nuevo campo opcional, `None` sin documento) expone
  extensión, tamaño, hash de contenido truncado y pipeline efectivo
  (`baseline`/`protected`) — compatible hacia atrás: ningún cliente que no lo lea se
  ve afectado.
- El mismo archivo (mismo `content_hash`) enviado a dos endpoints permite demostrar
  qué se mantuvo fijo y qué cambió — precondición de la "equivalencia para medición"
  del informe; la comparabilidad CAUSAL completa (PR5) requiere además fijar prompt,
  modelo, contexto y herramientas, que esta PR no toca.
- **Frontend bancario y Playground: diferidos.** Este PR entrega el contrato backend
  completo, validado con tests y en vivo contra el modelo real. La superficie de UI
  (selector de archivo, estados de carga/retirada, accesibilidad, actualizar la capa
  de API del Playground para elegir JSON/multipart) es trabajo de otra naturaleza
  (frontend vanilla JS, sin test runner en este repo) que no se pudo completar con
  el mismo nivel de rigor dentro de esta sesión. El contrato backend ya soporta todo
  lo que el frontend necesitará — no hay trabajo de backend bloqueante pendiente.
- **Límites técnicos exhaustivos (páginas/hojas/celdas/ratio de expansión/timeout/
  memoria) y streaming real de lectura**: quedan fuera de esta PR. El informe mismo
  los lista como "riesgos y decisiones pendientes" que requieren fijarse contra
  capacidad operativa real, no un valor arbitrario elegido sin esa evidencia.
- Fixtures documentales del catálogo (11 huérfanos identificados en PR4): siguen
  apuntando a `complex-with-document`; migrarlos a los endpoints canónicos con
  documento es trabajo de catálogo (`backend/tests/fixtures/`), no de este PR de
  código de plataforma — anotado como seguimiento.
