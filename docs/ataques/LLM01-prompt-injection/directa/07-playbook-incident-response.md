# Playbook de Respuesta a Incidentes — Prompt Injection Directa

> Ataque #2 del catálogo · Plantilla operativa para el LLM-SOC de VerdaBank

Este documento es una **plantilla de respuesta** (no implementación). Define el ciclo de vida de un incidente originado por inyección directa contra Clara. Cumple DORA Art. 11 (respuesta y recuperación).

---

## 1. Detección

| Fuente | Señal | Latencia objetivo |
|--------|-------|-------------------|
| Compliance Logger | Mensaje que activa firma regex (`injection_signatures.yaml`) | <5 s |
| Output Auditor | Respuesta de Clara contiene IBAN/saldo no pertenecientes al `user_id` autenticado | <5 s |
| Dashboard LLM-SOC | Pico de decisiones BLOCK/SUSPICIOUS en una sesión | tiempo real |

**Disparador de incidente:** un evento ALLOW seguido de output con dato ajeno (señal de bypass de la defensa) o, en modo vulnerable, cualquier `consulta_saldo` cuyo `account_id` no coincida con las cuentas del `user_id`.

## 2. Clasificación (severidad)

| Severidad | Criterio | Ejemplo |
|-----------|----------|---------|
| **CRITICAL** | Inyección con éxito + filtrado de dato financiero de tercero | Saldo de cuenta admin devuelto a usr_001 |
| **HIGH** | Inyección con éxito sin filtrado (override de rol confirmado) | Clara acepta rol sin restricciones pero el atacante no extrae dato |
| **MEDIUM** | Intento bloqueado por Input Sanitizer, patrón recurrente | 3+ `atk_001` bloqueados en la misma sesión (posible sondeo) |
| **LOW** | Intento aislado bloqueado | Un único `atk_002` bloqueado sin reincidencia |

La clasificación determina el canal de escalamiento y el reloj de notificación GDPR (Art. 33).

## 3. Contención

- [ ] Bloquear la sesión activa del `user_id` sospechoso (invalidar `session_id`).
- [ ] Activar modo "sombra" en el Input Sanitizer para la cuenta/usuario (detectar sin responder) si se desea recoger evidencia.
- [ ] Desactivar temporalmente las tools de alto riesgo (`transferencia_nacional`, `bloquear_tarjeta`) para el `user_id`.
- [ ] Forzar reautenticación del canal conversacional.

## 4. Erradicación

- [ ] Confirmar que el vector (mensaje directo al LLM) ya no es explotable: verificar que el Input Sanitizer está activo y bloquea el payload reproducido.
- [ ] Revisar el contexto de sesión del `user_id` para descartar inyecciones persistentes (payloads previos que sigan activos en la ventana de contexto).
- [ ] Rotar cualquier secreto expuesto si el atacante alcanzó a solicitarlo (ej. `API_KEY_INTERNAL` referenciado en `clara_system.txt:27`).

## 5. Recuperación

- [ ] Restablecer el servicio de Clara para el `user_id` afectado con normalidad.
- [ ] Confirmar que el titular de la cuenta comprometida (`usr_admin` en este escenario) no ha sufrido operaciones no autorizadas.
- [ ] Reabrir el canal conversacional al público tras validar que la defensa bloquea el payload reproducido.

## 6. Post-mortem (lecciones + hardening)

- [ ] Documentar el payload exacto, la capa de defensa que falló y el tiempo de detección.
- [ ] Añadir el payload a la regresión de tests del Input Sanitizer.
- [ ] Si el bypass fue por regex, añadir la firma o reforzar el clasificador ML.
- [ ] Actualizar el umbral de sondeo en el Attack Pattern Detector si procede.
- [ ] Revisar la revisión del system prompt: si la inyección reveló información interna, evaluar reducir lo expuesto en `clara_system.txt`.

## 7. Roles y responsabilidades

| Rol | Responsabilidad en el incidente |
|-----|--------------------------------|
| **SOC Analyst** | Detección, clasificación inicial, ejecución de contención. |
| **Security Engineer** | Erradicación técnica, reproducción del payload, hardening del Input Sanitizer. |
| **CISO** | Aprobación de escalamiento, decisión de activar protocolo de brecha, comunicación ejecutiva. |
| **DPO (Data Protection Officer)** | Evaluación GDPR, decisión de notificación AEPD (Art. 33) y comunicación al interesado (Art. 34), gestión del reloj de 72 h. |

## 8. Métricas del incidente

| KPI | Target |
|-----|--------|
| Mean Time to Detect (MTTD) | <5 min |
| Mean Time to Contain (MTTC) | <30 min |
| Notificación AEPD (si aplica) | ≤72 h desde el conocimiento |
| Cobertura de logs del incidente | 100% de turnos firmados |

> Este playbook es artefacto documental del TFM. La implementación concreta de cada control (Input Sanitizer, Output Auditor, Compliance Logger) se desarrolla en las fases de defensa del laboratorio, no en este documento.
