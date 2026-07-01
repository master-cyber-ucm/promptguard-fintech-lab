# Separación entre Suite Run y Analyze Pass

El cálculo de Verdicts y la invocación del juez LLM se separan del envío de fixtures al backend en dos comandos distintos: `suite` (envío + log) y `analyze` (evaluación + reporte).

El script original combinaba las dos responsabilidades: enviaba cada fixture, calculaba el Verdict heurístico, invocaba al juez para los UNKNOWN, y generaba el Run Report, todo en el mismo proceso. Esto impedía re-evaluar runs ya ejecutados con un juez distinto, forzaba a esperar al juez durante la ejecución (añadiendo latencia y riesgo de timeout), y acoplaba el coste del LLM juez al coste del LLM bajo evaluación.

Con la separación: `suite` es rápido y determinista (solo HTTP al backend), y `analyze` puede ejecutarse múltiples veces sobre el mismo Run Folder con distintos jueces o umbrales sin re-ejecutar los ataques. `make analyze` sin argumentos procesa todos los Pending Runs, facilitando el flujo `eval-all` → `analyze` como etapas distintas.

## Considered Options

- **Todo en suite** (anterior): un solo comando, pero sin posibilidad de re-análisis ni de separar el coste del juez.
- **Suite + analyze encadenados en eval**: `eval` ejecuta ambos automáticamente. Conveniente, pero sigue acoplando los dos pasos; y `eval-all` requeriría esperar al juez entre modelo y modelo.
- **Suite y analyze como comandos independientes (elegida)**: máxima flexibilidad. El flujo estándar es `suite` → `analyze`; `eval` y `eval-all` solo ejecutan `suite` y el usuario lanza `analyze` cuando considera oportuno.
