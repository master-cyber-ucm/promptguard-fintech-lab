# Run Folder por ejecución de suite, con subcarpetas por endpoint

Cada Suite Run crea un directorio `lab/audit/runs/{timestamp}_{model_slug}/` que agrupa todos sus artefactos. Dentro, hay una subcarpeta por endpoint (ej. `simple-prompt/`, `complex-prompt/`) con los Session Files correspondientes. El Run Report (`run.md`, `run.json`) queda en la raíz del Run Folder.

La estructura anterior era plana: Session Files en `audit/sessions/` y Run Reports en `audit/runs/`. Un mismo directorio mezclaba ficheros de distintos modelos, runs y endpoints, haciendo imposible saber qué ficheros pertenecían a qué run sin parsear el contenido. Con el Run Folder, todo lo de una ejecución está co-localizado y la estructura del directorio es autoexplicativa. La subcarpeta por endpoint resuelve la ambigüedad cuando el mismo fixture se ejecuta contra múltiples endpoints en el mismo run.

## Considered Options

- **Plano en `audit/sessions/`** (anterior): sin agrupación, ficheros de distintos runs mezclados. Imposible identificar pertenencia sin parsear contenido.
- **Subcarpeta por modelo**: agrupa por modelo pero no por ejecución — un modelo evaluado dos veces mezclaría runs.
- **Run Folder con subcarpeta por endpoint (elegida)**: agrupa por ejecución, distingue endpoints sin ambigüedad, y permite que `analyze` opere sobre un directorio concreto.
