# Propuesta del modelo separada del commit de dominio

Estado: **aceptado**. El `ActionProposal`/`CommitLedger` ya existían; PR 2 cierra el
único camino que quedaba abierto — el atajo `Effect.ALLOW -> _commit()` directo en
`transferencia_nacional` — para que ningún estado financiero llegue a
`STATE_COMMITTED` sin pasar por `transaction_authorization` (ver
[PR 2](../reports/pr-02-autorizacion-operaciones-financieras.md)).

Las tools de escritura dejarán de otorgar al modelo una vía directa al efecto. El modelo producirá una `Action Proposal`; validación de procedencia, Policy Decision, Transaction Authorization cuando corresponda y un command service idempotente serán los únicos pasos capaces de producir un Effect Receipt.

## Considered Options

- Mantener tools que ejecutan y confiar en el Output Auditor: conserva baja latencia, pero el auditor llega después del efecto y solo puede modificar texto.
- Añadir checks dentro de cada wrapper: mejora casos conocidos, pero duplica policy y hace fácil que una tool futura omita el control.
- Separar propuesta, autorización y command service (elegida): introduce más estados, pero concentra el punto de commit y hace auditable la autoridad efectiva.

## Consequences

- Las queries autorizadas pueden seguir ejecutándose directamente; la separación estricta aplica a commands.
- Todos los writes necesitan operation ID, idempotency key y recibo emitido por dominio.
- Las defensas de salida solo recibirán crédito por contener entrega textual, nunca un efecto anterior.
