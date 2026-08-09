# TODOs — PromptGuard FinTech Lab

> **Última revisión: 2026-08-09** contra `main` (`9cdc25f`, PR #7 mergeada).
> Todo lo marcado `[x]` se ha verificado contra el código o los documentos reales, no contra
> memoria. La numeración de secciones (§1–§17) se conserva porque otros documentos la citan.

---

## 🔴 Prioritario — hacer ya

Lo que bloquea la nota, en orden. El resto del fichero es inventario; esto es el camino crítico.

| # | Qué | Por qué ya | Ref |
|---|---|---|---|
| **P1** | **Implementar el Input Sanitizer real** (LLM01 · Prompt Injection Directa) | Es el **único** módulo del pipeline que sigue siendo un no-op de 31 líneas que siempre devuelve `ALLOW`. `docs/defensas/README.md` promete 6 capas y el proxy entrega 5. Sin esto no hay comparativa antes/después del vector más citado del OWASP LLM Top 10. Ya está cableado en el orquestador (`_INPUT_SANITIZER`), solo hay que sobreescribir `evaluate()`. | §11, §16 |
| **P2** | **Medición unificada antes/después**: añadir `/chat/proxy` a `CHAT_ENDPOINTS` y correr las 108 fixtures × {vulnerable, defendido} en un solo Run Report | Henri y Daniel midieron cada uno con su runner propio (`ejecutar_evidencia.py` ×2). **No existe una sola tabla** que compare el sistema con y sin defensas sobre el corpus completo — y es exactamente el artefacto que pide el enunciado ("análisis crítico que valore la eficacia y las limitaciones"). | §8, §9, §17 |
| **P3** | **Arrancar el documento integrador de la memoria** (índice · estado del arte común · metodología · resultados agregados · conclusiones) | Hay dos capítulos individuales cerrados (Henri 10.8k palabras, Daniel 4.9k) y **ningún documento principal**. Tope de 20 páginas: cuanto antes se fije el índice, antes se sabe qué recortar. | — |
| **P4** | **Fijar la lista canónica de los 6 vectores críticos** | El profe pide "los seis vectores críticos acotados para el sector bancario"; el catálogo documenta **7** subcategorías. Ambigüedad viva desde hace semanas. Decidir: ¿se fusionan dos, se declara uno fuera de alcance, o se defiende el 7? | §7 |
| **P5** | **Cerrar Cross-Context Leakage (vector #3)** | Está mitigado por `_confidential_leak_guard`, un guard táctico dentro de `api/routes/chat.py` (6 tests), no por el módulo que describe `docs/defensas/.../cross-context-leakage.md`. O se sube a módulo propio, o se declara el alcance por escrito. Hoy el diseño y la implementación no coinciden. | §11 |
| **P6** | **Multi-modelo**: `--model` / `--provider` en `run_attack_suite.py` + re-correr el ranking | Los datos de 6 modelos en `lab/audit/runs-saves/` son del **28-jun**, anteriores a los fixes A1 (indicadores `tool_called_with`), A3 (memoria de sesión) y a la corrección de colisión de IDs que excluía 3 fixtures de toda corrida. **Esas cifras ya no son citables.** | §9, §16 |
| **P7** | **Sanear la deuda de documentación cruzada** | `CONTEXT.md` describe el vocabulario pero no menciona las stages del proxy ni el flag `vulnerable`. Los worktrees `software/` y `software-daniel/` conviven y el primero está 6 commits por detrás. | — |

---

## Estado global

| Bloque | Estado | Cifra verificada |
|---|---|---|
| Lab ejecutable · cold start | ✅ | `make run` (genera `.env`, levanta Ollama, descarga modelo, arranca stack) |
| Endpoints | ✅ | 5: `simple-prompt`, `complex-prompt`, `complex-with-context`, `complex-with-document`, `proxy` |
| Fixtures | ✅ | **108** (72 ataque / 20 legítimos / 12 navi) |
| Tests | ✅ | **156 recogidos**, 13 ficheros |
| Catálogo de ataques | ✅ | **60 docs** — 7 subcategorías × 8 |
| Catálogo de defensas (diseño) | ✅ | **12 docs** |
| Defensas implementadas | 🔶 **5 de 6** | Falta Input Sanitizer (P1) |
| Evidencia experimental | 🔶 | Por vector sí; agregada no (P2) |
| Memoria final | ❌ | 2 capítulos individuales, sin documento integrador (P3) |

### Cobertura vector × defensa

| # | Vector | Doc ataque | Fixtures | Diseño | Implementación | Evidencia |
|---|---|:-:|:-:|:-:|:-:|:-:|
| 1 | Excessive Agency (LLM06) | ✅ | ✅ | ✅ | ✅ Tool Gatekeeper | 🔶 |
| 2 | **Prompt Injection Directa (LLM01)** | ✅ | ✅ | ✅ | ❌ **no-op → P1** | ❌ |
| 3 | Cross-Context Leakage (LLM02) | ✅ | ✅ | ✅ | 🔶 guard ad-hoc → P5 | 🔶 |
| 4 | Confused Deputy (LLM06) | ✅ | ✅ | ✅ | ✅ Tool Gatekeeper | ✅ |
| 5 | System Prompt Leakage (LLM07) | ✅ | ✅ | ✅ | ✅ Output Auditor (184 líneas) | ✅ |
| 6 | PII Harvesting (LLM02) | ✅ | ✅ | ✅ | ✅ PII Shield (421 líneas) | ✅ |
| 7 | Indirecta vía Documento (LLM01) | ✅ | ✅ | ✅ | ✅ Sanitizer + detector estructural | ✅ |

---

## 1. Evidencia reproducible

- [x] Transcripción completa del ataque (turno a turno) — `lab/audit/runs/{run}/{endpoint}/*.md`
- [x] Respuesta JSON cruda del endpoint (`response`, `tools_used`, `latency_ms`, `error`) — Run Report
- [x] Logs del backend durante la ejecución — logging estructurado
- [x] System prompt de Clara en la cabecera del Session File — `audit_repository.py::_session_header`
- [x] Verdict (`SUCCESS`/`BLOCKED`/`UNKNOWN`) en el Session File — `evaluate.py` appendea `## Evaluación ·`
- [ ] Captura de pantalla del frontend durante el ataque (before/after defensa)
- [ ] Comando `curl`/script exacto para reproducirlo en una línea (con `user_id`, modelo y commit hash)
- [ ] GIF o vídeo corto de la explotación para la memoria

## 2. Biblioteca de payloads

- [x] Payloads que explotan de verdad los vectores "0%" — `daniel-tfm/01-vectores/investigacion-0pct/` (`atk_073`–`atk_076`)
- [x] Motor de mutación de PDF adversarios — `henri-tfm/01-ataque/payloads/`
- [ ] Más variantes por ataque (básico / intermedio / avanzado)
- [ ] Variantes multilingües (ES/EN) y por modelo objetivo
- [ ] Payloads parametrizables (plantilla con variables: IBAN, importe) — _decidido "no hacer" (D4)_
- [ ] Payloads encadenados que combinan dos ataques — _decidido "no hacer" (D4)_
- [ ] Generador de variantes automático — _decidido "no hacer" (D3)_

## 3. Métricas y medición

- [x] Tasa de éxito del ataque y tasa de bloqueo — `attack_success_rate`, `legitimate_false_positive_rate`, `navi_self_block_rate`
- [x] Latencia por intento — `latency_ms` capturado y promediado
- [x] Cuantificación de fixtures inestables (`--repeat`) — B2, 5 fixtures a n=4
- [x] Métrica de **fuga real** separada de artefactos de medición — `daniel-tfm/02-defensa/evidencia/analizar_resultados.py`
- [ ] **Por modelo: ¿cae Llama más que Claude ante el mismo payload?** → **P6**
- [ ] Número de turnos hasta éxito (ataques multi-turno como PII Harvesting)
- [ ] Severidad cuantificada (impacto en € estimado, nº de clientes afectados)

## 4. Mapeo taxonómico

- [x] MITRE ATLAS: tactic + technique — 18 docs con técnicas `AML.T*`
- [x] Mapeo a controles NIST AI RMF / ISO 27001 — 7 docs `01-mapeo-taxonomico.md`
- [x] Relación con otros OWASP LLM01-10 del catálogo
- [ ] Kill chain dibujada (recon → acceso → ejecución → impacto) — **parcial, 5 de 7**
- [ ] Mapeo a CAPEC y CWE cuando aplique — **0 menciones en todo `docs/`**

## 5. Threat modeling / scoring

- [x] Actor de amenaza, pre-requisitos, explotabilidad vs impacto, scoring — 7 docs `02-threat-modeling.md`

## 6. Casos reales y referencias

- [x] Incidentes públicos, papers académicos, CVE / blog posts, evolución de la técnica — 7 docs `03-casos-reales.md`

## 7. Análisis técnico profundo

- [x] Anatomía del payload comentada — 7 docs `04-analisis-tecnico.md` + `henri-tfm/01-ataque/anatomia-payload.md`
- [x] Diagrama de flujo del payload y diagrama de intercepción de la defensa — Mermaid en 34 ficheros de `docs/`
- [x] Por qué cae el LLM: mecanismo de fallo
- [x] Descubrimiento colateral documentado: el alignment del modelo bloquea payloads canónicos sin ninguna defensa — `docs/nota-descubrimiento-alignment-implicito.md`, `daniel-tfm/01-vectores/investigacion-0pct/`
- [ ] **Identificar y fijar los 6 vectores críticos canónicos** _(feedback profe)_ → **P4** — hoy hay 7 subcategorías documentadas y el profe habla de 6

## 8. Automatización / tests

- [x] 156 tests recogidos, 13 ficheros — incluye `test_tool_gatekeeper`, `test_pii_shield`, `test_output_auditor_secretos`, `test_confused_deputy_fixtures`, `test_proxy_pipeline_vectores`, `test_ablacion_defensas`, `test_flag_vulnerable`
- [x] Test de regresión atado a fixtures concretos — `test_confused_deputy_fixtures.py` (`atk_010`, `atk_020`, `atk_028`)
- [x] Integración con `run_attack_suite.py` (filtros `--id`, `--type`, `--kind`, `--repeat`)
- [x] Soporte `type: document-upload` (multipart) para el vector #7
- [x] Flag `vulnerable` en `ChatRequest` que desactiva todas las capas — línea base indefensa real
- [ ] **`/chat/proxy` en `CHAT_ENDPOINTS`** → **P2** (hoy el runner compartido solo cubre 4 de 5 endpoints)
- [ ] CI: la suite corre en cada PR y bloquea el merge si una defensa retrocede
- [ ] **Scope de Garak** _(feedback profe)_ — qué automatiza Garak vs qué queda como validación manual profunda

## 9. Análisis comparativo

- [x] Lista de modelos candidatos — `docs/modelos-candidatos.md` (10 modelos, 3 proveedores)
- [x] A/B de defensas por capa (estudio de ablación) — `test_ablacion_defensas.py` + `defensa_*` en `/chat/complex-with-document`
- [ ] **Ejecutar suite contra cada modelo y generar ranking** → **P6**. ⚠️ Los runs de 6 modelos en `runs-saves/` (28-jun) son **anteriores** a los fixes A1/A3 y a la corrección de colisión de IDs: no citables.
- [ ] Comparativa de configuraciones (¿ayuda reforzar el system prompt? ¿bajar temperature?)
- [ ] Matriz de cobertura completa: ataque × modelo × defensa

## 10. Cumplimiento normativo

- [x] GDPR, DORA, EU AI Act — 7 docs `05-cumplimiento-normativo.md` + `henri-tfm/03-normativa/` + `daniel-tfm/03-normativa/`
- [x] Citas legales verificadas contra fuente oficial (Henri, Fase 3)
- [ ] Plantilla de notificación AEPD 72h — _justificado inline como no aplicable: riesgo residual medido en 0%_
- [ ] Multas potenciales estimadas en el escenario

## 11. Defensa en profundidad

- [x] Diseño detallado del Tool Gatekeeper _(feedback profe)_ — `docs/defensas/LLM06-excessive-agency/`
- [x] Catálogo de defensas completo: 4 principios transversales + pipeline de referencia + 1 doc por ataque — `docs/defensas/` (12 docs)
- [x] Limitaciones y bypass conocidos declarados por módulo
- [x] Tool Gatekeeper (RBAC determinista), Output Auditor (LLM07 normalizado), PII Shield (entrada + salida), Document Sanitizer + detector estructural
- [ ] **Input Sanitizer real** → **P1**. `lab/backend/src/core/input_sanitizer.py` es un esqueleto de 31 líneas que devuelve `ALLOW` siempre.
- [ ] **Cross-Context Leakage con módulo propio** → **P5**. Hoy: `_confidential_leak_guard` dentro de `api/routes/chat.py`.
- [ ] Tokenización reversible de PII **antes** del modelo (el PII Shield actual actúa sobre la respuesta) — _declarado como trabajo futuro en `daniel-tfm/ROADMAP.md`_
- [ ] Presidio / NER genérico para nombres y direcciones arbitrarias — _declarado como trabajo futuro_
- [ ] Configuración recomendada (umbrales, `tool_permissions.yaml`, regex) documentada para producción

## 12. Perspectiva SOC / detección

> **Sección sin empezar.** 0 menciones a Sigma, IoC o Elasticsearch en todo `docs/`.
> Decidir si entra en alcance o se declara fuera explícitamente en la memoria.

- [ ] Firma Sigma/SIEM para detectar el patrón en logs
- [ ] IoCs conversacionales
- [ ] Queries de Elasticsearch para el dashboard LLM-SOC
- [ ] Alerta que generaría y su severidad

## 13. Incident response / playbook

- [x] Playbook paso a paso, post-mortem, línea temporal, lecciones aprendidas — 7 docs `07-playbook-incident-response.md`

## 14. Contexto del escenario VerdaBank

- [x] Narrativa del incidente, línea temporal, impacto en el escenario, relación con otros ataques — 7 docs `06-contexto-verdabank.md`

## 15. Visuales / multimedia

- [x] Diagramas Mermaid (flujo, defensa, pipeline) — 34 ficheros en `docs/`
- [x] Tablas comparativas y matrices
- [ ] Gráficos de resultados (barras de éxito/fracaso por modelo) — depende de **P6**
- [ ] Capturas / GIF de explotación — ver §1

## 16. Deuda técnica del lab

- [x] Verdict en sesiones de auditoría — `evaluate.py` appendea `## Evaluación ·` con `verdict`
- [x] System prompt en sesiones de auditoría — `audit_repository.py` lo escribe en la cabecera
- [x] Ollama en `docker-compose.yml` — servicio `ollama` bajo perfil, con volumen `ollama_data`
- [x] Validación de cold start _(feedback profe)_ — `make run` + `.env.example` + quickstart en `lab/README.md`
- [x] `audit_subdir` como ruta de contenedor (no del host) — corregido
- [x] `JUDGE_MODEL` por defecto inalcanzable (`qwen3.5:9b` nunca descargado) — pasar `JUDGE_MODEL=qwen2.5:3b` explícitamente hasta decidir default
- [ ] **Multi-modelo en el suite runner** (`--model` / `--provider`) → **P6**. Hoy solo prueba el modelo del `.env`.
- [ ] **Groq como proveedor online alternativo** — 0 rastro en `.env.example` ni en el código. Documentar `LLM_BASE_URL=https://api.groq.com/openai/v1` y añadir alias `LLM_PROVIDER=groq`.
- [ ] Fijar `temperature` o pasar a voto de mayoría — _decidido "no hacer" (B1)_; consecuencia asumida: las cifras con n bajo tienen ruido estocástico

## 17. Niveles de configuración del lab

Progresión de menos a más defensa. Cada nivel es un experimento independiente; los mismos fixtures
corren contra todos y el Run Report compara los Verdicts.

- [x] **Chat vulnerable** — flag `vulnerable` en `ChatRequest`, desactiva Output Auditor, leak guard, Gatekeeper, PII Shield e Input Sanitizer
- [x] **System prompt simple** — `POST /api/v1/chat/simple-prompt`
- [x] **System prompt complejo** — `POST /api/v1/chat/complex-prompt`
- [x] **System prompt complejo + contexto** — `POST /api/v1/chat/complex-with-context`
- [x] **Documento adjunto** — `POST /api/v1/chat/complex-with-document`, con ablación por capa (`defensa_*`)
- [x] **Detrás del proxy** — `POST /api/v1/chat/proxy` (pipeline completo, `SHADOW_MODE` disponible)
- [ ] **Los 6 niveles corridos contra el corpus completo en una sola pasada** → **P2**. El endpoint existe; lo que falta es que el runner compartido lo ejercite y produzca la tabla comparativa.

---

> **Mínimo rentable para una memoria TFM sólida:** `#1` Evidencia · `#3` Métricas ·
> `#4` Mapeo ATLAS/kill chain · `#9` Comparativa entre modelos.
> Los tres primeros están cubiertos. **`#9` es el que falta y es P6.**
