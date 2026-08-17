# TODOs — PromptGuard FinTech Lab

> **Última revisión: 2026-08-16** contra `main` (`3ddfacb`).
> Reorganizado en dos bloques: primero lo cerrado, después lo pendiente como roadmap por
> fases. Todo lo marcado `[x]` se ha verificado contra el código o los documentos reales,
> no contra memoria. La numeración de secciones (§1–§17) se conserva porque otros
> documentos la citan.

---

## Estado global

| Bloque | Estado | Cifra verificada |
|---|---|---|
| Lab ejecutable · cold start | ✅ | `make run` (genera `.env`, levanta Ollama, descarga modelo, arranca stack) |
| Endpoints | ✅ | 5: `simple-prompt`, `complex-prompt`, `complex-with-context`, `complex-with-document`, `proxy` |
| Fixtures | ✅ | **108** (72 ataque / 20 legítimos / 12 navi) |
| Tests | ✅ | **186+ recogidos**, 14 ficheros (se sumó `test_soc.py`, 30 tests) |
| Catálogo de ataques | ✅ | **60 docs** — 7 subcategorías × 8 |
| Catálogo de defensas (diseño) | ✅ | **12 docs** |
| Panel SOC / observabilidad | ✅ | 7 pantallas, captura turno a turno, 71 docs indexados — §12 ya no está "sin empezar" |
| Defensas implementadas | 🔶 **5 de 6** | Falta Input Sanitizer (P1) |
| Evidencia experimental | 🔶 | Por vector sí; agregada no (P2 — el endpoint ya está en el runner) |
| Memoria final | ❌ | 2 capítulos individuales, sin documento integrador (P3) |

### Cobertura vector × defensa

| # | Vector | Doc ataque | Fixtures | Diseño | Implementación | Evidencia |
|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | Excessive Agency (LLM06) | ✅ | ✅ | ✅ | ✅ Tool Gatekeeper | 🔶 |
| 2 | **Prompt Injection Directa (LLM01)** | ✅ | ✅ | ✅ | ❌ **no-op → P1** | ❌ |
| 3 | Cross-Context Leakage (LLM02) | ✅ | ✅ | ✅ | ✅ `core/leak_guard.py` + PII Shield | ✅ |
| 4 | Confused Deputy (LLM06) | ✅ | ✅ | ✅ | ✅ Tool Gatekeeper | ✅ |
| 5 | System Prompt Leakage (LLM07) | ✅ | ✅ | ✅ | ✅ Output Auditor (184 líneas) | ✅ |
| 6 | PII Harvesting (LLM02) | ✅ | ✅ | ✅ | ✅ PII Shield (421 líneas) | ✅ |
| 7 | Indirecta vía Documento (LLM01) | ✅ | ✅ | ✅ | ✅ Sanitizer + detector estructural | ✅ |

---

## ✅ Hecho

### §1 — Evidencia reproducible
- [x] Transcripción completa del ataque (turno a turno) — `lab/audit/runs/{run}/{endpoint}/*.md`
- [x] Respuesta JSON cruda del endpoint (`response`, `tools_used`, `latency_ms`, `error`) — Run Report
- [x] Logs del backend durante la ejecución — logging estructurado
- [x] System prompt de Clara en la cabecera del Session File — `audit_repository.py::_session_header`
- [x] Verdict (`SUCCESS`/`BLOCKED`/`UNKNOWN`) en el Session File — `evaluate.py` appendea `## Evaluación ·`

### §2 — Biblioteca de payloads
- [x] Payloads que explotan de verdad los vectores "0%" — `daniel-tfm/01-vectores/investigacion-0pct/` (`atk_073`–`atk_076`)
- [x] Motor de mutación de PDF adversarios — `henri-tfm/01-ataque/payloads/`

