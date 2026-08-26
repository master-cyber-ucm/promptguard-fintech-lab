# Verdict calculado desde los indicadores del fixture, no desde lógica centralizada

El Suite Run determina si un ataque tuvo éxito comparando la respuesta de Clara contra las listas `indicators.success` e `indicators.blocked` definidas en el propio YAML del fixture, en lugar de usar keywords hardcodeadas en el script.

La lógica centralizada anterior tenía IBANs y palabras clave fijos en `run_attack_suite.py`. Cada nuevo fixture requería editar el script, y los indicadores no reflejaban las particularidades de cada variante de ataque. Mover los indicadores al fixture hace que cada caso de prueba sea autónomo: define qué constituye éxito o fracaso para sí mismo, y el script solo evalúa.

## Considered Options

- **Keywords hardcodeados en el script**: más simple inicialmente, pero no escala y desincroniza la definición del ataque de sus criterios de evaluación.
- **Indicadores por fixture (elegida)**: cada YAML es la fuente de verdad para su propio Verdict. Añadir un fixture nuevo no requiere tocar el script.
