"""SOC — capa de observabilidad del proxy PromptGuard.

El proxy detecta y detiene; el SOC solo mira. Ningún módulo de este paquete
decide nada sobre una petición: capturan lo que los componentes de defensa ya
decidieron y lo hacen consultable.

Diseño completo en `docs/soc/README.md`.
"""