### §3 — Métricas y medición
- [x] Tasa de éxito del ataque y tasa de bloqueo — `attack_success_rate`, `legitimate_false_positive_rate`, `navi_self_block_rate`
- [x] Latencia por intento — `latency_ms` capturado y promediado
- [x] Cuantificación de fixtures inestables (`--repeat`) — B2, 5 fixtures a n=4
- [x] Métrica de **fuga real** separada de artefactos de medición — `daniel-tfm/02-defensa/evidencia/analizar_resultados.py`

### §4 — Mapeo taxonómico
- [x] MITRE ATLAS: tactic + technique — 18 docs con técnicas `AML.T*`
- [x] Mapeo a controles NIST AI RMF / ISO 27001 — 7 docs `01-mapeo-taxonomico.md`
- [x] Relación con otros OWASP LLM01-10 del catálogo

### §5 — Threat modeling / scoring
- [x] Actor de amenaza, pre-requisitos, explotabilidad vs impacto, scoring — 7 docs `02-threat-modeling.md`

### §6 — Casos reales y referencias
- [x] Incidentes públicos, papers académicos, CVE / blog posts, evolución de la técnica — 7 docs `03-casos-reales.md`

### §7 — Análisis técnico profundo
- [x] Anatomía del payload comentada — 7 docs `04-analisis-tecnico.md` + `henri-tfm/01-ataque/anatomia-payload.md`
- [x] Diagrama de flujo del payload y diagrama de intercepción de la defensa — Mermaid en 34 ficheros de `docs/`
- [x] Por qué cae el LLM: mecanismo de fallo
- [x] Descubrimiento colateral documentado: el alignment del modelo bloquea payloads canónicos sin ninguna defensa — `docs/nota-descubrimiento-alignment-implicito.md`, `daniel-tfm/01-vectores/investigacion-0pct/`

### §8 — Automatización / tests
- [x] 186+ tests recogidos, 14 ficheros — incluye `test_tool_gatekeeper`, `test_pii_shield`, `test_output_auditor_secretos`, `test_confused_deputy_fixtures`, `test_proxy_pipeline_vectores`, `test_ablacion_defensas`, `test_flag_vulnerable`, `test_soc` (30 tests)
- [x] Test de regresión atado a fixtures concretos — `test_confused_deputy_fixtures.py` (`atk_010`, `atk_020`, `atk_028`)
- [x] Integración con `run_attack_suite.py` (filtros `--id`, `--type`, `--kind`, `--repeat`)
- [x] Soporte `type: document-upload` (multipart) para el vector #7
- [x] Flag `vulnerable` en `ChatRequest` que desactiva todas las capas — línea base indefensa real
- [x] `/chat/proxy` añadido a `CHAT_ENDPOINTS` — mitad de P2. Falta la corrida y la tabla comparativa, ver roadmap.

### §9 — Análisis comparativo
- [x] Lista de modelos candidatos — `docs/modelos-candidatos.md` (10 modelos, 3 proveedores)
- [x] A/B de defensas por capa (estudio de ablación) — `test_ablacion_defensas.py` + `defensa_*` en `/chat/complex-with-document`

### §10 — Cumplimiento normativo
- [x] GDPR, DORA, EU AI Act — 7 docs `05-cumplimiento-normativo.md` + `henri-tfm/03-normativa/` + `daniel-tfm/03-normativa/`
- [x] Citas legales verificadas contra fuente oficial (Henri, Fase 3)

