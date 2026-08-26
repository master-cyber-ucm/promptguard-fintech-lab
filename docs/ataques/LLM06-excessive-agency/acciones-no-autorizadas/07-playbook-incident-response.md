# 07 — Playbook de Respuesta a Incidentes

> Énfasis: la transferencia SEPA completada es **irreversible**. La contención no es un *rollback*; es una **recuperación cooperativa**.

## Clasificación

- **Severidad:** **CRITICAL** (pérdida financiera directa, incidente grave ICT — DORA Art. 17).
- **Categoría:** Fraude por abuso de agency en canal IA.
- **Activa confirmación humana (24/7):** sí.

## Fases

### 1. Detección
- Alerta del Compliance Logger ante tool call `transferencia_nacional` con `status: completed` fuera de horario o sobre umbral.
- Disparador secundario: conciliación de saldos / monitor de descubiertos en el core bancario.
- Indicador en el dashboard LLM-SOC (`propuesta-formal-promptguard-fintech.md:433`): alerta CRITICAL en cola.

### 2. Clasificación
- Triage en **CRITICAL financiero** en <5 min (MTTA target).
- Asignar a SOC Analyst + Compliance Officer de guardia.

### 3. Contención
- [ ] **Congelar** la cuenta origen y bloquear nuevas tool calls de la sesión.
- [ ] **Contacto inmediato al banco receptor** para retener el importe antes de la liquidación SEPA.
- [ ] Revocar el token de sesión del atacante (`usr_001`).

### 4. Erradicación
- [ ] Parchear la lógica de las tools (`tools.py:71`, `tools.py:118`) para exigir validación determinista.
- [ ] Activar `tool_permissions.yaml` en el Tool Gatekeeper (defensa futura).
- [ ] Forzar confirmación humana sobre umbral (EU AI Act Art. 14).

### 5. Recuperación
- [ ] Iniciar **devolución SEPA** (no *rollback* técnico) con el banco receptor.
- [ ] **Reembolso** al titular perjudicado si la devolución falla; provisionar el pasivo.
- [ ] Reemitir la tarjeta de Carlos (`usr_002`) bloqueada en `atk_017`.

### 6. Notificación regulatoria
- [ ] DORA Art. 17 — reporte de incidente grave ICT.
- [ ] GDPR Art. 33 — notificación AEPD en **72 h**.
- [ ] GDPR Art. 34 — comunicación al titular afectado.

### 7. Post-mortem
- [ ] Transcripción firmada de la sesión (Compliance Logger).
- [ ] Análisis de causa raíz: ausencia de gate entre LLM y tool.
- [ ] Actualización del catálogo de riesgos y de `tool_permissions.yaml`.
- [ ] Ejercicio de lecciones aprendidas con SOC y Compliance.

## Roles y responsabilidades

| Rol | Responsabilidad en el incidente |
|-----|--------------------------------|
| SOC Analyst | Detección, triage, contención inicial. |
| Security Engineer | Erradicación técnica, activación del gatekeeper. |
| Compliance Officer | Notificación DORA Art. 17 / GDPR Art. 33-34. |
| Operaciones / Tesorería | Devolución SEPA y reembolso al titular. |
| CISO | Decisión de escalado y comunicación interna. |

## Estado

- [x] Playbook con énfasis en irreversibilidad SEPA
- [x] Roles asignados
- [ ] Simulacro (tabletop) del playbook (trabajo futuro)
