# Identidad derivada del Principal autenticado

Estado: **propuesto**.

Toda autoridad de usuario se derivará de un `Principal` creado por la frontera de autenticación a partir de una credencial verificada. El body, el prompt, el identificador de sesión y los argumentos de una Tool no podrán seleccionar sujeto ni tenant. Los servicios de dominio aplicarán autorización con ese Principal, incluso cuando la llamada no pase por el agente.

## Considered Options

- Mantener `user_id` en los DTOs y comprobarlo dentro de algunas tools: preserva compatibilidad, pero deja rutas, servicios internos y nuevas tools expuestos a BOLA.
- Firmar el `user_id` enviado por el cliente: reduce manipulación, pero sigue mezclando identidad de transporte con datos de dominio y facilita APIs que omiten la verificación.
- Inyectar un Principal server-side y exigirlo en repositorios/servicios (elegida): requiere migrar DTOs y tests, pero convierte la frontera de confianza en una propiedad estructural.

## Consequences

- Producción validará tokens del issuer configurado; el lab usará un issuer firmado de test, no identidad dentro del prompt.
- Las sesiones, policies, operaciones y recibos quedarán ligados a subject y tenant.
- Las APIs administrativas usarán scopes y rutas explícitas, no un `user_id` alternativo.
