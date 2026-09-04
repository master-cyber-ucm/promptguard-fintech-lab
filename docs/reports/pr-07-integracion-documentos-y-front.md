# PR 7 — Integrar documentos en los endpoints existentes y actualizar los frontends

**Estado:** propuesta técnica para revisión  
**Prioridad:** P1 — unifica el contrato documental y elimina una superficie especial  
**Dependencias:** coordinar aplicabilidad con PR 4, comparabilidad con PR 5 e instrumentación con PR 6  
**Ámbito:** backend de chat, frontend bancario, Playground, pruebas y documentación de contrato

## Resumen ejecutivo

El backend expone hoy `simple-prompt`, `complex-prompt`, `complex-with-context`, `proxy` y `complex-with-document`. Solo el último acepta `multipart/form-data`; el frontend bancario no permite adjuntos y el Playground los limita a ese modo especial. Esta separación hace que «usar un documento» se confunda con elegir otro endpoint y dificulta comparar el mismo agente con y sin procesamiento defensivo.

Esta PR convierte el documento en una capacidad opcional de los endpoints existentes. Sin documento, cada endpoint conserva su contrato y comportamiento actuales. Con documento, los endpoints baseline incorporan su contenido a la petición del modelo sin defensas documentales específicas; `proxy` lo somete primero al pipeline documental defensivo y solo incorpora contenido controlado. En ambos casos se mantienen controles técnicos mínimos de tipo, tamaño y consumo.

No se crea un endpoint documental particular. `/complex-with-document` deja de ser el destino conceptual. Si se conserva durante la migración, será únicamente un adaptador de compatibilidad deprecado, sin lógica propia, con telemetría y fecha/criterio de retirada.

## Objetivo

1. Permitir un documento opcional en `simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy`.
2. Conservar el comportamiento actual cuando no se adjunta documento.
3. Hacer explícita la diferencia entre incorporación baseline y procesamiento protegido de `proxy`.
4. Actualizar el frontend bancario y el Playground para adjuntar archivos al endpoint seleccionado.
5. Retirar la dependencia funcional y experimental de `/complex-with-document`.
6. Producir trazas, métricas y pruebas por endpoint, modalidad y pipeline efectivo.

## No objetivos

- Crear `/proxy-with-document`, otro endpoint documental o una nueva familia de rutas.
- Aplicar las defensas documentales de `proxy` a los endpoints baseline.
- Cambiar prompts, modelo, configuración, contexto confiable, herramientas o policy no documental por el mero hecho de cambiar el transporte.
- Rediseñar el agente, el dominio bancario o la autorización financiera de PR 2.
- Lanzar la campaña experimental de PR 5 ni recalcular por sí sola los resultados históricos.
- Aumentar tipos o cantidades de archivo sin límites explícitos.

## Estado actual y estado objetivo

| Superficie | Estado actual | Estado objetivo |
|---|---|---|
| `POST /api/v1/chat/simple-prompt` | JSON, sin documento | mensaje con documento opcional; pipeline baseline |
| `POST /api/v1/chat/complex-prompt` | JSON, sin documento | mensaje con documento opcional; pipeline baseline |
| `POST /api/v1/chat/complex-with-context` | JSON, sin documento | mensaje con documento opcional; pipeline baseline |
| `POST /api/v1/chat/proxy` | JSON, sin documento | mensaje con documento opcional; pipeline protegido |
| `POST /api/v1/chat/complex-with-document` | multipart y lógica documental propia | adaptador deprecado temporal o retirada; nunca destino conceptual |
| Frontend bancario | chat JSON a `proxy`, sin selector | adjunto opcional enviado a `proxy` |
| Playground | adjunto solo en modo `complex-with-document` | adjunto opcional en cada endpoint existente |

## Contrato funcional

### Una operación lógica, dos representaciones de transporte

Cada endpoint admite los mismos campos lógicos que hoy y un campo opcional `document`:

- sin documento, el cliente puede continuar enviando `application/json` sin cambios;
- con documento, el cliente envía `multipart/form-data` al mismo endpoint seleccionado;
- los campos escalares del multipart conservan nombre, tipo, obligatoriedad y semántica respecto del contrato JSON;
- `document` admite como máximo un archivo en esta PR;
- un `session_id` ausente se omite; nunca se serializa el texto `"null"`;
- la respuesta conserva el esquema público del endpoint y puede añadir metadatos documentales no sensibles y compatibles hacia atrás.

La capa de entrada normaliza JSON y multipart a una única petición interna tipada antes de invocar el comportamiento del endpoint. La selección de `Content-Type` no crea una ruta lógica distinta ni altera por sí sola prompt, configuración o defensas.

