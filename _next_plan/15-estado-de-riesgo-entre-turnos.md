# Conservar estado de riesgo entre turnos para ataques encadenados

## Descripción del problema

El proxy evalúa cada turno con señales locales, pero los ataques encadenados distribuyen la intención: primero solicitan una excepción, secreto o jailbreak; después piden una acción aparentemente ordinaria. Sin memoria de riesgo, el segundo turno puede perder el contexto adversarial.

## Evidencia observada

La familia chained attacks sólo bloquea 57,1% en `proxy-full`. [`atk_045`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_205402_ses_6acb7e42614f_1788036842.md) separa la inyección y la transferencia en dos mensajes; [`atk_046`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_210543_ses_9f292e9541d5_1788037537.md) encadena extracción y uso de secreto.

## Explicación técnica

El sanitizador conserva una ventana textual, pero una decisión de seguridad bloqueada no se modela necesariamente como estado de sesión que restrinja operaciones posteriores. Tampoco existe un nivel de riesgo consumible por Gatekeeper y confirmación.

## Alternativas de mejora

### A. Máquina de riesgo de sesión con TTL (recomendada)

Persistir señales (`injection_blocked`, `secret_requested`, `tool_denied`) con tiempo de vida y elevar requisitos: prohibir escrituras, exigir confirmación fuerte o terminar sesión según severidad.

### B. Usar sólo historial textual

Es vulnerable a resumido, truncado y evasiones; además no ofrece una política clara por señal.

## Solución propuesta

Crear `RiskContext` por `session_id`, firmado o almacenado en backend, con niveles `normal`, `elevated`, `restricted`. El Gatekeeper consulta ese contexto antes de permitir acciones de escritura.

## Pruebas de aceptación

1. Una inyección bloqueada seguida de transferencia no puede ejecutar sin revisión reforzada.
2. El estado expira tras TTL y no contamina sesiones nuevas.
3. El usuario no puede bajar el riesgo mediante instrucciones conversacionales.