### §11 — Defensa en profundidad
- [x] Diseño detallado del Tool Gatekeeper _(feedback profe)_ — `docs/defensas/LLM06-excessive-agency/`
- [x] Catálogo de defensas completo: 4 principios transversales + pipeline de referencia + 1 doc por ataque — `docs/defensas/` (12 docs)
- [x] Limitaciones y bypass conocidos declarados por módulo
- [x] Tool Gatekeeper (RBAC determinista), Output Auditor (LLM07 normalizado), PII Shield (entrada + salida), Document Sanitizer + detector estructural
- [x] **Cerrado P5 — Cross-Context Leakage (§3 del catálogo)**: `_confidential_leak_guard` promovido de guard ad-hoc en `api/routes/chat.py` a módulo propio `core/leak_guard.py` (`confidential_leak_guard`, `verified_ibans_from_tools`), mismo patrón que `output_auditor.py`/`pii_shield.py`. Diseño (`docs/defensas/LLM02.../cross-context-leakage.md`) corregido contra la implementación real. Evidencia vulnerable/defendida con metodología de fuga real (no solo el criterio del fixture) en `docs/reports/evidencia-cross-context-leakage.md`: 83,3% de fuga real en la línea base, 0% con el pipeline defendido, 0 falsos positivos sobre el legítimo. 188 tests pasan tras el refactor.

### §12 — Perspectiva SOC / detección
> Corregido: esta sección estaba marcada como "sin empezar" en la revisión anterior. Ya no lo está — se diseñó e implementó completa entre el 8 y el 9 de agosto.
- [x] Panel LLM-SOC de 7 pantallas — Postura, Eventos, Alertas, Sesión, Conocimiento, Playbooks, Corridas (`soc.html`, hash routing)
- [x] Captura de decisiones del proxy turno a turno — `SocCollector`, un evento por componente, **incluso cuando la acción es `ALLOW`**
- [x] Persistencia en SQLite (`soc_turn`, `soc_event`, `soc_alert`) — `ADR 0007`, corregido para no vivir en el contenedor efímero (antes los tests la contaminaban)
- [x] Stream de eventos en vivo con polling incremental cada 2s, paginado, techo de 250 filas
- [x] Base de conocimiento indexada: 71 documentos de `docs/ataques/` y `docs/defensas/` por árbol de taxonomía
- [x] Alertas con severidad, procedencia (`fixture` / `mapa-categoria` / `por-defecto`) y estado (`nueva`/`revisada`/`descartada`) — triaje humano, el sistema no cierra nada solo
- [x] Accesibilidad: doble codificación color+forma, tema claro por física de proyector, `prefers-reduced-motion`, contraste AA verificado
- [x] 30 tests del almacén, collector, indexador y API — `test_soc.py`
- [x] Diseño y ADR documentados — `docs/soc/README.md`, `docs/adr/0007-dos-almacenes-para-la-traza-de-un-turno.md`

### §13 — Incident response / playbook
- [x] Playbook paso a paso, post-mortem, línea temporal, lecciones aprendidas — 7 docs `07-playbook-incident-response.md`

### §14 — Contexto del escenario VerdaBank
- [x] Narrativa del incidente, línea temporal, impacto en el escenario, relación con otros ataques — 7 docs `06-contexto-verdabank.md`

### §15 — Visuales / multimedia
- [x] Diagramas Mermaid (flujo, defensa, pipeline) — 34 ficheros en `docs/`
- [x] Tablas comparativas y matrices
- [x] Capturas de los tres sistemas (Playground, SOC, VerdaBank) para el README — `docs/img/`

### §16 — Deuda técnica del lab
- [x] Verdict en sesiones de auditoría — `evaluate.py` appendea `## Evaluación ·` con `verdict`
- [x] System prompt en sesiones de auditoría — `audit_repository.py` lo escribe en la cabecera
- [x] Ollama en `docker-compose.yml` — servicio `ollama` bajo perfil, con volumen `ollama_data`
- [x] Validación de cold start _(feedback profe)_ — `make run` + `.env.example` + quickstart en `lab/README.md`
- [x] `audit_subdir` como ruta de contenedor (no del host) — corregido
- [x] `JUDGE_MODEL` por defecto inalcanzable (`qwen3.5:9b` nunca descargado) — pasar `JUDGE_MODEL=qwen2.5:3b` explícitamente hasta decidir default
- [x] Worktree duplicado `software-daniel/` — ya no existe en disco, resuelto