### Semántica del documento

«Sin análisis documental» en baseline significa sin sanitización, detección de inyección, separación semántica, tool framing ni otras defensas específicas. No significa entregar bytes opacos al modelo ni omitir controles técnicos: el contenido debe extraerse de forma acotada y representarse de manera determinista para incorporarlo al mensaje/contexto.

La composición identifica con claridad el mensaje del usuario y el contenido extraído. Prompt de sistema, historial, contexto confiable y documento no se concatenan de forma ambigua. El documento es siempre contenido no confiable y no aporta por sí solo autorización, identidad ni parámetros aprobados para una escritura.

### Equivalencia para medición

Cuando el objetivo sea medir transporte, procesamiento o defensas, se fijan el archivo y su hash, mensaje, prompt, modelo, parámetros, contexto confiable, herramientas, policy no defensiva, budgets y código. Se registran por separado:

- endpoint y transporte;
- versión/huella del extractor y representación;
- huella del pipeline documental;
- vector de defensas;
- diferencias deliberadas del tratamiento.

La comparabilidad causal se decide conforme a PR 5; aceptar el mismo documento en dos endpoints no basta para declararlos equivalentes.

## Matriz de comportamiento por endpoint

| Endpoint | Documento opcional | Extracción acotada | Defensas documentales | Incorporación al modelo | Postura |
|---|---:|---:|---:|---|---|
| `simple-prompt` | sí | sí | no | contenido extraído sin saneamiento defensivo, separado del mensaje | baseline mínimo |
| `complex-prompt` | sí | sí | no | contenido extraído sin saneamiento defensivo dentro de la composición compleja | baseline complejo |
| `complex-with-context` | sí | sí | no | contenido extraído sin saneamiento defensivo, distinto del contexto confiable | baseline con contexto |
| `proxy` | sí | sí | sí | solo contenido resultante/controlado tras el pipeline del proxy | protegido |

La ausencia de defensas documentales en baseline es deliberada, observable y probada. Los límites técnicos comunes no cuentan como defensa experimental desactivable.

## Comportamiento baseline

Para `simple-prompt`, `complex-prompt` y `complex-with-context`:

1. validar metadatos, tipo, tamaño y presupuesto;
2. extraer el contenido mediante el componente compartido y acotado;
3. construir una representación determinista con nombre/tipo y delimitadores inequívocos;
4. incorporarla en la ubicación correspondiente del mensaje/contexto del endpoint;
5. no ejecutar sanitizer, detector estructural, separación semántica, tool framing ni defensas documentales del proxy;
6. registrar que el pipeline efectivo es baseline y qué controles técnicos se aplicaron.

En `complex-with-context`, el documento no se promueve a contexto confiable. En todos los baseline, instrucciones o valores procedentes del archivo siguen sin constituir autorización de dominio.

## Comportamiento de `proxy`

Para `proxy` con documento:

1. aplicar los controles técnicos comunes y extraer de forma acotada;
2. ejecutar sanitización y detección estructural sobre el contenido documental;
3. aplicar separación semántica y tool framing para impedir que el documento suplante instrucciones, contexto confiable o resultados de tools;
4. ejecutar las defensas del proxy que correspondan al perfil efectivo, incluido Gatekeeper/PII cuando aplique;
5. producir una representación controlada o un rechazo estructurado con reason code;
6. incorporar al modelo únicamente esa representación controlada;
7. preservar trazabilidad entre hash de entrada, etapas, decisiones y contenido derivado sin registrar datos sensibles innecesarios.

No se deriva la petición a `/complex-with-document` ni se duplica el pipeline. La lógica documental protegida vive en componentes reutilizables invocados por `proxy`.

## Cambios backend

1. Extender las cuatro rutas existentes para aceptar JSON sin archivo y multipart con `document` opcional.
2. Normalizar ambas representaciones al mismo modelo interno de petición.
3. Separar responsabilidades reutilizables: validación técnica, extracción acotada, representación baseline, pipeline protegido y composición final.
4. Conectar baseline y `proxy` según la matriz, sin condicionales implícitos basados solo en el nombre de la ruta.
5. Eliminar lógica documental exclusiva de `/complex-with-document`; el adaptador, si existe, llama al camino canónico acordado y emite aviso de deprecación.
6. Añadir metadatos auditables: modalidad, hash, tipo/tamaño, resultado de extracción, pipeline fingerprint, defensas efectivas, tiempos y consumo por fase.
7. Normalizar errores públicos de archivo y extracción sin filtrar contenido, rutas internas ni detalles del parser.

