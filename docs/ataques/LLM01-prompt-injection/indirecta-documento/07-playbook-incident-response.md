# 07 — Playbook de Respuesta a Incidentes

> **Ataque #7** — Prompt Injection Indirecta — Documento
> Procedimiento PRE-implementación. Alineado con NIST SP 800-61 y DORA Art. 17.

---

## 1. Roles

| Rol | Responsabilidad en este incidente |
|-----|-----------------------------------|
| **SOC Analyst** | Detección y clasificación inicial; aislamiento de la sesión. |
| **Security Engineer** | Análisis técnico del PDF, del contexto inyectado y de la respuesta del LLM. |
| **DPO / Compliance Officer** | Decisión de notificación GDPR Art. 33/34; contacto con la AEPD. |
| **CISO** | Aprobación de medidas de contención de alto impacto y comunicación interna. |
| **Comms / Atención al cliente** | Comunicación al cliente afectado (Art. 34) si procede. |

---

## 2. Fases del playbook

### 2.1 Detección

- [ ] Alerta del Compliance Logger: ejecución de `consulta_saldo` o `transferencia_nacional` **sin correspondencia** entre el `account_id` consultado y el `user_id` autenticado.
- [ ] Alerta del Output Auditor: la respuesta del LLM contiene un IBAN o saldo **no perteneciente** al usuario autenticado.
- [ ] (Futuro) Alerta del Input Sanitizer extendido al texto extraído del PDF: payload detectado en el documento.
- [ ] Reclamación entrante del cliente afectado (vía humano o por el propio canal).

### 2.2 Clasificación

| Severidad | Criterio | Ejemplo |
|-----------|----------|---------|
| **CRITICAL** | Fuga de PII de terceros o transferencia ejecutada. | Payload consulta saldo ajeno. |
| **HIGH** | Instrucción inyectada detectada sin ejecución de tool. | Payload bloqueado antes de tool call. |
| **MEDIUM** | Documento sospechoso detectado sin impacto en datos. | Payload en metadatos, no procesado. |

### 2.3 Contención

- [ ] Cerrar la sesión del atacante (`session_id`).
- [ ] Bloquear temporalmente el canal de subida de documentos en Clara.
- [ ] Marcar el PDF en cuarentena; preservar copia firmada para evidencia.
- [ ] Revocar tokens de sesión sospechosos asociados al `user_id`.

### 2.4 Erradicación

- [ ] Análisis forense del PDF: localizar el payload (texto blanco, fuente 1pt, metadatos).
- [ ] Auditoría retrospectiva de PDFs subidos en los últimos 30 días con la misma firma.
- [ ] Identificar al cliente afectado por la fuga y alcance real de los datos comprometidos.
- [ ] Confirmar que ningún otro cliente explotó el mismo patrón.

### 2.5 Recuperación

- [ ] Reabrir el canal documental **sólo** tras activar la sanitización sobre el texto extraído (defensa futura, no implementada).
- [ ] Revisar logs del Compliance Logger en busca de ejecuciones de tools derivadas del mismo payload.
- [ ] Comunicar al equipo de producto la validación previa requerida para futuras modificaciones del canal.

### 2.6 Notificación (DPO)

- [ ] Decidir notificación a la AEPD bajo **GDPR Art. 33** (≤ 72 h desde la detección) si hubo fuga de PII.
- [ ] Decidir comunicación al interesado bajo **GDPR Art. 34** si el riesgo es alto.
- [ ] Documentar la decisión (también la de **no** notificar, si aplica).

### 2.7 Post-mortem

- [ ] Redactar informe con timeline, alcance, causa raíz y contramedidas.
- [ ] Actualizar el catálogo de ataques y el sistema de gestión de riesgos (AI Act Art. 9).
- [ ] Añadir el payload a `attack_prompts.jsonl` como fixture de regresión.
- [ ] Reentrenar / afinar los umbrales del Input Sanitizer con el caso detectado.

---

## 3. Métricas de respuesta

| KPI | Objetivo |
|-----|----------|
| Mean Time to Detect (MTTD) | < 1 hora desde el evento |
| Mean Time to Contain (MTTC) | < 4 horas desde la detección |
| Cobertura de auditoría de PDFs retroactivos | 100 % de los últimos 30 días |
| Cumplimiento del plazo GDPR Art. 33 | ≤ 72 h |

---

## 4. Evidencias a preservar

- Sesión completa del atacante (chat + documento subido) con firma HMAC del log.
- PDF original y versión extraída en texto plano por el backend.
- Respuesta del LLM y secuencia de `tool_calls` ejecutadas (`tools.py`).
- Decisión y razón del Output Auditor sobre la respuesta.
