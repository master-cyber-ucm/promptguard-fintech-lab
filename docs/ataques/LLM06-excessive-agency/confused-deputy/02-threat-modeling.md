# 2. Threat Modeling — Confused Deputy Attack

## Actor de amenaza

**Fraude bancario realista.** Estafador con perfil de cliente de banca digital y literacy conversacional. No requiere conocimientos de reversing, redes ni acceso interno. Reutiliza tácticas de ingeniería social habituales en estafas de suplantación bancaria por canal digital.

## Pre-requisitos

- [ ] Sesión autenticada legítima propia (p. ej. `usr_001`).
- [ ] Conocimiento de un IBAN objetivo ajeno (filtrable por otras vías o parcialmente adivinable por el patrón español `ES` + 22 dígitos).
- [ ] Acceso al canal `/chat` de Clara (`lab/backend/src/api/routes/chat.py:45`).
- **NO requiere:** robar credenciales de un tercero, escalar privilegios ni acceso administrativo.

## Explotabilidad

**Alta.** La barrera de entrada es una cuenta propia y un pretexto verbal. No existe control de autorización en las tools: `consulta_saldo` y `transferencia_nacional` aceptan cualquier `account_id` sin compararlo con el `user_id` del contexto (`lab/backend/src/agents/tools.py:44`, `tools.py:71`). El contexto del usuario se inyecta como texto libre en `lab/backend/src/api/routes/chat.py:62-65`, pero ninguna tool lo consume como frontera de permisos.

## Impacto

| Dimensión | Consecuencia |
|-----------|-------------|
| **Confidencialidad** | Saldo y movimientos de cuentas ajenas exfiltrados (titular, IBAN, importes, beneficiarios). |
| **Integridad** | Transferencias SEPA ejecutadas desde cuentas de terceros hacia cuentas controladas por el atacante. |
| **Disponibilidad** | Bajo (no se busca denegar servicio). |
| **Regulatorio** | Brecha de dato personal GDPR; incidente DORA notificable. |

## Score CVSS 3.1 (orientativo)

```
CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N  →  Base 9.6 (Critical)
```

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Attack Vector | Network (AV:N) | Vía `/chat`, canal web/app de VerdaBank. |
| Attack Complexity | Low (AC:L) | Sin token especial; solo pretexto textual. |
| Privileges Required | Low (PR:L) | El atacante **usa su propia sesión**; no escala privilegios. Es la marca definitoria del confused deputy. |
| User Interaction | None (UI:N) | No requiere acción de la víctima ni del operador. |
| Scope | Changed (S:C) | El impacto salta de la cuenta del atacante a la cuenta del tercero. |
| Confidentiality | High (C:H) | Saldo y movimientos financieros de terceros. |
| Integrity | High (I:H) | Transferencias fraudulentas desde cuentas ajenas. |
| Availability | None (A:N) | No interrumpe el servicio. |

El **Scope Changed** refleja con precisión la naturaleza del confused deputy: el agente actúa con un privilegio que no pertenece a la identidad que origina la petición, extendiendo el impacto a un dominio de recurso ajeno.
