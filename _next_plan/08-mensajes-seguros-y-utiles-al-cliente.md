# Sustituir marcadores técnicos por respuestas seguras y útiles

## Descripción del problema

El cliente puede recibir el literal `[BLOCKED_BY_INPUT_SANITIZER] Patrón de inyección detectado.`. Expone detalles internos, no explica una vía legítima y convierte un control de seguridad en una mala experiencia de usuario.

## Evidencia observada

El marcador aparece como respuesta final en [`leg_021`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_233901_ses_783104617691_1788046741.md). En ese caso además revela que el bloqueo fue erróneo, pero el problema de UX existe incluso cuando el bloqueo es correcto.

## Explicación técnica

La capa de entrada retorna una decisión técnica y la ruta HTTP la convierte directamente en respuesta visible. Se mezclan tres contratos: motivo interno, evento SOC y texto para cliente.

## Alternativas de mejora

### A. Catálogo de respuestas por categoría y acción (recomendada)

Mantener el motivo exacto sólo en auditoría; devolver al cliente una respuesta neutra con alternativa segura. Ejemplo para saldo: “Puedo ayudarte a consultar el saldo de tu cuenta. ¿Quieres verlo ahora o prefieres los pasos en la app?”

### B. Un único rechazo genérico

Oculta reglas pero no guía al usuario ni reduce abandonos.

## Solución propuesta

Crear un adaptador `Decision -> ClientResponse` con mensajes revisados por producto, localizables y sin nombre de regla. Para `SUSPICIOUS`, preferir pedir aclaración o continuar con controles de backend.

## Pruebas de aceptación

1. Ningún texto visible contiene nombres de componentes, reglas o patrones.
2. Cada bloqueo tiene una alternativa segura cuando aplica.
3. El motivo técnico queda disponible en SOC y Session File estructurado.

## Implementación realizada — 2026-08-30

Se añadió `core/client_messages.py`, un catálogo de mensajes cliente por tipo de
control. Las rutas de bloqueo de Input Sanitizer, PII Shield, Rate Limiter,
Budget Guard y los controles de documento lo usan ahora como adaptador entre la
decisión técnica y la respuesta HTTP.

### Contrato de respuesta

Ante un bloqueo controlado, la API devuelve:

- `response`: mensaje seguro, útil y sin regla, patrón ni nombre del componente;
- `error: null`: reservado para fallos técnicos reales;
- `block_code: "REQUEST_NOT_PROCESSED"`: señal estable y neutra para clientes y
  el runner, sin revelar qué defensa intervino.

El runner de la suite consume `block_code` para seguir contando el bloqueo como
tal, sin depender de los antiguos literales `BLOCKED_BY_*`.

### Auditoría y SOC

El motivo técnico sigue preservándose en el Session File v2 como
`model_output_raw` y en `defense_decisions` (componente, acción, regla y razón).
El SOC conserva la decisión original ya emitida por cada capa. Por ello el
cliente no recibe detalles explotables, pero el equipo puede investigar la causa
exacta.

## Estado del fix

**Estado: implementado y validado.**

- Las pruebas verifican que los mensajes visibles no contienen `input_sanitizer`,
  `pii_shield`, reglas ni patrones, y que ofrecen una alternativa segura.
- Los Session Files de bloqueos conservan `BLOCKED_BY_*` sólo como evidencia
  interna protegida.
- Suite completa del backend: **252 tests aprobados**; `py_compile` y
  `git diff --check` sin errores.