### §17 — Niveles de configuración del lab
- [x] **Chat vulnerable** — flag `vulnerable` en `ChatRequest`, desactiva Output Auditor, leak guard, Gatekeeper, PII Shield e Input Sanitizer
- [x] **System prompt simple** — `POST /api/v1/chat/simple-prompt`
- [x] **System prompt complejo** — `POST /api/v1/chat/complex-prompt`
- [x] **System prompt complejo + contexto** — `POST /api/v1/chat/complex-with-context`
- [x] **Documento adjunto** — `POST /api/v1/chat/complex-with-document`, con ablación por capa (`defensa_*`)
- [x] **Detrás del proxy** — `POST /api/v1/chat/proxy` (pipeline completo, `SHADOW_MODE` disponible)

---

## 🔲 Pendiente — Roadmap

Cuatro fases, en orden de dependencia. No saltar una fase hasta que la anterior esté
cerrada: la Fase 3 (comparativa de modelos) depende de que la Fase 1 exista, y la memoria
(Fase 2) necesita que el alcance esté fijado antes de escribirse.

### Fase 1 — Cerrar el pipeline de defensa (bloqueante para todo lo demás)

- [ ] **P1 · Implementar el Input Sanitizer real** (§11) — único módulo no-op de las 6
  defensas prometidas. Ya está cableado en el orquestador (`_INPUT_SANITIZER`); solo hay
  que sobreescribir `evaluate()`. Sin esto no hay comparativa antes/después del vector
  más citado del OWASP LLM Top 10.
- [ ] **P2 · Medición unificada antes/después** (§8, §9, §17) — correr las 108 fixtures ×
  6 niveles en una sola pasada y generar el Run Report comparativo. El endpoint ya está
  en `CHAT_ENDPOINTS`; falta ejecutar la corrida y producir la tabla.

### Fase 2 — Decisiones de alcance y arranque de la memoria

- [ ] **P4 · Fijar la lista canónica de los 6 vectores críticos** (§7) — el catálogo
  documenta 7 subcategorías; el profesor habla de 6. Decidir: ¿se fusionan dos, se
  declara uno fuera de alcance, o se defiende el 7?
- [ ] **P3 · Arrancar el documento integrador de la memoria** — índice, estado del arte
  común, metodología, resultados agregados, conclusiones. Dos capítulos individuales
  cerrados (Henri 10.8k palabras, Daniel 4.9k), ningún documento principal. Tope de 20
  páginas: cuanto antes se fije el índice, antes se sabe qué recortar.
- [ ] Trasladar a la memoria (§10) los controles de PII/retención que un despliegue real
  necesitaría — ya documentados en `docs/soc/README.md` ("PII y retención"), falta
  integrarlos en el capítulo de cumplimiento normativo.

### Fase 3 — Comparativa multi-modelo

- [ ] **P6 · Multi-modelo**: `--model` / `--provider` en `run_attack_suite.py` + re-correr
  el ranking (§9, §16). Los datos de 6 modelos en `runs-saves/` (28-jun) son anteriores a
  los fixes A1 (indicadores `tool_called_with`), A3 (memoria de sesión) y a la corrección
  de colisión de IDs — **no citables**.
- [ ] Comparativa de configuraciones (§9): ¿ayuda reforzar el system prompt? ¿bajar
  `temperature`?
- [ ] Matriz de cobertura completa: ataque × modelo × defensa (§9)
- [ ] Gráficos de resultados por modelo (§15) — depende de P6

### Fase 4 — Evidencia, automatización y pulido final

- [ ] Captura de pantalla del frontend durante el ataque (before/after defensa) + GIF o
  vídeo corto de la explotación (§1, §15)
- [ ] Comando `curl`/script exacto para reproducir un ataque en una línea, con `user_id`,
  modelo y commit hash (§1)
