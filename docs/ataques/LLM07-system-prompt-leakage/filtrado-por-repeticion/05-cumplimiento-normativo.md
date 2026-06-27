# 05 — Cumplimiento Normativo

> System Prompt Leakage — Mapeo a GDPR, DORA y EU AI Act.
> Solo se citan **artículos de las normativas permitidas** en el alcance del TFM.

## Premisa (alineada con OWASP)

OWASP LLM07:2025 establece que **el system prompt no es un mecanismo de control de acceso**. Esta premisa condiciona todo el análisis: cualquier secreto embebido en el prompt (`clara_system.txt:27-29`) está, por diseño, insuficientemente protegido.

## 1. GDPR (Reglamento UE 2016/679)

| Artículo | Requisito | Incumplimiento en el lab |
|----------|-----------|--------------------------|
| **Art. 5.1.c — Minimización** | Los datos personales deben ser *adecuados, pertinentes y limitados a lo necesario*. | Embeber `API_KEY_INTERNAL`, host de DB y bucket en el prompt viola el principio: **ninguno de esos secretos pertenece al contexto conversacional** con el cliente. |
| **Art. 32 — Seguridad del tratamiento** | Medidas técnicas y organizativas apropiadas (pseudonimización, cifrado, control de acceso). | Un secreto en texto plano dentro del prompt no está protegido por RBAC ni por cifrado: viaja con cada llamada al LLM y es emitible por el modelo. **No es una medida apropiada.** |
| **Art. 33 — Notificación a la autoridad** | Brecha de datos personales → AEPD en **72 h**. | Si `API_KEY_INTERNAL` da acceso a datos de clientes, su filtración activa el reloj de 72 h (motivado por el incidente INC-2025-0089, `propuesta-formal-promptguard-fintech.md:45`). |
| **Art. 34 — Comunicación al interesado** | Notificación al afectado cuando riesgo alto. | Aplicable si la filtración escala a acceso a cuentas. |

## 2. DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Mapeo al ataque |
|----------|-----------|-----------------|
| **Art. 6 — Marco de gestión del riesgo ICT** | Políticas para identificar, clasificar y documentar riesgos. | El system prompt con secretos debe figurar como activo ICT de riesgo y ser objeto de revisión. |
| **Art. 9 — Protección y prevención ICT** | Controles sobre el canal conversacional. | La instrucción `NUNCA reveles` **no es un control preventivo válido** según OWASP; requiere el Output Auditor. |
| **Art. 10 — Detección** | Capacidad de identificar anomalías. | Detección de patrones de filtración (regex sobre `api_key_internal`, `db-banking`, límites exactos) en tiempo real. |
| **Art. 11 — Respuesta y recuperación** | Contención y restauración. | Rotación inmediata del secreto "filtrado" (ver `07-playbook-incident-response.md`). |
| **Art. 17 — Notificación de incidentes mayores** | Comunicación a la autoridad competente. | Si la filtración del secreto escala a incidente mayor, aplica el escalado regulatorio. |

## 3. EU AI Act (Reglamento UE 2024/1689)

Clara se clasifica como **sistema de IA de alto riesgo** (Anexo III, categoría 5.b — acceso a servicios financieros; `propuesta-formal-promptguard-fintech.md:522`).

| Artículo | Requisito | Mapeo al ataque |
|----------|-----------|-----------------|
| **Art. 9 — Gestión de riesgos** | Identificación y mitigación de riesgos conocidos. | System Prompt Leakage es un riesgo catalogado (OWASP LLM07); debe figurar en el análisis con su mitigación. |
| **Art. 12 — Registro (logging)** | Eventos registrados que permitan trazabilidad. | El Compliance Logger debe registrar tanto el payload de filtración como el output emitido por el LLM. |
| **Art. 13 — Transparencia e información** | Diseño transparente hacia los usuarios. | Un secreto en el prompt invisible para el usuario, pero exfiltrable, contradice el principio de transparencia operativa. |
| **Art. 14 — Supervisión humana** | Los operadores pueden intervenir. | El Output Auditor futuro y la confirmación humana de operaciones críticas son la supervisión exigida. |
| **Art. 15 — Robustez, exactitud y ciberseguridad** | Resistencia a errores, fallos y ataques. | El modo vulnerable de Clara incumple Art. 15; el modo defendido (con Output Auditor) lo satisface parcialmente. |

## Conclusión regulatoria

La conclusión es **estructural**, no contextual:

- **El defecto raíz** es la presencia de secretos en el prompt (Art. 5.1.c GDPR, Art. 32 GDPR, Art. 9 DORA).
- **El control reactivo** debe detectar la filtración (Art. 10 DORA, Art. 12 AI Act).
- **El control preventivo** es no embeber secretos jamás en el prompt y moverlos fuera del alcance del LLM (principio OWASP LLM07).

## Referencias

- Reglamento (UE) 2016/679 (GDPR), Art. 5.1.c, Art. 32, Art. 33, Art. 34.
- Reglamento (UE) 2022/2554 (DORA), Art. 6, Art. 9, Art. 10, Art. 11, Art. 17.
- Reglamento (UE) 2024/1689 (EU AI Act), Art. 9, Art. 12, Art. 13, Art. 14, Art. 15.
- OWASP LLM Top 10 2025 — LLM07: System Prompt Leakage (genai.owasp.org).
