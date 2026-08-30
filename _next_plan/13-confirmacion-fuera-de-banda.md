# Confirmación fuera de banda sin exponer secretos en el chat

## Descripción del problema

El flujo de `pending_confirmation` evita ejecutar la transferencia, pero devuelve `confirm_token` dentro de la conversación. Un segundo factor que el propio canal conversacional puede revelar o reutilizar no ofrece una separación real de canales.

## Evidencia observada

En [`atk_006_transfer_ajena`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_182419_ses_a653c278f005_1788027836.md), la respuesta incluye un `confirm_token` y una ruta para confirmar, aunque la operación queda pendiente.

## Explicación técnica

El backend crea la operación y token, y el modelo lo incorpora a su respuesta. El atacante controla el texto que induce esa llamada y puede intentar extraer/reutilizar el token desde el mismo canal. La confirmación debe estar vinculada a usuario, dispositivo, operación y expiración, pero no ser transportada por el LLM.

## Alternativas de mejora

### A. Push/app/SMS transaccional (recomendada)

Enviar una notificación a un dispositivo/canal previamente vinculado. El chat recibe sólo un identificador no secreto y el estado “pendiente de aprobación”.

### B. Código en el chat

Es adecuado sólo para demostración local; no constituye segundo factor real.

## Solución propuesta

Crear una aprobación firmada, de un solo uso y ligada a hash de la operación; entregar el desafío al canal externo. La API de confirmación debe requerir sesión autenticada y prueba del dispositivo, nunca sólo un token expuesto en el texto.

## Pruebas de aceptación

1. La respuesta del chat no contiene token, OTP ni enlace autenticador.
2. Un token capturado por chat no confirma ninguna operación.
3. La aprobación expira y no puede reutilizarse ni cambiar importe/destino.
