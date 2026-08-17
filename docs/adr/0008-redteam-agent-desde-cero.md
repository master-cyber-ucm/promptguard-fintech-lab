# Agente de red-team construido desde cero, no sobre FuzzyAI/Garak

El Agente de red-team (`lab/redteam-agent/`) se implementa como módulo propio sobre Ollama, sin depender de un fuzzer LLM existente. `FuzzyAI` (CyberArk) está clonado en el repo padre y ya sabe hablar con Ollama y mutar jailbreaks iterativamente; la pregunta de scope de Garak sigue abierta en `TODOs.md` §8. Un lector futuro que vea ambas herramientas sin usar junto a un agente propio recién construido preguntará por qué no se reutilizó ninguna.

La razón no es técnica: el propósito declarado de esta épica es el aprendizaje de diseñar el propio bucle generar→atacar→leer→adaptar contra el marco de defensa del lab, no producir el mayor número de bypasses en el menor tiempo. Montar el agente sobre FuzzyAI habría resuelto el problema más rápido pero habría delegado justo la parte que se quiere construir. FuzzyAI y la pregunta de Garak quedan como referencia de diseño y como opción a evaluar por separado, sin bloquear ni compartir código con este módulo.

## Considered Options

- **FuzzyAI como motor, lab como target** (rápida, resuelve además la duda pendiente sobre Garak/FuzzyAI) — descartada porque desplaza el aprendizaje buscado a configurar una herramienta ajena.
- **Híbrido: harness/taxonomía propios, mutación delegada a una librería** — descartada por la misma razón: la generación de mutaciones es precisamente donde vive el "pensamiento lateral" que se quiere diseñar, no un detalle de bajo nivel a delegar.
- **Construir desde cero (elegida)**: más trabajo y sin las estrategias de mutación ya maduras de FuzzyAI, pero el diseño del bucle, del harness de taxonomía y del motor de evolución es el propio entregable de aprendizaje.
