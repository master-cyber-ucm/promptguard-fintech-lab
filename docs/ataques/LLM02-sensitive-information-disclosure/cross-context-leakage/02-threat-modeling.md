# 02 — Threat Modeling

> Cross-Context Data Leakage (#3). Modelo de amenaza, explotabilidad e impacto.

## 1. Actor de amenaza

| Atributo | Valor |
|----------|-------|
| Perfil | **Cliente bancario autenticado** (rol `customer`). |
| Motivación principal | **Fraude financiero**: conocer el saldo de una víctima para diseñar estafa o transferencia. |
| Motivación secundaria | **Curiosidad / espionaje**: verificar el saldo de un conocido, pareja o competidor. |
| Conocimiento técnico | Bajo-medio: no requiere exploits, solo redacción de prompts. |
| Acceso interno | **Ninguno**: opera desde fuera, con su sesión legítima. |

## 2. Pre-requisitos

- [x] Sesión autenticada válida en Clara (`POST /chat` con `user_id`).
- [x] **Conocimiento de un `account_id` (IBAN) ajeno**, obtenible por:
  - filtrado previo por otro canal del banco,
  - ingeniería social / phishing al titular,
  - o **pidiéndoselo al propio LLM** en turnos anteriores (encadenamiento con PII Harvesting #6).
- [x] `consulta_saldo` accesible al agente en la sesión (`lab/backend/src/agents/tools.py:44`).

No se requieren credenciales ajenas, acceso a red interna ni herramientas especiales.

## 3. Explotabilidad

**Alta.** Barrera de entrada muy baja: un único turno de conversación. La tool `consulta_saldo` no comprueba que `account_id` pertenezca a `user_id` (`tools.py:44-68`). El contexto del usuario se inyecta como texto en `lab/backend/src/api/routes/chat.py:62-65`, pero el LLM puede invocar la tool con cualquier IBAN presente en el mensaje.

## 4. STRIDE

| Categoría | Aplica | Nota |
|-----------|:------:|------|
| Information Disclosure | **Sí (principal)** | Filtrado de saldo/IBAN de un tercero. |
| Elevation of Privilege | **Sí (horizontal)** | Acceso a datos de un par (otro cliente). |
| Repudiation | Parcial | Si el logging es incompleto, el atacante puede negar intención. |
| Spoofing / Tampering / DoS | No | No son el objetivo del ataque. |

## 5. Impacto

- **Activo comprometido**: saldo e IBAN de cuentas ajenas (dato financiero de carácter personal).
- **Víctima**: otro cliente del banco (ej. `usr_003` Ana — 231.500 €; `usr_admin` — 999.999,99 €, ver `lab/backend/src/models/banking.py:87-100`).
- **Regulatorio**: **GDPR Art. 33** — notificación a la AEPD en **≤72 h** desde la toma de conocimiento.
- **Reputacional/financiero**: pérdida de confianza, reclamaciones y posibles sanciones.

## 6. CVSS 3.1 orientativo

**Vector:** `CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:N`
**Base score: 7.4 — Alto**

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Attack Vector | Network | Clara se alcanza por la API web/app. |
| Attack Complexity | Low | Un mensaje de texto; sin bypass técnico. |
| Privileges Required | Low | Cliente autenticado (no anónimo). |
| User Interaction | None | Sin interacción de la víctima. |
| Scope | **Changed** | El impacto cruza la frontera de autorización: dato de **otra** identidad. |
| Confidentiality | **High** | Saldo e IBAN completos del tercero expuestos. |
| Integrity / Availability | None | No se alteran ni interrumpen datos o servicio. |

La métrica decisiva es **Confidentiality: High** combinada con **Scope: Changed**, que refleja la naturaleza *cross-tenant* de la fuga.