- [ ] Número de turnos hasta éxito en ataques multi-turno (ej. PII Harvesting) (§3)
- [ ] Severidad cuantificada: impacto en €, nº de clientes afectados (§3)
- [ ] Kill chain dibujada completa — hoy parcial, 5 de 7 vectores (§4)
- [ ] Mapeo a CAPEC y CWE cuando aplique — 0 menciones hoy en `docs/` (§4)
- [ ] CI que corra la suite en cada PR y bloquee el merge si una defensa retrocede (§8)
- [ ] **Scope de Garak** _(feedback profe)_ — qué automatiza Garak vs qué queda como
  validación manual profunda (§8)
- [ ] Configuración recomendada para producción documentada: umbrales,
  `tool_permissions.yaml`, regex (§11)
- [ ] Groq como proveedor online alternativo — documentar
  `LLM_BASE_URL=https://api.groq.com/openai/v1` y alias `LLM_PROVIDER=groq` (§16)
- [ ] Multas potenciales estimadas en el escenario normativo (§10)
- [ ] Aislamiento de sesión por `user_id` en cada lectura (§11, I3 del diseño de
  Cross-Context Leakage) — `session_store.py` indexa solo por `session_id`, sin validar
  a quién pertenece. Declarado como hueco abierto en `core/leak_guard.py` y en
  `docs/defensas/LLM02.../cross-context-leakage.md` §5/§10 al cerrar P5; no lo cierra.
- [ ] Detección de importes ajenos sin IBAN al lado (§11, §4.3 del mismo diseño) — sigue
  siendo un diseño propuesto, sin código.

### Fase 5 — Ataques a la infraestructura (LLM10, nueva área)

> Hasta ahora el catálogo (#1–#7) solo cubre ataques a la **inteligencia** del
> modelo — convencerlo de hacer algo que no debería. Sesión de investigación abierta
> el 17/08 para la otra mitad: ataques a la **infraestructura** — volumen, tamaño o
> repetición de peticiones, sin necesidad de engañar a Clara en absoluto. Mapeado
> contra **OWASP LLM10:2025 — Unbounded Consumption**, **MITRE ATLAS AML.T0029**
> (Denial of ML Service), **AML.T0034** (Cost Harvesting) y **AML.T0024**
> (Exfiltration via AI Inference API). No bloquea las Fases 1–4 — es alcance nuevo, no
> una corrección de lo existente.

- [x] Investigación documentada — `docs/ataques/LLM10-unbounded-consumption/`
  (categoría + **4 ataques**: #8 denegación de servicio, #9 denial of wallet,
  #10 extracción de modelo, #11 amplificación vía documentos adjuntos) y
  `docs/defensas/LLM10-unbounded-consumption/` (Rate Limiter, Budget Guard, Query
  Pattern Monitor, Document Size Guard — diseño). Cuatro huecos reales del lab
  verificados contra el código: sin rate limiting, sin cap de tokens de salida,
  `session_store.py` sin cota ni TTL, `document_extractor.py` sin límite de tamaño,
  ratio de compresión, páginas ni filas.
- [x] Técnicas avanzadas de DoS incorporadas al mapeo de #8, con cita — *sponge
  examples* (Shumailov et al. 2021, amplificación de hasta 6000× medida en servicios de
  traducción reales), *"overthinking"* en modelos con razonamiento explícito (literatura
  2025-2026), ataques al framework de serving (Ollama) en vez de al modelo.
- [x] **#8 y #9 implementados, con fixtures y evidencia** (PR
  `feat/llm10-unbounded-consumption-defenses`, 17/08) — Rate Limiter
  (`core/rate_limiter.py`), cap de tokens de salida
  (`agents/clara_base.py::_default_model_settings`), cota LRU + TTL de sesiones
  (`agents/session_store.py`), Budget Guard (`core/budget_guard.py`). Cableados en
  `/chat/proxy`, respetan el flag `vulnerable` — misma metodología de comparación que
  el resto del proyecto. Fixtures nuevas: `lab/backend/tests/fixtures/
  llm10_scenarios.yaml` (`llm10_001` flood, `llm10_002` token_burn, `llm10_003`
  budget_burn, `llm10_navi_001` control legítimo), ejecutables con
  `lab/scripts/run_llm10_suite.py`. 18 tests nuevos (`test_rate_limiter.py`,
  `test_budget_guard.py`, `test_session_store_limits.py`), 206/206 del backend en
  verde. Evidencia vulnerable-vs-defendida en
  `docs/reports/evidencia-llm10-unbounded-consumption.md`.
- [ ] **#10 y #11 siguen sin implementar** (Query Pattern Monitor, Document Size
  Guard) — declarado fuera de esta PR: #10 tiene bajo valor con el Ollama local por
  defecto (sin IP que robar); #11 (zip bombs contra `document_extractor.py`) requiere
  un entorno aislado que no es el lab compartido de desarrollo.
