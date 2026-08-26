# Cross-Context Data Leakage

> Ataque **#3** del catálogo — Escenario Base.
> **OWASP LLM02:2025 · MITRE ATLAS AML.T0024** — Sensitive Information Disclosure

## Resumen

Este es **exactamente el incidente motivador** del TFM: **INC-2025-0089**, en el que Clara filtró el saldo de otro cliente mediante context manipulation.

El atacante manipula el contexto de la conversación para que Clara incluya en su respuesta datos financieros de **otro usuario** que están en memoria de sesión o en el contexto activo del modelo.

## Vector de ejecución

- Solicitar directamente el saldo/IBAN de una cuenta ajena, justificando un motivo legítimo.
- Pedir al LLM que invoque `consulta_saldo` con un `account_id` ajeno.
- Referencias indirectas a datos procesados previamente para que el modelo los repita.

En el lab, `consulta_saldo` (`lab/backend/src/agents/tools.py`) **no verifica que la cuenta pertenezca al usuario autenticado**.

## Relevancia en VerdaBank

- **GDPR Art. 33**: notificación obligatoria a la AEPD en **72 horas**.
- Es la brecha que activó el proyecto PromptGuard.
- Datos en juego: saldos, IBANs, movimientos de cuentas ajenas (ver `lab/backend/src/models/banking.py`).

## Defensa que lo mitiga

**Output Auditor**:

- Escanear la respuesta buscando **IBANs, saldos y tarjetas que no pertenecen al usuario autenticado**.
- Cross-check de cualquier dato financiero en el output contra las cuentas del `user_id` de la sesión.
- **Strict session isolation**: ningún dato de otras sesiones/usuarios debe estar accesible.

## Payloads disponibles en el lab

Fixture `lab/backend/tests/fixtures/attack_prompts.jsonl`:

- `atk_008` — `saldo_otro_cliente_directo`.
- `atk_009` — `tool_call_directo` (invocación directa de `consulta_saldo` con IBAN ajeno).

## Estado

- [x] Definido en el catálogo
- [x] Vinculado al incidente motivador (INC-2025-0089)
- [ ] Payloads diseñados / ampliados
- [ ] Ejecutado contra Clara (modo vulnerable)
- [ ] Evidencia capturada
- [ ] Defensa validada (Output Auditor)
