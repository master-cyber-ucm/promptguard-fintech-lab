# 7. Playbook de Respuesta a Incidentes — Confused Deputy Attack

## Detección

- **Señal primaria:** en los logs del Compliance Logger, `tool_call` sobre un `account_id` distinto del `account_id` del `user_id` autenticado. El contexto del usuario se construye en `lab/backend/src/api/routes/chat.py:62`; cruzar ese `account_id` contra el `account_id` de cada tool en `lab/backend/src/agents/tools.py:44` y `tools.py:71`.
- **Señales secundarias:**
  - Atribución de identidad distinta en el prompt ("soy el admin", "he entrado como…").
  - Presión temporal explícita ("urgente", "no hay tiempo", "hackeada").
  - Coincidencia del `to_account` con el `account_id` del propio `user_id` autenticado (destino = beneficiario real del atacante).
- [ ] Alerta SIEM por divergencia `user_id` ↔ `account_id` en cualquier tool call.

## Clasificación

| Campo | Valor |
|-------|-------|
| Tipo | Confused Deputy / Excessive Agency (variante delegación) |
| Severidad | CRITICAL |
| Categoría de impacto | Confidencialidad + Integridad |
| Notificable | GDPR Art. 33/34 · DORA Art. 17 |

## Contención

1. [ ] Suspender la sesión del `user_id` implicado en el `/chat`.
2. [ ] Bloquear `transferencia_nacional` y `consulta_saldo` (modo *shadow*) para ese usuario.
3. [ ] Revertir transferencias tentativas aún no liquidadas dentro de la ventana SEPA.
4. [ ] Poner en cuarentena los IBAN objetivo (`ES58…35`, `ES34…34`) como víctimas.

## Erradicación

- [ ] Confirmar que no hay otras sesiones activas reutilizando el mismo patrón.
- [ ] Auditar logs de las últimas 72 h buscando divergencia `user_id` ↔ `account_id` en cualquier tool.
- [ ] Identificar el canal de fuga del IBAN objetivo (cómo obtuvo María el IBAN de `usr_admin`/`usr_003`).

## Recuperación

- [ ] Reembolsar el importe revertido a las cuentas afectadas.
- [ ] Notificar a los titulares afectados (GDPR Art. 34).
- [ ] Notificación a la AEPD en ≤72 h (GDPR Art. 33) y reporte DORA Art. 17 si aplica.
- [ ] Reapertura del canal `/chat` con monitoreo reforzado.

## Post-mortem y hardening

| Hallazgo | Hardening (defensa futura, fuera del alcance del lab) |
|---------|-----------------------------------------------------|
| Las tools no consultan el `user_id` autenticado | **Tool Gatekeeper** con `require_own_account: true`: toda tool con `account_id` valida que pertenezca al `user_id` del contexto. |
| El `user_context` es texto libre para el LLM | Inyectar el `account_id` autorizado como parámetro implícito del agente, no como texto interpretable. |
| Ausencia de confirmación humana en transferencias | Umbral monetario + *human-in-the-loop* (EU AI Act Art. 14). |
| Trazabilidad débil | Log determinista `tool · user_id · account_id · decisión` en el Compliance Logger. |

## Roles

| Rol | Responsabilidad |
|-----|----------------|
| SOC Analyst | Detección de la divergencia `user_id` ↔ `account_id` y clasificación inicial. |
| Compliance Officer | Notificación AEPD (GDPR Art. 33/34) y reporte DORA (Art. 17). |
| Security Engineer | Hardening del Tool Gatekeeper (`require_own_account`). |
| CISO | Aprobación de medidas y comunicación interna. |
| Operaciones | Reversión de transferencias y atención al titular afectado. |
