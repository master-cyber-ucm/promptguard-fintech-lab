"""SOC — capa de observabilidad del proxy PromptGuard.

El proxy detecta y detiene; el SOC solo mira. Ningún módulo de este paquete
decide nada sobre una petición: capturan lo que los componentes de defensa ya
decidieron y lo hacen consultable.

Diseño completo en `docs/soc/README.md`. Decisión de persistencia en
`docs/adr/0007-dos-almacenes-para-la-traza-de-un-turno.md`.
"""
