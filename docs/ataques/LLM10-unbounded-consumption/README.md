# LLM10:2025 — Unbounded Consumption

> **OWASP LLM Top 10 (2025) — LLM10:2025**
> Categoría del catálogo. Agrupa **4 ataques** — primera sesión de investigación,
> sin fixtures ni implementación todavía. Ver `TODOs.md` § "Ataques a la
> infraestructura" para el estado de avance.

## Definición

> "Unbounded Consumption occurs when a Large Language Model (LLM) application allows
> users to conduct excessive and uncontrolled inferences, leading to risks such as
> denial of service (DoS), economic losses, model theft, and service degradation."

Fuente: [OWASP GenAI Security Project — LLM10:2025 Unbounded Consumption](https://genai.owasp.org/llmrisk/llm102025-unbounded-consumption/).

Es la categoría que rompe con el resto del catálogo del proyecto: LLM01, LLM02, LLM06 y
LLM07 atacan la **inteligencia** del sistema — convencen al modelo de hacer algo que no
debería. LLM10 ataca su **infraestructura** — el modelo hace exactamente lo que se le
pide, pero el volumen, el tamaño o la repetición de las peticiones agota recursos
(cómputo, memoria, presupuesto) hasta degradar o tumbar el servicio. Ningún payload de
esta categoría necesita "engañar" a Clara.

## Por qué es relevante en VerdaBank

El lab no tiene, hoy, ningún control de consumo — verificado contra el código, no
asumido:

- **Sin límite de tokens de salida.** Ninguna llamada al proveedor LLM
  (`lab/backend/src/agents/clara_*.py` vía pydantic-ai) fija `max_tokens`/`num_predict`.
  Un prompt que induzca una generación larga no tiene techo.
- **Sin rate limiting.** `lab/backend/src/main.py` no monta ningún middleware de límite
  de peticiones por IP/usuario — se puede llamar a `/chat/proxy` tan rápido como
  responda el proveedor.
- **Sesiones sin cota ni expiración.** `agents/session_store.py` limita el historial
  **dentro** de una sesión (`MAX_TURNS = 20`), pero el diccionario `_store` que indexa
  por `session_id` no tiene límite de entradas ni TTL — cada `session_id` nuevo (trivial
  de generar: basta con omitirlo) es una entrada más que vive mientras el proceso esté
  arriba.
- **El lab soporta proveedores de pago por token** (`OPENROUTER_API_KEY`, Groq, NVIDIA
  NIM — ver `lab/README.md` § "Proveedores LLM"), no solo Ollama local: la "quema de
  presupuesto" no es hipotética en este proyecto, es una configuración soportada.
- **`document_extractor.py` parsea PDF/DOCX/XLSX sin ningún límite de tamaño, ratio de
  compresión, filas o páginas** — verificado leyendo las tres funciones de extracción.
  DOCX/XLSX son contenedores ZIP; un fichero de pocos KB puede descomprimirse a
  gigabytes en memoria del proceso backend, antes de que el LLM intervenga.

## Ataques en esta categoría

| # | Ataque | Subcarpeta | Distinción |
|---|--------|-----------|------------|
| 8 | Denegación de Servicio | [`denegacion-de-servicio/`](./denegacion-de-servicio) | Agota **cómputo/memoria** — flooding, input desmedido, sesiones sin cota, sponge examples, "overthinking" |
| 9 | Denial of Wallet | [`denial-of-wallet/`](./denial-of-wallet) | Agota **presupuesto** — vía proveedores de pago por token, o coste de cómputo en local |
| 10 | Extracción de Modelo | [`extraccion-de-modelo/`](./extraccion-de-modelo) | Roba **propiedad intelectual/comportamiento** del modelo vía muestreo sistemático de queries |
| 11 | Amplificación vía Documentos Adjuntos | [`amplificacion-documentos-adjuntos/`](./amplificacion-documentos-adjuntos) | Agota recursos en el **parser** (zip bombs DOCX/XLSX, PDF patológico) — el LLM nunca llega a ejecutarse |

Numeración `#8`–`#11` continúa la del catálogo existente (`anexo-catalogo-ataques-llm.md`
lista 7 ataques, #1 a #7) — pendiente de integrar formalmente en ese documento, ver
TODOs.md.

Los cuatro comparten el mecanismo de fondo (consumo no acotado) pero difieren en el
daño: #8 degrada o tumba el servicio; #9 genera coste económico real aunque el
servicio siga en pie; #10 no busca ni caída ni coste sino robar el comportamiento del
modelo; #11 es el único que no necesita que el LLM llegue a ejecutarse — el daño ocurre
en la capa de parsing de ficheros, antes del pipeline de defensa de prompt.

## Mapeo MITRE ATLAS (v4)

A diferencia de Excessive Agency (donde ATLAS no ofrece *technique ID*), esta categoría
sí tiene mapeo directo, bajo la táctica **Impact**:

- **[AML.T0029 — Denial of ML Service](https://atlas.mitre.org/techniques/AML.T0029)**:
  flooding de peticiones o inputs diseñados para forzar cómputo desproporcionado.
- **[AML.T0034 — Cost Harvesting](https://atlas.mitre.org/techniques/AML.T0034)**:
  peticiones de alto volumen o coste computacional para inflar el gasto operativo del
  objetivo — en despliegues por token, es *denial of wallet* explícito.
- **[AML.T0024 — Exfiltration via AI Inference API](https://atlas.mitre.org/techniques/AML.T0024)**
  (táctica **Exfiltration**): robo de datos de entrenamiento o del propio modelo vía
  volumen de queries — el mapeo de `extraccion-de-modelo/`.

`amplificacion-documentos-adjuntos/` no tiene *technique ID* de ATLAS propio —
honestidad metodológica, igual que ya declara el catálogo para Excessive Agency. Se
documenta con su clasificación general de seguridad de aplicaciones (CWE-409,
decompression bomb) en vez de fabricar un mapeo ATLAS que no existe.

## Filosofía de defensa (adelanto — detalle en `docs/defensas/`)

**Principio:** ningún recurso (tokens de salida, peticiones por minuto, sesiones
abiertas, coste acumulado) puede ser ilimitado por diseño. Si un límite no está escrito
en código o configuración, no existe — un system prompt no es un control de cuota.

Controles de referencia (OWASP): input validation, rate limiting, resource allocation
management, timeouts/throttling, sandboxing, logging/monitoring, graceful degradation,
límites de acciones encoladas.

## Estado

- [x] Categoría mapeada contra OWASP LLM10:2025 y MITRE ATLAS (AML.T0029, AML.T0034,
  AML.T0024)
- [x] Huecos reales del lab verificados contra el código (no asumidos)
- [x] **#8 y #9 con fixtures, defensa implementada y evidencia vulnerable-vs-defendida**
  — ver `lab/backend/tests/fixtures/llm10_scenarios.yaml`,
  `docs/defensas/LLM10-unbounded-consumption/` y
  `docs/reports/evidencia-llm10-unbounded-consumption.md`
- [ ] #10 y #11 siguen sin fixtures ni implementación — investigación únicamente (#10
  de bajo valor con el Ollama local por defecto; #11 requiere entorno aislado, ver sus
  fichas)
- [ ] Threat modeling, casos reales, análisis técnico profundo, cumplimiento normativo,
  playbook — mismo nivel de profundidad que LLM01/02/06/07 — pendiente para los 4
  ataques, ver TODOs.md
