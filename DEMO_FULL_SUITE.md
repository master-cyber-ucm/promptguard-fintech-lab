# Suite completa y auditoría de resultados

Protocolo vigente de evaluación. La biblioteca incluye texto y documentos PDF, DOCX
y XLSX. Los ensayos de consumo LLM10 usan el runner separado de la
[demostración por comandos](DEMO_BY_COMMANDS.md#5-consumo-de-recursos-llm10).

## 1. Preparación

Seguir primero [el arranque](DEMO_BY_COMMANDS.md#1-arrancar). Todos los comandos de
esta guía se ejecutan desde `lab/`, con el stack arrancado mediante `make run`:

```bash
docker compose exec ollama ollama pull qwen3.5:9b
make test
```

El modelo de Clara es `qwen2.5:3b` y el juez predeterminado es `qwen3.5:9b`.
Para una campaña que se vaya a citar, partir de un commit con el árbol limpio;
comprobar después que `provenance.json` identifica esa versión.
El hardware y los modelos condicionan la duración; en CPU una matriz exhaustiva
puede tardar mucho. Registrar la configuración y conservar la procedencia del run.

## 2. Ejecutar

Para comprobar primero los tres endpoints de texto, los siete perfiles de proxy
y los dos perfiles documentales con DOCX y XLSX, se puede usar esta muestra de
**3 fixtures y 14 ejecuciones** (el PDF se comprueba en la guía por comandos):

```bash
make suite REPEAT=1 ARGS='--id leg_001_consulta_saldo_propio --id leg_031 --id leg_032'
```

Para la biblioteca completa, ejecutar en su lugar:

```bash
# Una repetición por combinación aplicable; ya es una matriz exhaustiva.
make suite REPEAT=1
# Para el estudio con cinco repeticiones, lanzar en su lugar:
# make suite REPEAT=5
```

La matriz predeterminada comprende:

| Canal | Endpoint o postura |
|---|---|
| Texto | `simple-prompt`, `complex-prompt`, `complex-with-context` |
| Texto por proxy | `baseline`, `full`, `only-input`, `only-pii`, `only-gatekeeper`, `only-auditor`, `only-leak` |
| Documento por proxy | `document-baseline`, `document-full` |

Con las 111 fixtures de esta versión, `REPEAT=1` planifica **918 ejecuciones
y 1244 peticiones HTTP** (los casos de varios turnos hacen más de una petición).
Con `REPEAT=5`, son 4590 ejecuciones y 6220 peticiones. Los reintentos de evaluación
pueden añadir tráfico. No todas las fixtures son aplicables a todas las posturas.
El plan de cobertura registra el denominador esperado. La postura `baseline` no implica automáticamente
`vulnerable=true`: son dimensiones separadas que quedan registradas en la configuración de cada ejecución.

Alternativa directa para **cinco repeticiones** (usar `--repeat 1` para equivaler
a la comprobación anterior). No añade la inyección de procedencia Git de Make;
para una campaña que se vaya a citar, utilizar preferentemente `make suite`:

```bash
docker compose exec -T -e FIXTURES_DIR=/app/tests/fixtures backend \
  python scripts/run_attack_suite.py --repeat 5 \
  --endpoint simple-prompt --endpoint complex-prompt \
  --endpoint complex-with-context --endpoint proxy \
  --proxy-profile baseline --proxy-profile full --proxy-profile only-input \
  --proxy-profile only-pii --proxy-profile only-gatekeeper \
  --proxy-profile only-auditor --proxy-profile only-leak \
  --document-profile document-baseline --document-profile document-full
```

Para una muestra documental: `make suite SUITE_ENDPOINTS=proxy ARGS='--id atk_035 --id leg_030'`.
Para limitar la matriz a texto: añadir `DOCUMENT_PROFILES=`. Las opciones completas
se consultan desde `lab/` con:

```bash
docker compose exec -T backend python scripts/run_attack_suite.py --help
```

## 3. Verificar ejecución y evaluar

Copiar el nombre del Run Folder impreso. En estos ejemplos `NOMBRE` es únicamente
ese nombre, sin `audit/runs/`:

```bash
make check-suite RUN=NOMBRE LEVEL=execution
make evaluate RUN=audit/runs/NOMBRE
make report RUN=audit/runs/NOMBRE
make check-suite RUN=NOMBRE LEVEL=evaluation
```

`check-suite` verifica la correspondencia entre plan y resultados. Un error técnico
terminal puede reconciliar correctamente sin ser un resultado válido de seguridad.
`evaluate` reintenta errores recuperables y evaluaciones inconclusas de forma acotada;
`report` llama a `evaluate` antes de generar el informe. Revisar el estado final y los
errores pendientes, no solo el código de salida del comando.

Sin Make (la evaluación se lanza explícitamente; `report.py` por sí solo no la ejecuta):

```bash
docker compose exec -T backend python scripts/check_suite_run.py --run NOMBRE --level execution
docker compose exec -T backend python scripts/evaluate.py --run audit/runs/NOMBRE --retry-rounds 3
docker compose exec -T backend python scripts/report.py --run audit/runs/NOMBRE
docker compose exec -T backend python scripts/check_suite_run.py --run NOMBRE --level evaluation
```

## 4. Leer el Run Folder

Los artefactos de la suite y la evaluación incluyen:

- `suite-config.json` y `provenance.json`: parámetros, modelos y procedencia disponible.
- `coverage-plan.json` y `execution-ledger.jsonl`: combinaciones planificadas y estados.
- `executions.json`: resultados de las ejecuciones.
- Session Files por endpoint/postura: conversación, herramientas y evidencia.
- `run.md` y `run.json`: informe legible y estructurado.

Consultar primero cobertura, exclusiones e inconclusos. Después examinar seguridad,
utilidad legítima, atribución causal e incertidumbre. Una respuesta bloqueada no es
necesariamente útil; una llamada a herramienta no acredita por sí sola su efecto.
El Run Report distingue estas dimensiones y explica sus criterios de evaluación.

## 5. Inspección visual y agregación

En `http://localhost:3000/soc.html`, abrir **Corridas**, localizar el Run Folder y
consultar **Eventos**. Desplegar el Turn y su sesión para identificar el prompt,
las decisiones de cada control y las herramientas. El SOC aporta observabilidad;
las conclusiones cuantitativas se sustentan en el informe y su evidencia.

Para obtener un resumen auxiliar de varias **corridas de suite ya evaluadas**
(no campañas del agente ni escenarios LLM10):

```bash
make final-report RUNS='NOMBRE_1 NOMBRE_2'
```

Se generan `audit/final-results.md` y `audit/final-results.json`, sustituyendo el
consolidado anterior. El script agrupa por modelo y etiqueta de perfil: **no valida
la cobertura ni la comparabilidad**, ni sustituye las exclusiones, inconclusos e
incertidumbre del Run Report. Antes de agregar, comprobar manualmente en cada run
la versión, los modelos, las fixtures y las posturas efectivas. No usar ese resumen
para sostener por sí solo una conclusión causal ni mezclar corridas incompatibles.
Los perfiles actuales `proxy-document-*` sí entran en el agregado; la exclusión
heredada del script solo afecta al antiguo target `complex-with-document`.

## 6. Evidencia que acompaña a una conclusión

Citar el modelo, la postura, las repeticiones, el denominador, las exclusiones y el
Run Folder. Entregar ese Run Folder completo cuando se utilice en la memoria.
`lab/audit/` está ignorado por Git: generar un informe local no lo añade al anexo.
Las [evidencias históricas incluidas](docs/evidencias/README.md) tienen un manifiesto
propio y no sustituyen una campaña nueva sobre la versión final.
