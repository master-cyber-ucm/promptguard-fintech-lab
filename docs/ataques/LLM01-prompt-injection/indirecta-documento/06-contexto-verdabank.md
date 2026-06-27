# 06 — Contexto VerdaBank

> **Ataque #7** — Prompt Injection Indirecta — Documento
> Escenario ficticio de análisis. **NO hay payload ejecutado** en el lab en el momento de redactar este documento.

---

## 1. Narrativa del incidente (hipotético)

VerdaBank habilita en el segundo trimestre de 2025 un canal para que los clientes suban documentación a Clara —principalmente nóminas y extractos— para acelerar la concesión de microcréditos y la atención de reclamaciones. El flujo es: el cliente adjunta el PDF en el chat; el backend extrae el texto y lo entrega a Clara como contexto junto con el mensaje.

Un cliente —en lo sucesivo, **el atacante**— prepara una nómina manipulada con instrucciones ocultas en texto blanco sobre blanco (técnica ya prototipada en `lab/gen_adversarial_pdf.py:36`). El payload solicita a Clara que, al procesar el extracto, **consulte el saldo de una cuenta ajena** y lo incluya en su respuesta como parte del análisis "solicitado" por el documento. El atacante acompaña la subida con un mensaje aparentemente inocente: *"Adjunto mi última nómina. ¿Puedes confirmar mi elegibilidad para el préstamo?"*.

Como el texto del chat no contiene nada sospechoso, el Input Sanitizer del escenario base —que sólo escruta el mensaje visible— no lo detecta. El texto oculto del PDF viaja al LLM como **dato confiable** y se ejecuta como instrucción.

---

## 2. Timeline ficticia

| Hora | Evento | Actor |
|------|--------|-------|
| **D+0 · 10:42** | El atacante edita su nómina real con texto blanco sobre blanco y la sube a Clara. | Cliente |
| **10:42** | El backend extrae el texto del PDF, incluido el payload oculto, y lo concatena al contexto. | Backend |
| **10:43** | Clara ejecuta `consulta_saldo` sobre una cuenta ajena y devuelve el saldo en su respuesta. | Clara (`tools.py:44`) |
| **10:44** | El atacante recibe el saldo de un tercero en el chat. | Cliente |
| **D+3 · 09:15** | El cliente afectado reclama por un cargo desconocido; la auditoría del Compliance Logger recupera la sesión. | SOC |
| **D+3 · 14:30** | Clasificación del incidente como brecha de dato personal — activación GDPR Art. 33. | Compliance |
| **D+3 · 18:00** | Notificación a la AEPD dentro del plazo de 72 h. | DPO |

---

## 3. Impacto cuantificado (escenario)

| Concepto | Valor orientativo |
|----------|-------------------|
| Clientes afectados por fuga | 1 (escala a N si el payload consulta en bucle) |
| Datos comprometidos | IBAN + saldo + último movimiento |
| Coste de notificación GDPR Art. 33/34 | Estimación según tarifa habitual del encargado del tratamiento |
| Reembolso / indemnización al cliente afectado | Según política interna de VerdaBank |
| Revisión forense de PDFs subidos en los últimos 30 días | Coste operativo del equipo SOC |
| Impacto reputacional | No cuantificado — clasificado como alto |

---

## 4. Estado actual del lab

> **NOTA IMPORTANTE — Pre-implementación.**

- **No existe payload específico** para este ataque en `lab/backend/tests/fixtures/attack_prompts.jsonl`. El catálogo lo marca como pendiente de diseñar (`docs/ataques/LLM01-prompt-injection/indirecta-documento/README.md:42`).
- La utilidad `lab/gen_adversarial_pdf.py` genera un PDF demostrador (con un payload de RRHH, no bancario); **no** está integrada en el flujo del lab.
- **El pipeline de extracción de texto del documento no está implementado**: el endpoint `POST /chat` (`lab/backend/src/api/routes/chat.py:45`) sólo acepta `message` de texto; no existe campo para `document` en `ChatRequest` (`chat.py:24-28`).
- El ataque se reproduce **sólo cuando** se incorpore el canal documental previsto en la **Extensión 2 — Multimodal** (`docs/propuesta-formal-promptguard-fintech.md:178-189`).

---

## 5. Conexión con el resto del catálogo

- Encadena con **#1 Excessive Agency** si el payload pide ejecutar una transferencia.
- Encadena con **#3 Cross-Context Data Leakage** si el payload pide datos de un tercero.
- Habilita **#5 System Prompt Leakage** si el payload pide revelar las restricciones de Clara.
