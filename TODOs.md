# TODOs — PromptGuard FinTech Lab

## Próximos pasos

~~**Completados:**~~

- ~~**Evidencia reproducible (#1)**~~ ✅ — Audit repository implementado: fichero `.md` por sesión con transcript turno a turno (prompt → razonamiento → tools → respuesta → latencia). Run Report JSON+MD por ejecución de suite en `lab/audit/`.
- ~~**Métricas y medición (#3)**~~ ✅ — `run_attack_suite.py` produce métricas por ejecución: `attack_success_rate`, `legitimate_false_positive_rate`, `navi_self_block_rate`, latencia media. Desglose por kind y por categoría OWASP.
- ~~**Automatización del suite (#8)**~~ ✅ — `run_attack_suite.py` completo: corre los 3 kinds, calcula Verdict desde indicadores del fixture, genera JSON+MD, `make suite` lo ejecuta dentro del contenedor backend.
- ~~**Selección de modelos y ranking de vulnerabilidad (#9)**~~ ✅ (lista) — `docs/modelos-candidatos.md` creado: 10 modelos prioritarios en 3 proveedores (Ollama, OpenRouter, Groq). **Pendiente**: ejecutar la suite contra cada modelo y construir el ranking.

**En curso:**

1. **Calidad de la evidencia** `(§16)` — Deuda técnica de la evidencia: añadir Verdict (SUCCESS/BLOCKED/UNKNOWN) y system prompt de Clara en los ficheros de sesión. Sin esto la evidencia generada no es autocontenida ni interpretable de forma aislada.

2. **Cold start reproducible** `(§16 · feedback profe)` — `.env.example`, servicio Ollama en docker-compose, README de quickstart. Bloquea la corrección: si el profe no levanta el lab desde cero, el resto no se evalúa.

3. **Ejecutar suite multi-modelo y construir el ranking** `(§9)` — Con la evidencia sólida y el lab reproducible, correr la suite contra los modelos candidatos de `docs/modelos-candidatos.md` y producir el ranking de vulnerabilidad por modelo y categoría de ataque.

4. **Revisar cobertura de fixtures** `(§7 · feedback profe)` — Los vectores de ataque ya están definidos y documentados (catálogo de ataques seleccionados). Este paso es un análisis crítico: ¿tenemos fixtures suficientes y variados por vector para que la evidencia experimental sea convincente, o necesitamos añadir más casos?

---

Complementos posibles agrupados por tipo. Marcar con `[x]` los que se incorporen.

---

## 1. Evidencia reproducible

- [x] Transcripción completa del ataque (turno a turno: prompt → respuesta cruda del LLM) — `lab/audit/sessions/`
- [x] Respuesta JSON cruda del endpoint `/chat` (`response`, `tools_used`, `latency_ms`, `error`) — Run Report JSON
- [ ] Captura de pantalla del frontend durante el ataque (before/after defensa)
- [x] Logs del backend (`stdout` de `promptguard-backend`) durante la ejecución — logging estructurado añadido
- [ ] Comando `curl`/script exacto para reproducirlo en una sola línea (con `user_id`, modelo y commit hash)
- [ ] GIF o vídeo corto de la explotación para la memoria

## 2. Biblioteca de payloads

- [ ] Más variantes por ataque (básico / intermedio / avanzado)
- [ ] Variantes multilingües (ES/EN) y por modelo objetivo (Llama vs Claude vs GPT)
- [ ] Payloads parametrizables (plantilla con variables: IBAN, importe)
- [ ] Payloads encadenados que combinan dos ataques del catálogo
- [ ] Generador de variantes automático (mutaciones del payload base)

## 3. Métricas y medición

- [x] Tasa de éxito del ataque (vulnerable) y tasa de bloqueo — `attack_success_rate`, `legitimate_false_positive_rate`, `navi_self_block_rate` en Run Report
- [ ] Por modelo: ¿cae Llama más que Claude ante el mismo payload? — requiere ejecutar suite multi-modelo
- [ ] Número de turnos hasta éxito (ataques multi-turno como PII Harvesting)
- [x] Latencia y tokens consumidos por intento — `latency_ms` capturado por fixture y promediado
- [ ] Severidad cuantificada (impacto en € estimado, nº de clientes afectados)

## 4. Mapeo taxonómico

- [ ] MITRE ATLAS completo: tactic + technique + sub-technique
- [ ] Kill chain del ataque dibujada (recon → acceso → ejecución → impacto)
- [ ] Mapeo a CAPEC y CWE cuando aplique
- [ ] Mapeo a controles NIST AI RMF / ISO 27001
- [ ] Relación con otros OWASP LLM01-10 del catálogo

## 5. Threat modeling / scoring

- [ ] Actor de amenaza (script kiddie, fraude organizado, insider)
- [ ] Pre-requisitos del ataque (sesión, conocimiento previo…)
- [ ] Explotabilidad vs impacto (matriz de riesgo)
- [ ] Score tipo CVSS adaptado a LLM o el de ATLAS

## 6. Casos reales y referencias

- [ ] Incidentes públicos del mismo tipo (Air Canada chatbot, Bing DAN, Samsung ChatGPT leak…)
- [ ] Papers académicos clave por ataque (Carlini para data extraction, Greshake para indirect injection…)
- [ ] CVE / blog posts de la industria
- [ ] Historia/evolución de la técnica

## 7. Análisis técnico profundo

- [ ] **Identificar y fijar los 6 vectores de ataque críticos para banca** _(feedback profe)_ — El profe los llama explícitamente "los seis vectores críticos acotados para el sector bancario". Necesitamos una lista canónica de cuáles son los 6 y asegurarnos de que cada uno tiene evidencia experimental completa (no solo fixture automatizado).
- [ ] Anatomía del payload: desglose comentado de por qué funciona — uno por cada uno de los 6 vectores críticos
- [ ] Diagrama de flujo (Mermaid): cómo viaja el payload por el sistema
- [ ] Diagrama de la defensa: en qué punto exacto intercepta el proxy
- [ ] Por qué cae el LLM: mecanismo de fallo (alignment failure, role confusion, context bleed)

## 8. Automatización / tests

- [ ] Caso pytest automatizado por ataque (input → assert esperado)
- [ ] Test de regresión que verifique que la defensa sigue bloqueándolo
- [x] Integración de cada ataque con `run_attack_suite.py` (filtros por `--id`, `--type`, `--kind`) — `make suite ARGS="..."`
- [ ] CI: la suite corre en cada PR y bloquea el merge si una defensa retrocede
- [ ] **Scope de Garak** _(feedback profe)_ — Definir qué automatiza Garak (generación de variantes, fuzzing de payloads) y qué queda como validación experimental manual/profunda. La automatización no debe sustituir el análisis en profundidad de los 6 vectores críticos.

## 9. Análisis comparativo

- [x] Lista de modelos candidatos definida — `docs/modelos-candidatos.md` (10 modelos prioritarios, 3 proveedores)
- [ ] Ejecutar suite completa contra cada modelo candidato y generar ranking de vulnerabilidad
- [ ] Comparativa de configuraciones (¿ayuda reforzar el system prompt? ¿bajar temperature?)
- [ ] A/B de defensas (regex vs ML vs LLM guard) — qué capa caza cada ataque
- [ ] Matriz de cobertura: ataque × modelo × defensa

## 10. Cumplimiento normativo

- [ ] GDPR: artículo exacto + plantilla de notificación AEPD 72h
- [ ] DORA: artículos con texto y cómo los satisface el módulo
- [ ] EU AI Act: requisitos concretos (Art. 13/14/15) y estado verde/amarillo/rojo
- [ ] EBA guidelines / PSD2 si aplica
- [ ] Multas potenciales estimadas en el escenario

## 11. Defensa en profundidad

- [ ] **Diseño detallado del Tool Gatekeeper** _(feedback profe)_ — El profe pide que documentemos explícitamente cómo gestiona permisos en tiempo real para evitar confused deputy. Concretar: ¿qué comprueba antes de ejecutar cada tool? ¿cómo decide si el contexto del mensaje justifica el permiso? ¿qué herramientas quedan fuera de alcance por rol/sesión?
- [ ] Defensa primaria (PromptGuard) + secundarias alternativas
- [ ] Configuración recomendada (umbrales, parámetros del `tool_permissions.yaml`, regex)
- [ ] Limitaciones de la defensa (¿cuándo falla?)
- [ ] Bypass conocidos de la propia defensa

## 12. Perspectiva SOC / detección

- [ ] Firma Sigma/SIEM para detectar el patrón en logs
- [ ] IoCs conversacionales (indicadores de que se está intentando)
- [ ] Queries de Elasticsearch para el dashboard LLM-SOC
- [ ] Alerta que generaría y su severidad

## 13. Incident response / playbook

- [ ] Playbook paso a paso si el ataque tiene éxito (contención, erradicación, recuperación)
- [ ] Post-mortem template
- [ ] Línea temporal del incidente
- [ ] Lecciones aprendidas / hardening derivado

## 14. Contexto del escenario VerdaBank

- [ ] Narrativa del incidente (storytelling con víctima concreta: `usr_001` María…)
- [ ] Línea temporal ficticia (INC-2025-0089 para el ataque #3)
- [ ] Impacto cuantificado en el escenario (€, clientes, reputación)
- [ ] Relación con otros ataques del catálogo (qué habilita, con qué se solapa)

## 15. Visuales / multimedia

- [ ] Diagramas Mermaid (flujo, kill chain, defensa)
- [ ] Tablas comparativas y matrices
- [ ] Gráficos de resultados (barras de éxito/fracaso por modelo)
- [ ] Mapa mental del ataque

## 17. Niveles de configuración del lab

Hoy el lab tiene dos modos: **chat vulnerable** y **chat protegido**. La evaluación experimental requiere una progresión más granular que aísle cada variable de defensa por separado.

Estado actual:
- [x] Chat vulnerable — sin ninguna protección, system prompt complejo con contexto inyectado en el mensaje

Pendiente — progresión propuesta (de menos a más defensa):

- [x] **Chat con system prompt simple** — `POST /api/v1/chat/simple-prompt`. System prompt mínimo (rol + capacidades + formato). Sin reglas de seguridad ni contexto de usuario.
- [x] **Chat con system prompt complejo** — `POST /api/v1/chat/complex-prompt`. System prompt completo de Clara. Sin contexto de usuario inyectado.
- [x] **Chat con system prompt complejo + contexto** — `POST /api/v1/chat/complex-with-context`. System prompt complejo + bloque `[Contexto del usuario autenticado]` en el mensaje.
- [ ] **Chat detrás del proxy** — system prompt complejo + contexto + capa PromptGuard activa. Sin contexto adicional en el proxy.
- [ ] **Chat detrás del proxy con contexto** — proxy activo con contexto de usuario propagado al proxy para que pueda tomar decisiones informadas.
- [ ] **Chat detrás del proxy con contexto y system prompt complejo** — configuración completa: proxy + contexto + system prompt complejo en Clara. Nivel de protección máximo del lab.

> Cada nivel es un experimento independiente. Los mismos fixtures corren contra todos los niveles y el Run Report compara los Verdicts — así se mide el efecto aislado de cada capa de defensa.

---

## 16. Deuda técnica del lab

Mejoras detectadas durante la implementación. Resolver antes de la fase de evaluación multi-modelo.

- [ ] **Verdict en sesiones de auditoría** — El fichero `.md` de sesión no indica si el agente bloqueó o procesó el ataque. Añadir el `expected_result` del fixture y el Verdict calculado (SUCCESS/BLOCKED/UNKNOWN) en la cabecera de cada turno.
- [ ] **System prompt en sesiones de auditoría** — El agente tiene más contexto del esperado. Capturar el system prompt de Clara en la cabecera del fichero de sesión para que la evidencia sea autocontenida y reproducible.
- [ ] **Multi-modelo en el suite runner** — `run_attack_suite.py` solo prueba el modelo configurado en `.env`. Añadir `--model` y `--provider` como argumentos para ejecutar la misma suite contra distintos modelos en una sola pasada y comparar resultados directamente en el Run Report.
- [ ] **Ollama en docker-compose** — Añadir un servicio `ollama` al `docker-compose.yml` como alternativa de infra local (imagen `ollama/ollama`). El backend ya lo soporta con `LLM_PROVIDER=ollama`; falta el servicio y la configuración de red para que el backend lo alcance sin `host.docker.internal`.
- [ ] **Groq como proveedor online alternativo** — El backend soporta `LLM_PROVIDER=custom`; documentar la configuración de Groq (`LLM_BASE_URL=https://api.groq.com/openai/v1`) y añadir `LLM_PROVIDER=groq` como alias explícito para mayor claridad. Ver `docs/modelos-candidatos.md` para los modelos candidatos.
- [ ] **Validación de cold start** _(feedback profe)_ — El profe insiste en que la corrección se hará desplegando desde cero. Verificar que `docker compose up` en una máquina limpia (sin modelos descargados, sin `.env` previo) levanta todo en <5 min con instrucciones claras. Necesita: `.env.example`, script de descarga del modelo Ollama si se usa local, y `README` de quickstart.

---

> **Mínimo rentable sugerido para una memoria TFM sólida:**
> `#1` Evidencia · `#3` Métricas · `#4` Mapeo ATLAS/kill chain · `#9` Comparativa entre modelos.
> Son las que más diferencian un trabajo evaluativo frente a una mera descripción.
