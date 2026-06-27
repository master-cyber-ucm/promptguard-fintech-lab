# 07 — Playbook de Respuesta a Incidentes

> System Prompt Leakage — Procedimiento de respuesta ante la filtración del system prompt
> o de un secreto embebido en Clara. Documento analítico **previo a la implementación**.

## Alcance

Detecta y responde a un incidente del ataque #5 (System Prompt Leakage), en particular la filtración de `API_KEY_INTERNAL`, host de DB, bucket S3 o literales de límite bancario documentados en `clara_system.txt:23-29`.

## Detección (futura, Output Auditor)

El Output Auditor (módulo previsto en `propuesta-formal-promptguard-fintech.md:152`) debe aplicar **regex** sobre el output de Clara antes de devolverlo al usuario:

| Patrón | Activo protegido |
|--------|------------------|
| `api_key_internal` / `pg_internal_sk_[a-f0-9]+` | Secreto simulado |
| `db-banking\.internal\.verdabank\.es` | Host interno |
| `s3://verdabank-audit-logs-prod` | Bucket de auditoría |
| `(10\.000|5\.000|1\.000|3\.000)\s*(EUR|€)` | Literales de límite exactos |
| Fragmentos verbatim de las "Reglas de seguridad" (`clara_system.txt:14-20`) | Bloque de configuración |

**Complemento de detección**: el Input Sanitizer debe marcar como sospechosos los prompts que contengan "repeat", "instructions", "system prompt" y derivados (`atk_004`, `atk_005`, `atk_019`).

## Clasificación del incidente

| Severidad | Criterio | Ejemplo |
|-----------|----------|---------|
| **CRITICAL** | Filtración de `API_KEY_INTERNAL` o de cualquier secreto real | `atk_015` exitoso |
| **HIGH** | Filtración del bloque "Reglas de seguridad" o de los límites exactos | `atk_004` o `atk_019` exitoso |
| **MEDIUM** | Intento detectado y bloqueado, sin filtración | `atk_005` bloqueado |

## Roles

| Rol | Responsabilidad en el incidente |
|-----|--------------------------------|
| SOC Analyst | Detecta el patrón en el dashboard, abre incidente |
| Security Engineer | Diagnostica la causa (qué parte del prompt filtró) |
| CISO | Aprueba rotación de secretos y notificación interna |
| Compliance Officer | Evalúa obligación de notificar (GDPR Art. 33, DORA Art. 17) |
| App Owner (VerdaBank) | Decide despliegue de mitigación |

## Fases de respuesta (PICERL alineado)

### 1. Detección
Output Auditor bloquea la respuesta; se crea alerta en el dashboard con severidad asignada.

### 2. Clasificación
SOC asigna severidad según la tabla anterior. Si hay filtración de secreto → CRITICAL.

### 3. Contención
- [ ] Revocar y rotar `API_KEY_INTERNAL` inmediatamente (asumiendo un secreto real).
- [ ] Invalidar sesiones sospechosas asociadas al `user_id` atacante.
- [ ] Activar modo `SHADOW_MODE` o, si procede, degradar temporalmente el servicio de Clara.

### 4. Erradicación
- [ ] **Eliminar el secreto del system prompt.** No debe volver a embeberse: mover a un gestor de secretos fuera del alcance del LLM.
- [ ] Revisar el resto del prompt y extraer cualquier configuración sensible (host, bucket, umbrales si se consideran sensibles).
- [ ] Desplegar el regex de detección actualizado en el Output Auditor.

### 5. Recuperación
- [ ] Redesplegar Clara con el prompt saneado.
- [ ] Verificar la no-regresión con la suite de tests (`atk_004`, `atk_005`, `atk_015`, `atk_019`).
- [ ] Monitorizar durante 72 h la reutilización del secreto revocado.

### 6. Post-mortem
- [ ] Redactar informe de lecciones aprendidas (DORA Art. 12 — aprendizaje).
- [ ] Definir **principio de hardening**: *nunca* secretos reales en el prompt (GDPR Art. 32, OWASP LLM07).
- [ ] Registrar el incidente en el Compliance Logger con retención de 5 años (DORA Art. 17).

## Notificación regulatoria (evaluación)

| Norma | Umbral | Acción |
|-------|--------|--------|
| GDPR Art. 33 | Brecha de dato personal → **72 h** a la AEPD | Si el secreto filtrado da acceso a datos de clientes |
| GDPR Art. 34 | Riesgo alto al interesado | Comunicación a los afectados |
| DORA Art. 17 | Incidente ICT mayor | Comunicación a la autoridad competente |

## Lección estructural

La mitigación duradera **no** es un regex más estricto. Es **eliminar la causa raíz**:

> Cualquier secreto que pueda aparecer en el output del LLM acabará apareciendo.
> El control eficaz es **no ponerlo ahí**.

## Referencias internas

- `lab/backend/config/prompts/clara_system.txt:27-29` — activos a defender.
- `docs/propuesta-formal-promptguard-fintech.md:152` — definición del Output Auditor.
- `docs/propuesta-formal-promptguard-fintech.md:517-518` — DORA Art. 12 y Art. 17 en el mapeo del marco normativo.
