# Defensa — Amplificación vía Documentos Adjuntos

> Diseño de control: puede incluir propuestas y estados históricos. El [alcance de la entrega](../../alcance-y-limitaciones.md) delimita lo implementado; la eficacia se comprueba con las evidencias de cada ejecución.

> Contra el ataque **#11** del catálogo · [ficha del ataque](../../ataques/LLM10-unbounded-consumption/amplificacion-documentos-adjuntos)
> **Sin *technique ID* de MITRE ATLAS** (honestidad metodológica — ver ficha del ataque) · **CWE-409** (decompression bomb)
> **Módulo principal:** Document Size Guard · **Posición:** antes de `document_extractor.py`, antes incluso del `document_sanitizer` del ataque #7

## 1. Qué hay que impedir

Que un fichero adjunto agote CPU o memoria del proceso backend **durante la
extracción**, antes de que exista texto sobre el que aplicar ninguna defensa de
contenido (`document_sanitizer`, `document_structural_detector` — ambas actúan sobre
texto ya extraído). Es el único control de este catálogo LLM10 que se sitúa antes del
propio parser, no antes del modelo.

| Invariante | Cómo se garantiza |
|-----------|-------------------|
| **I1** — Ningún fichero adjunto supera un tamaño máximo declarado | Chequeo de `Content-Length`/tamaño real antes de leer el body completo en memoria |
| **I2** — Ningún fichero se descomprime más allá de un ratio máximo | Límite de ratio de compresión (tamaño descomprimido / tamaño comprimido) para DOCX/XLSX |
| **I3** — La extracción tiene un techo de tiempo y de unidades procesadas | Timeout duro + límite de páginas (PDF) / filas (XLSX) |

## 2. Principio de diseño

> El coste de rechazar un fichero tiene que pagarse ANTES de descomprimirlo o
> parsearlo, no después.

Mismo principio que el Rate Limiter de `denegacion-de-servicio.md` (rechazar barato,
antes de gastar el recurso caro) aplicado a ficheros: comprobar el tamaño declarado del
upload y un muestreo del ratio de compresión del ZIP contenedor (DOCX/XLSX) **antes**
de invocar `python-docx`/`openpyxl`/`pypdf` sobre el contenido completo.

## 3. Diseño del control

- **Límite de tamaño de subida** — rechazo en el propio endpoint FastAPI
  (`api/routes/chat.py::chat_complex_with_document`) antes de `document.read()`
  completo — hoy se lee sin comprobar nada.
- **Límite de ratio de descompresión** — para DOCX/XLSX (ZIP), inspeccionar los tamaños
  declarados en el central directory del ZIP antes de descomprimir cada entrada;
  rechazar si el ratio supera un umbral (valores de referencia habituales en la
  industria: 100:1 a 1000:1 según el caso de uso).
- **Cota de páginas/filas** — `_extract_pdf()` y `_extract_xlsx()` necesitan un límite
  explícito de páginas/filas procesadas, con corte y aviso en vez de silencio (un
  documento legítimo de VerdaBank — nómina, extracto — no se acerca a esas cotas).
- **Timeout + aislamiento de recursos del propio proceso de extracción** — ejecutar
  `extract_text()` con un timeout duro y, si el coste de implementarlo lo justifica, en
  un subproceso con límites de memoria propios (`resource.setrlimit` o un sandbox), de
  forma que un fallo de esta capa no tumbe el proceso principal del backend.

## 4. Qué NO cubre

- **PDFs con vulnerabilidades específicas de la librería** (CVEs de `pypdf` con
  payloads que no son "grandes" sino que explotan un bug de parsing) — un Document Size
  Guard no sustituye mantener las dependencias actualizadas; son controles
  complementarios, no intercambiables.
- **No interactúa con el ataque #7** (indirecta vía documento) — deliberado. Este
  control decide si el fichero se procesa en absoluto; `document_sanitizer` decide si
  el TEXTO ya extraído es seguro. Cortar antes no debe implicar saltarse la
  sanitización cuando el fichero sí pasa el Size Guard.

## 5. Estado

- [x] Invariantes definidos
- [x] Diseño de los cuatro controles (tamaño, ratio de compresión, cota de
  páginas/filas, timeout/aislamiento)
- [ ] Implementación — nada de esto existe en `lab/backend/src/` todavía
- [ ] Valores de umbral concretos (tamaño máximo, ratio máximo, nº de páginas/filas) —
  sin decidir, requieren calibrarse contra los documentos legítimos reales del lab
  (`lab/payloads/`) para no romper el flujo del ataque #7
- [ ] Fixtures de prueba (zip bomb / PDF patológico) — no existen, generarlas con
  cuidado en un entorno aislado
