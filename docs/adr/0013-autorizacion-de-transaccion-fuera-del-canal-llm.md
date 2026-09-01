# Autorización de transacción fuera del canal LLM

Estado: **propuesto**.

Una operación financiera sensible solo podrá autorizarse en una superficie autenticada separada del canal conversacional, mostrando y vinculando la operación, origen, beneficiario, importe, moneda y caducidad exactos. El LLM no verá ni transportará el challenge o la credencial de aprobación.

## Considered Options

- Pedir al usuario un token dentro del chat: es sencillo, pero prompt, transcript y modelo pasan a controlar el mismo factor que debe limitar su autoridad.
- Confirmar solo un `operation_id`: evita exponer secretos al modelo, pero permite autorizar una operación cuyos detalles cambiaron o no fueron mostrados.
- Autorizar el digest de detalles canónicos fuera del chat (elegida): añade workflow y estado, pero ofrece WYSIWYS, resistencia a replay y separación real de actores.

## Consequences

- Propuesta, aprobación y commit tendrán estados, evidencias e idempotencia independientes.
- El lab necesitará un actor de aprobación de test con credencial separada.
- Cualquier cambio de detalles después de aprobar invalida la autorización.
