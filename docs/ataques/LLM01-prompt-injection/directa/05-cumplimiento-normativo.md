# Cumplimiento Normativo — Prompt Injection Directa

> Ataque #2 del catálogo · Mapeo a GDPR · DORA · EU AI Act

El ataque es un **vector de entrada**: la obligación de notificación se activa cuando el impacto se materializa (filtrado de dato personal o ejecución de tool no autorizada). Esta sección mapea el ataque contra los artículos aplicables del marco normativo del TFM.

---

## 1. GDPR (Reglamento 2016/679)

| Artículo | Requisito | Aplicación al ataque |
|----------|-----------|----------------------|
| **Art. 5.1.c** (minimización) | Los datos personales deben ser adecuados, pertinentes y limitados a lo necesario. | El system prompt de Clara y el contexto de sesión (`chat.py:62`) exponen IBANs y datos de cuenta al modelo. Si el atacante los recupera por inyección, se viola el principio de minimización: el dato no debería estar accesible para ese canal. |
| **Art. 32** (seguridad del tratamiento) | Medidas técnicas y organizativas apropiadas al riesgo. | Un canal conversacional sin sanitización de input ni control sobre el LLM no cumple el nivel de seguridad exigido. El Input Sanitizer (mencionado, no implementado en este documento) es la medida técnica de mitigación. |
| **Art. 33** (notificación ≤72 h) | Notificar a la autoridad competente (AEPD) en 72 h tras conocer una brecha. | Si la inyección tiene éxito y se filtra saldo de la cuenta admin, hay **brecha de dato personal** y se inicia el reloj de 72 h. |
| **Art. 34** (comunicación al interesado) | Comunicar la brecha al afectado cuando el riesgo sea alto. | El titular de la cuenta `ES58...1335` (usr_admin) debe ser informado del filtrado de sus datos financieros. |

> **Incidente motivador (INC-2025-0089):** la propuesta formal del TFM indica que el incidente del 15/03/2025 fue clasificado como brecha GDPR Art. 33 y notificado a la AEPD. La inyección directa es el vector que abre ese incidente.

## 2. DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Aplicación al ataque |
|----------|-----------|----------------------|
| **Art. 6** (marco de gestión del riesgo TIC) | Sistema de gestión del riesgo ICT integral. | La inyección a un chatbot que ejecuta tools bancarias es un riesgo ICT que debe estar inventariado. |
| **Art. 9** (protección y prevención TIC) | Controles sobre sistemas de información. | El canal conversacional debe tener control de entrada (Input Sanitizer) y validación de permisos en tools (Tool Gatekeeper). |
| **Art. 10** (detección de incidentes TIC) | Capacidad de detección en tiempo real. | El Compliance Logger debe registrar el intento de inyección y alimentar alertas en el dashboard LLM-SOC. |
| **Art. 11** (respuesta y recuperación) | Procesos de respuesta a incidentes y de recuperación. | El playbook de respuesta (`07-playbook-incident-response.md`) es el artefacto que satisface este artículo. |
| **Art. 17** (notificación de incidentes importantes) | Notificación a la autoridad de incidentes TIC importantes. | Si el ataque escala a fraude o filtrado masivo, puede alcanzar el umbral de incidente importante notificable. |

## 3. EU AI Act (Reglamento 2024/1689)

Clara se clasifica como **sistema de IA de alto riesgo** (acceso a servicios financieros).

| Artículo | Requisito | Aplicación al ataque |
|----------|-----------|----------------------|
| **Art. 9** (gestión de riesgos) | Sistema iterativo de gestión de riesgos durante el ciclo de vida. | El catálogo de 22 ataques es la base del análisis; LLM01 debe estar identificado como riesgo con su medida de mitigación. |
| **Art. 12** (registro de eventos / logs) | Registros que permitan trazabilidad. | Toda interacción con intento de inyección debe quedar registrada con firma de auditoría en el Compliance Logger. |
| **Art. 13** (transparencia e información a usuarios) | Los usuarios deben saber que interactúan con IA. | (Complementario; no específico del ataque, pero reforzado por el contexto.) |
| **Art. 14** (supervisión humana) | Supervisión humana efectiva. | Las tools de alto riesgo (`transferencia_nacional`) requieren confirmación humana; la inyección intenta precisamente eludirla. |
| **Art. 15** (robustez, ciberseguridad e informes) | Resiliencia frente a errores, fallos y ataques. | Medidas técnicas contra manipulación deliberada: Input Sanitizer multicapa + Output Auditor. |

## 4. Síntesis de notificación

| Evento | ¿Notificable? | Marco |
|--------|---------------|-------|
| Intento de inyección **bloqueado** | No (registro interno) | DORA Art. 10 · AI Act Art. 12 |
| Inyección con éxito → filtrado de saldo ajeno | **Sí** — AEPD ≤72 h | GDPR Art. 33/34 |
| Inyección con éxito → transferencia fraudulenta | **Sí** — incidente importante | DORA Art. 17 · GDPR Art. 33/34 |

La barrera entre "ruido operativo" y "brecha notificable" es el éxito del payload, no su mero envío.