La elección exacta de adaptador para `/complex-with-document` debe documentarse: dado que su comportamiento histórico no equivale necesariamente a `proxy`, no se redirige silenciosamente a una semántica distinta. Debe mapearse al endpoint canónico que preserve su contrato observable o retirarse como cambio incompatible anunciado.

## Cambios en el frontend bancario

- Añadir selector de archivo accesible al chat completo y al widget si ambos siguen siendo superficies soportadas.
- Mostrar nombre, estado, opción de retirar y errores previos al envío.
- Mantener el envío JSON actual cuando no haya adjunto.
- Con adjunto, construir multipart y enviarlo a `proxy`, que continúa siendo el endpoint seleccionado por el banco.
- Omitir `session_id` en el primer turno y conservar la sesión devuelta para los siguientes.
- Deshabilitar reenvíos accidentales mientras la petición está activa y limpiar el adjunto solo tras éxito o acción explícita del usuario.
- Mostrar rechazos por tipo, tamaño, extracción o defensa con mensajes accionables y sin exponer detalles sensibles.

## Cambios en el Playground

- El selector de endpoint conserva únicamente los endpoints existentes de la matriz; `complex-with-document` desaparece como modo normal.
- El control de adjunto está disponible de forma opcional en `simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy`.
- La capa de API elige JSON o multipart para el mismo endpoint según exista archivo.
- La UI muestra la postura efectiva: baseline sin defensas documentales o `proxy` con el vector de defensas seleccionado.
- Los controles defensivos documentales solo son configurables donde el contrato los admite; no deben sugerir que baseline los ejecuta.
- El estado del archivo no queda oculto y activo al cambiar de endpoint: se conserva de forma visible o se solicita retirarlo explícitamente.
- Se alinean los campos disponibles con backend, incluido PII si forma parte del perfil expuesto.

## Compatibilidad, deprecación y retirada

### Clientes sin documentos

Las peticiones JSON existentes y sus respuestas siguen funcionando sin cambios semánticos. Este camino tiene pruebas de regresión por endpoint.

### Clientes de `/complex-with-document`

Si existen consumidores que impidan retirarlo en el mismo merge:

1. marcar la ruta como deprecada en documentación y respuesta/cabeceras apropiadas;
2. implementar un adaptador fino sin extractor, defensas ni composición propios;
3. publicar el endpoint canónico de sustitución y ejemplo de migración;
4. medir llamadas restantes por cliente/versionado sin registrar contenido;
5. fijar criterio de retirada: cero consumidores conocidos y al menos una ventana de versión anunciada;
6. eliminar adaptador y pruebas legacy en una PR posterior identificada.

No se añaden funcionalidades al adaptador. Las métricas nuevas se atribuyen al endpoint canónico y etiquetan el uso legacy; `/complex-with-document` no aparece como destino futuro en UI, fixtures ni diseño experimental.

## Validaciones de seguridad y consumo mínimas

Aplican a todos los endpoints, también baseline, y no pueden desactivarse como ablación:

- lista permitida explícita de formatos inicialmente alineada con PDF, DOCX y XLSX;
- coherencia entre extensión, tipo declarado y firma/contenido detectado; rechazo al fallar;
- tamaño máximo configurable y probado antes de leer el archivo completo;
- lectura en streaming o con límite duro, sin buffers ilimitados;
- límites de páginas, hojas, celdas, texto extraído, ratio de expansión, tiempo y memoria;
- rechazo seguro de archivos cifrados, corruptos, contenedores recursivos o contenido no soportado;
- nombres normalizados sin uso como ruta y parsers aislados de efectos externos;
- un archivo por petición, salvo futura decisión explícita;
- errores deterministas y reason codes; no incluir contenido documental en logs por defecto;
- cancelación y cleanup de temporales en éxito, rechazo, timeout y desconexión.

Los valores concretos se centralizan en configuración versionada, se exponen en el contrato del cliente cuando sea necesario y quedan fijados en la evidencia de cada run.

## Pruebas requeridas

### Contrato y regresión

- JSON sin documento en los cuatro endpoints: misma semántica y esquema de respuesta que antes.
- Multipart sin `document`: comportamiento definido y equivalente o rechazo contractual explícito.
- Multipart con documento válido por formato en cada endpoint.
- Campos opcionales, booleanos y sesión normalizados igual en JSON/multipart; `session_id="null"` nunca se genera.
- Error público estable para tipo, tamaño y extracción.

### Diferencia baseline/proxy

