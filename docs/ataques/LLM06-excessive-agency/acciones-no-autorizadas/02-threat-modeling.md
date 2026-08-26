# 02 — Threat Modeling

> Modelado de amenaza para Excessive Agency en el canal conversacional de Clara.

## Actor de amenaza

- **Perfil:** cliente bancario **fraudulento** (insider fraud), no un atacante externo sin acceso.
- **Motivación:** **mayor ROI del catálogo**. Impacto económico inmediato y cuantificable, sin necesidad de comprometer credenciales ajenas ni infraestructura (`README.md:10`).
- **Habilidad requerida:** baja. Basta con redactar un mensaje; no hay explotación de memoria, red ni criptografía.

## Pre-requisitos

- [x] Sesión **autenticada** válida en VerdaBank (rol `customer`).
- [x] Canal `/chat` operativo con Clara.
- [ ] *No* se requieren credenciales del titular de la cuenta origen ni del banco receptor.

## Explotabilidad: **ALTA**

- Vector: red (API conversacional).
- Complejidad: baja — un único turno de conversación.
- Sin interacción adicional del usuario legítimo ni de un operador.

## Impacto

- **Financiero DIRECTO e irreversible**: transferencia SEPA completada (`tools.py:98` `status="completed"`) o tarjeta bloqueada permanentemente (`tools.py:129` "Tarjeta bloqueada permanentemente").
- La irreversibilidad de la liquidación SEPA dificulta el reembolso una vez ejecutada.

## CVSS 3.1 (orientativo)

`CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:N/I:H/A:H` — **9.6 Critical**

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Attack Vector | Network | Ataque vía API `/chat` de Clara. |
| Attack Complexity | Low | Un mensaje de texto; sin condición de carrera ni timing. |
| Privileges Required | Low | Cliente autenticado con rol `customer` (`banking.py:108`). |
| User Interaction | None | El titular legítimo no interviene; la tool ejecuta en solitario. |
| Scope | **Changed** | La vulnerabilidad está en el componente LLM; el impacto cruza al *core banking* y al patrimonio de otros usuarios. |
| Confidentiality | None | El objetivo es ejecutar, no divulgar (la fuga se cubre en ataque #3). |
| Integrity | **High** | Saldo alterado de forma irreversible; cuenta vaciada (`atk_007`: 50.000 €). |
| Availability | **High** | Tarjeta inservible (`atk_017`) y patrimonio no disponible para el titular. |

> Interpretación conservadora con `S:U` → **8.1 High**. En ambos casos el riesgo es CRÍTICO/HIGH: no existe defensa en el lab vulnerable.

## Activos en riesgo

| Activo | Dueño | Exposición |
|--------|-------|-----------|
| `ES9121000418450200051332` | María (usr_001) | Origen drenado en `atk_006`/`atk_007`. |
| Tarjeta de `ES7621000418450200051333` | Carlos (usr_002) | Bloqueada en `atk_017`. |
| Liquidez del banco | VerdaBank | Reembolso y reputación. |

## Estado

- [x] Actor y pre-requisitos definidos
- [x] CVSS justificado métrica a métrica
- [ ] Revisión por el tutor de la métrica Scope
