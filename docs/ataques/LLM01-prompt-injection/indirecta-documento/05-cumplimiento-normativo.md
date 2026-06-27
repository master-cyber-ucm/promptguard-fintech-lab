# 05 — Cumplimiento Normativo

> **Ataque #7** — Prompt Injection Indirecta — Documento
> Análisis PRE-implementación. Artículos citados estrictamente del repertorio permitido.

---

## 1. GDPR (Reglamento UE 2016/679)

| Artículo | Requisito | Aplicación al ataque #7 |
|----------|-----------|--------------------------|
| **Art. 5.1.c** | **Minimización de datos.** Los datos personales deben ser adecuados, pertinentes y limitados a lo necesario. | Si el payload oculto fuerza la lectura de saldo/IBAN de terceros desde el contexto, se procesan datos **fuera del propósito** declarado por VerdaBank al cliente cuyos datos se filtran. |
| **Art. 32** | **Seguridad del tratamiento.** Medidas técnicas y organizativas apropiadas al riesgo. | Tratar el texto extraído de PDFs como contexto confiable sin sanitización es una **omisión de medida técnica**. El Input Sanitizer extendido al canal documental es la salvaguarda esperable. |
| **Art. 33** | **Notificación a la autoridad de control en 72 h.** | Si la inyección logra fuga de PII de terceros, se activa la obligación de **notificar a la AEPD** en un plazo de 72 h desde la detección. |
| **Art. 34** | **Comunicación al interesado.** | Si la brecha implica **alto riesgo** para derechos y libertades (p. ej. IBAN + saldo de cuentas ajenas), debe comunicarse además a los **clientes afectados**. |

**Obligación de notificación aplicable:** Sí. La fuga de PII financiera de terceros vía el canal documental encaja en los supuestos de los Arts. 33 y 34.

---

## 2. DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Aplicación al ataque #7 |
|----------|-----------|--------------------------|
| **Art. 9** | **Protección y prevención** de los activos de TI bajo control de la entidad. | El canal conversacional con subida de documentos es un activo de TI; el riesgo de indirect injection debe estar identificado y mitigado en su diseño. |
| **Art. 10** | **Detección** de incidentes de TIC. | El Compliance Logger y el dashboard LLM-SOC deben generar alerta cuando un PDF contenga instrucciones detectadas en su texto extraído. |

> *Arts. 6, 11 y 17 del repertorio DORA quedan fuera del impacto directo de este ataque concreto (afectan a gobernanza del marco ICT, gestión del incidente grave y de terceros, respectivamente).*

---

## 3. EU AI Act (Reglamento UE 2024/1689)

Clara es clasificada como **sistema de IA de alto riesgo** (Anexo III, categoría 5.b — acceso a servicios financieros) en la propuesta formal (`docs/propuesta-formal-promptguard-fintech.md:522`).

| Artículo | Requisito | Aplicación al ataque #7 |
|----------|-----------|--------------------------|
| **Art. 9** | **Sistema de gestión de riesgos** durante todo el ciclo de vida. | El ataque #7 debe figurar como riesgo identificado; este documento y su kill chain alimentan directamente dicho sistema. |
| **Art. 15** | **Robustez, ciberseguridad y accuracy.** Medidas técnicas contra manipulación intencionada o uso indebido. | La omisión de sanitización sobre texto extraído de PDFs es una **brecha de robustez** exigible bajo este artículo. |

> *Arts. 12, 13 y 14 (trazabilidad, transparencia al usuario, supervisión humana) ya están cubiertos transversalmente por el Compliance Logger y el Tool Gatekeeper; el ataque #7 no introduce obligaciones adicionales en esos artículos.*

---

## 4. Síntesis de obligaciones accionables

| Obligación | Marco | Plazo / momento |
|------------|-------|-----------------|
| Sanitizar texto extraído de documentos antes del LLM | GDPR Art. 32 · AI Act Art. 15 | Antes de habilitar el canal documental |
| Registrar cada subida y su texto extraído | DORA Art. 10 · GDPR Art. 32 | En tiempo de ejecución |
| Notificar a la AEPD ante fuga de PII | GDPR Art. 33 | ≤ 72 h desde la detección |
| Comunicar al cliente afectado si hay alto riesgo | GDPR Art. 34 | Sin retraso indebido |
| Re-evaluar el sistema de gestión de riesgos | AI Act Art. 9 | Tras cada modificación relevante del sistema |
