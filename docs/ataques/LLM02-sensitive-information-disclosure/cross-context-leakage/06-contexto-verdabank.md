# 06 — Contexto VerdaBank

> Cross-Context Data Leakage (#3). Vínculo explícito con el incidente motivador **INC-2025-0089**.

## 1. El incidente que originó el TFM

**INC-2025-0089 — 15 de marzo de 2025.** Un cliente de VerdaBank manipuló a **Clara**, el asistente conversacional basado en LLM, para que revelara **el saldo de la cuenta de otro usuario** mediante *context manipulation*. El incidente fue clasificado como **brecha de dato personal** bajo **GDPR Art. 33** y **notificado a la AEPD**. Este evento **activa el proyecto PromptGuard**.

- Fuente interna: `docs/propuesta-formal-promptguard-fintech.md` §2.2.
- Catálogo: `docs/anexo-catalogo-ataques-llm.md` fila #3.

## 2. Narrativa

María (`usr_001`, cliente legítima con saldo de 15.420,50 € en `ES9121000418450200051332`, `lab/backend/src/models/banking.py:73-79`) abrió Clara desde la app con su sesión autenticada. En lugar de consultar su propia cuenta, redactó un mensaje apelando a un motivo de negocio creíble ("es la cuenta de mi empresa, necesito verificar un pago") y solicitó el saldo de **otra cuenta**. Clara, sin control de propiedad sobre la tool `consulta_saldo`, ejecutó la consulta contra la cuenta de un **tercer titular** y devolvió saldo e IBAN en su respuesta.

## 3. Objetivos viables en el lab

| Víctima | user_id | IBAN | Saldo expuesto | Origen |
|---------|---------|------|----------------|--------|
| Ana Fernández Ruiz | `usr_003` | `ES3421000418450200051334` | **231.500,00 €** | `atk_008` · `banking.py:87-93` |
| Admin Banco | `usr_admin` | `ES5821000418450200051335` | **999.999,99 €** | `atk_009` · `banking.py:94-100` |

Ambas cuentas son accesibles desde la sesión de `usr_001` porque `consulta_saldo` (`tools.py:44`) no comprueba pertenencia.

## 4. Timeline (ficticia, ilustrativa)

```mermaid
gantt
    title INC-2025-0089 — respuesta a incidente (reloj GDPR 72 h)
    dateFormat YYYY-MM-DD HH:mm
    axisFormat %d-%m %H:%M
    section Ataque
    Conversación con Clara (atk_008)        :crit, a1, 2025-03-15 10:42, 5m
    section Detección
    Toma de conocimiento (alerta/queja)     :crit, a2, 2025-03-15 16:30, 30m
    Clasificación CRITICAL (DPO)            :a3, after a2, 2h
    section Respuesta
    Contención (tool aislada)               :a4, 2025-03-15 19:00, 3h
    Borrador notificación AEPD              :a5, 2025-03-16 09:00, 8h
    Envío notificación AEPD (Art. 33)       :crit, a6, 2025-03-17 12:00, 1h
    section Cierre
    Comunicación al interesado (Art. 34)    :a7, 2025-03-18 10:00, 1h
    Post-mortem                              :a8, 2025-03-20 10:00, 4h
```

> El envío a la AEPD queda dentro de la ventana de **72 h** desde la detección.

## 5. Impacto cuantificado (estimación)

| Dimensión | Estimación |
|-----------|-----------|
| Clientes afectados (cuenta filtrada) | desde 1 (INC-2025-0089) hasta escenarios de exposición masiva por el mismo vector. |
| Tipo de dato | Financiero (saldo, IBAN) — considerado de alto riesgo por el GDPR. |
| Coste de notificación | Gestión Art. 33 + Art. 34 + atención al cliente por afectado. |
| Sanción GDPR potencial | Hasta **20M € o el 4 % de la facturación anual global**, lo que sea mayor (régimen sancionador del GDPR). |
| Reputacional | Pérdida de confianza en el canal conversacional. |

VerdaBank gestiona ≈900.000 clientes activos (`propuesta-formal-promptguard-fintech.md` §2.1); cualquier propagación del vector elevaría el recuento de afectados de forma directa.

## 6. Por qué este ataque es el núcleo del TFM

Es el único del catálogo que se traduce de forma inmediata en una **obligación regulatoria con reloj de 72 h**, lo que justifica que PromptGuard diseñe defensas (Output Auditor, strict session isolation) orientadas a bloquear la fuga antes de que salga del sistema.