- Archivo con instrucciones adversarias: los tres baseline lo incorporan sin activar defensas documentales y dejan evidencia de postura baseline.
- El mismo archivo en `proxy` recorre las etapas defensivas y solo el contenido controlado llega a composición.
- Contexto confiable, documento, prompt y tool framing permanecen separados.
- Hashes/fingerprints permiten demostrar qué se mantuvo fijo y qué tratamiento cambió.

### Límites técnicos

- Extensión/MIME/firma discordantes, archivo corrupto, cifrado y formato no permitido.
- Byte exacto en límite y por encima; expansión, páginas/hojas/celdas, timeout y memoria.
- Cancelación, cleanup, concurrencia y ausencia de lectura ilimitada.
- Documento no aporta autorización ni parámetros aprobados para una escritura financiera.

### Frontends y compatibilidad

- Banco: enviar sin/con adjunto desde cada superficie soportada, retirar, reintentar y continuar sesión.
- Playground: matriz completa de endpoint × sin/con documento y controles visibles correctos.
- Pruebas accesibles de teclado, foco, estado y mensajes de error.
- Adaptador legacy: equivalencia observable, aviso de deprecación, telemetría y ausencia de lógica duplicada.

## Métricas y cobertura

PR 4 actualiza aplicabilidad y denominadores por endpoint existente. Para cada ejecución documental se registra al menos:

- endpoint, postura, modalidad y transporte;
- formato, tamaño y hash no reversible del archivo;
- resultado y reason code de validación/extracción;
- pipeline fingerprint y defensas efectivas;
- éxito funcional, contención/FP cuando aplique y conclusividad;
- latencia y consumo por fase;
- uso del adaptador legacy.

Los once fixtures documentales antes huérfanos deben adquirir una decisión de aplicabilidad por endpoint/postura. Ningún agregado mezcla baseline y `proxy` sin etiquetar su diferente pipeline. PR 5 gobierna los claims causales y PR 6 las métricas de utilidad, resiliencia y rendimiento.

## Despliegue propuesto

1. Introducir normalización, límites y pruebas de JSON sin alterar comportamiento.
2. Habilitar multipart opcional en los endpoints existentes detrás de una capacidad versionada.
3. Conectar baseline y `proxy` a sus pipelines correspondientes y activar observabilidad.
4. Actualizar Playground y frontend bancario.
5. Marcar `/complex-with-document` como deprecado/adaptador y migrar fixtures/clientes.
6. Verificar cero consumidores y retirar en la ventana anunciada.

Cada fase conserva rollback del cliente sin reintroducir lógica documental duplicada.

## Criterios de aceptación

- `simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy` aceptan documento opcional en su propia ruta.
- Sin documento, los cuatro endpoints conservan el comportamiento JSON previo.
- Los tres baseline incorporan contenido extraído sin defensas documentales específicas y con controles técnicos mínimos.
- `proxy` aplica extracción, sanitización, detección estructural, separación semántica/tool framing y defensas efectivas antes de incorporar contenido controlado.
- Prompt, configuración, modelo, contexto confiable y herramientas permanecen equivalentes cuando el plan declara que mide transporte/procesamiento/defensas.
- Banco y Playground pueden adjuntar, retirar y enviar documentos al endpoint seleccionado; el Playground ya no depende del modo `complex-with-document`.
- No se crea ningún endpoint documental particular.
- `/complex-with-document` se elimina o queda como adaptador deprecado sin lógica propia, sustitución documentada, telemetría y criterio de retirada.
- Tipo, firma, tamaño, expansión, tiempo y consumo tienen límites fail-closed y pruebas de borde.
- Cobertura, utilidad, resiliencia y rendimiento documentales se informan por endpoint/postura con denominadores explícitos.
- No se modifica la semántica de autorización: contenido documental no autoriza escrituras.

## Riesgos y decisiones pendientes

- La representación exacta del contenido extraído debe ser común y versionada, pero baseline y `proxy` no pueden compartir por accidente una salida ya saneada.
- La semántica histórica de `/complex-with-document` debe compararse con los endpoints canónicos antes de elegir adaptador; una redirección que cambie defensas sería incompatible.
- Los límites numéricos requieren fijarse según capacidad operativa y fixtures reales antes de implementar, sin dejar valores ilimitados por defecto.
- Aceptar multipart y JSON en una misma ruta exige documentación y clientes generados que representen ambas variantes con claridad.

Estas decisiones se resuelven dentro de la implementación de esta PR y se reflejan en pruebas/configuración; no justifican mantener una arquitectura documental separada.
