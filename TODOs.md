# TODOs — PromptGuard FinTech Lab

## Próximos pasos

1. **Evidencia reproducible (#1)** — Definir y generar los artefactos de evidencia por ataque: transcript turno a turno, respuesta JSON cruda, comando `curl` exacto con commit hash. El formato se fija aquí para que todo lo posterior lo respete.
2. **Métricas y medición (#3)** — Definir las métricas que debe producir cada ejecución: tasa de éxito/bloqueo, latencia, severidad cuantificada. Se diseñan sobre la estructura de evidencia del paso anterior.
3. **Automatización del suite (#8)** — Completar `run_attack_suite.py` para que al ejecutar los fixtures genere automáticamente toda la base de evidencias auditables definida en los pasos 1 y 2.
4. **Selección de modelos y ranking de vulnerabilidad (#9)** — Definir la lista de modelos a probar (ej. Llama 3, Mistral, Gemma, Qwen…), ejecutar el suite completo contra cada uno y documentar un ranking de vulnerabilidad: qué modelo cae más, ante qué categoría de ataque, y con qué severidad.

---

Complementos posibles agrupados por tipo. Marcar con `[x]` los que se incorporen.

---

## 1. Evidencia reproducible

- [ ] Transcripción completa del ataque (turno a turno: prompt → respuesta cruda del LLM)
- [ ] Respuesta JSON cruda del endpoint `/chat` (`response`, `tools_used`, `latency_ms`, `error`)
- [ ] Captura de pantalla del frontend durante el ataque (before/after defensa)
- [ ] Logs del backend (`stdout` de `promptguard-backend`) durante la ejecución
- [ ] Comando `curl`/script exacto para reproducirlo en una sola línea (con `user_id`, modelo y commit hash)
- [ ] GIF o vídeo corto de la explotación para la memoria

## 2. Biblioteca de payloads

- [ ] Más variantes por ataque (básico / intermedio / avanzado)
- [ ] Variantes multilingües (ES/EN) y por modelo objetivo (Llama vs Claude vs GPT)
- [ ] Payloads parametrizables (plantilla con variables: IBAN, importe)
- [ ] Payloads encadenados que combinan dos ataques del catálogo
- [ ] Generador de variantes automático (mutaciones del payload base)

## 3. Métricas y medición

- [ ] Tasa de éxito del ataque (vulnerable) y tasa de bloqueo (con PromptGuard)
- [ ] Por modelo: ¿cae Llama más que Claude ante el mismo payload?
- [ ] Número de turnos hasta éxito (ataques multi-turno como PII Harvesting)
- [ ] Latencia y tokens consumidos por intento
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

- [ ] Anatomía del payload: desglose comentado de por qué funciona
- [ ] Diagrama de flujo (Mermaid): cómo viaja el payload por el sistema
- [ ] Diagrama de la defensa: en qué punto exacto intercepta el proxy
- [ ] Por qué cae el LLM: mecanismo de fallo (alignment failure, role confusion, context bleed)

## 8. Automatización / tests

- [ ] Caso pytest automatizado por ataque (input → assert esperado)
- [ ] Test de regresión que verifique que la defensa sigue bloqueándolo
- [ ] Integración de cada ataque con `run_attack_suite.py` (filtros por `--id`, `--type`)
- [ ] CI: la suite corre en cada PR y bloquea el merge si una defensa retrocede

## 9. Análisis comparativo

- [ ] Comparativa entre modelos ante el mismo payload
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

---

> **Mínimo rentable sugerido para una memoria TFM sólida:**
> `#1` Evidencia · `#3` Métricas · `#4` Mapeo ATLAS/kill chain · `#9` Comparativa entre modelos.
> Son las que más diferencian un trabajo evaluativo frente a una mera descripción.
