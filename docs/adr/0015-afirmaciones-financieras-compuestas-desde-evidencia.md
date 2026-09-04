# Afirmaciones financieras compuestas desde evidencia

Estado: **propuesto**.

Saldos, titulares, movimientos, estados de tarjeta y resultados de operaciones se entregarán como Financial Claims compuestos por backend desde facts autorizados y vigentes. El modelo podrá interpretar intención y aportar lenguaje no factual, pero no inventar ni alterar los valores de alto impacto.

## Considered Options

- Permitir texto libre y detectar errores después: maximiza flexibilidad, pero una segunda clasificación probabilística no garantiza soporte, autorización ni consistencia.
- Redactar cualquier respuesta con números: reduce exposición, pero destruye utilidad legítima.
- Componer slots protegidos desde evidencia y permitir lenguaje alrededor (elegida): exige contratos y templates, pero mantiene utilidad sin delegar hechos al modelo.

## Consequences

- Los servicios de lectura emitirán Financial Facts con evidencia, audiencia y `as_of`.
- El Safe Response Composer tratará datos de alto impacto como slots inmutables.
- Evidencia ausente, obsoleta o conflictiva producirá un fallback útil y una clase de error explícita, no una afirmación aproximada.
