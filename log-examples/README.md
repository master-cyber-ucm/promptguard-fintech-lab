# Ejemplo de una ejecución completa

Esta carpeta contiene una ejecución histórica completa del laboratorio para que la
entrega pueda revisarse sin esperar a que termine una campaña nueva. El ejemplo se
ejecutó con `qwen2.5:3b`, 111 fixtures y tres repeticiones por combinación.

## Qué contiene

Los logs conservan la salida de los comandos tal como se produjo, separados por fase:

| Archivo | Contenido |
|---|---|
| [`logs/01-suite.log`](logs/01-suite.log) | `run_attack_suite.py` y la comprobación inicial del plan |
| [`logs/02-evaluate.log`](logs/02-evaluate.log) | Las rondas de `evaluate.py`, incluidos reintentos e inconclusos |
| [`logs/03-report.log`](logs/03-report.log) | `report.py` y las tablas agregadas del informe |

El resultado estructurado está en [`runs/20260907_193559_qwen2.5-3b/`](runs/20260907_193559_qwen2.5-3b/).
Empieza por [`run.md`](runs/20260907_193559_qwen2.5-3b/run.md), y después sigue un
resultado de la tabla hasta su Session File dentro de la carpeta de la postura.
`run.json`, `coverage-plan.json`, `execution-ledger.jsonl` y `provenance.json` son las
fuentes estructuradas para comprobar la misma lectura.

## Cómo leer el ejemplo

1. En `01-suite.log`, localiza el `Run Folder`, el número de ejecuciones y las
   peticiones HTTP. El indicador `correctos` solo significa que la petición terminó
   sin error técnico; no significa que un ataque haya sido bloqueado.
2. En `02-evaluate.log`, busca `INCONCLUSIVE`, `ERROR` y las rondas de reintento.
   Una evaluación inconclusa no debe convertirse en un bloqueo ni en una brecha.
3. En `03-report.log`, contrasta los porcentajes con la cobertura y los límites que
   aparecen en `run.md`. El denominador y las exclusiones importan tanto como el
   porcentaje.
4. Abre un Session File para verificar el prompt, la respuesta, las herramientas y
   los eventos de defensa. El SOC puede consultar estos mismos artefactos cuando el
   Run Folder se copie bajo `lab/audit/runs/`.
5. Comprueba `provenance.json` antes de citar el resultado. Este ejemplo conserva el
   estado histórico del árbol y por eso declara el árbol sucio; no representa una
   ejecución reproducida sobre el `main` actual.

## Cómo analizar un run propio

Desde `lab/`, después de arrancar el stack y ejecutar la suite:

```bash
make check-suite RUN=NOMBRE LEVEL=execution
make evaluate RUN=audit/runs/NOMBRE
make report RUN=audit/runs/NOMBRE
make check-suite RUN=NOMBRE LEVEL=evaluation
```

Lee el resultado siguiendo el mismo orden: cobertura, errores e inconclusos,
seguridad, utilidad legítima, postura efectiva y procedencia. `report` vuelve a
invocar la evaluación pendiente antes de publicar el informe. Si la cobertura no
reconcilia o una postura solicitada no coincide con la efectiva, el resultado no debe
usarse para una conclusión causal.

Para consolidar varias corridas compatibles, usa `make final-report RUNS='NOMBRE_1 NOMBRE_2'` después de revisar manualmente que comparten modelo, fixtures, versión y
posturas. El consolidado es auxiliar: no sustituye la lectura de cada Run Report ni
comprueba por sí solo la comparabilidad.

## Alcance del ejemplo

Este material es evidencia de lectura y trazabilidad, no una promesa de que el modelo
produzca exactamente las mismas respuestas. El proveedor LLM no garantiza
determinismo. El ejemplo contiene errores técnicos resueltos o pendientes e
inconclusos deliberados de aquella campaña; deben leerse como parte del resultado,
no ocultarse al citarlo.