- [ ] **Validación empírica bajo carga de producción real** — la evidencia capturada
  usa el lab de desarrollo con volumen acotado (decenas de peticiones), no un entorno
  de carga dedicado.
- [ ] **Tabla de coste real por proveedor** (€/1M tokens de OpenRouter/Groq/NVIDIA
  NIM vigentes) — necesaria para calibrar el Budget Guard, no investigada todavía.
- [ ] **Umbrales concretos del Document Size Guard** (#11) — tamaño máximo, ratio de
  compresión, páginas/filas — sin decidir, requieren calibrarse contra los documentos
  legítimos reales del lab para no romper el flujo del ataque #7.
- [ ] Resto de la profundidad que sí tienen LLM01/02/06/07 (7 docs por ataque: threat
  modeling, casos reales — incluidos CVEs conocidos de `pypdf`/`openpyxl`/`python-docx`
  para #11 —, análisis técnico, cumplimiento normativo, contexto VerdaBank, playbook) —
  hoy solo existe el mapeo taxonómico (`01-`) de cada uno.
- [ ] Integrar #8–#11 en `anexo-catalogo-ataques-llm.md` (el catálogo raíz sigue
  listando solo 7 ataques).
- [ ] Decidir si esta área entra en el alcance de la memoria final dado el tope de 20
  páginas (§ "Fase 2 · P4"), o queda como línea de investigación futura declarada.

---

## ❌ Descartado — decisiones explícitas

No son trabajo pendiente: son alcance que ya se decidió no cubrir. Se listan para que no
vuelvan a proponerse sin revisar la razón.

- Payloads parametrizables (plantilla con variables: IBAN, importe) — decidido "no hacer" (D4)
- Payloads encadenados que combinan dos ataques — decidido "no hacer" (D4)
- Generador de variantes automático — decidido "no hacer" (D3)
- Fijar `temperature` o pasar a voto de mayoría — decidido "no hacer" (B1); consecuencia
  asumida: las cifras con n bajo tienen ruido estocástico
- Plantilla de notificación AEPD 72h — no aplicable, riesgo residual medido en 0%
- Tokenización reversible de PII antes del modelo — declarado trabajo futuro en
  `daniel-tfm/ROADMAP.md`
- Presidio / NER genérico para nombres y direcciones arbitrarias — declarado trabajo futuro
- Firmas Sigma/SIEM e IoCs conversacionales (§12) — fuera de alcance deliberado; el SOC
  aporta el sustrato, no las firmas (`docs/soc/README.md` § "Trabajo declarado fuera de alcance")
- Cruce del SOC con ground truth (`fixture_expected_result`) o con el Verdict del Analyze
  Pass — fuera de alcance deliberado: mezclaría observación con evaluación
- Asignación de alertas a personas y fases cronometradas del playbook — fuera de alcance

---

> **Mínimo rentable para una memoria TFM sólida:** `#1` Evidencia · `#3` Métricas ·
> `#4` Mapeo ATLAS/kill chain · `#9` Comparativa entre modelos.
> Los tres primeros están cubiertos. La Fase 3 del roadmap (P6) es la que falta.
