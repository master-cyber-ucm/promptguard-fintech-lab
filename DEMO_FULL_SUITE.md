# DEMO — campaña exhaustiva y auditoría de resultados

Esta guía ejecuta la biblioteca completa de PromptGuard, recupera casos sin
evidencia y explica cómo auditar el resultado. Complementa `DEMO_BY_COMMANDS.md`
(revisión técnica) y `DEMO_BY_FRONT.md` (recorrido visual curado).

La suite no es una demostración rápida: ejecuta los escenarios `simple-prompt`,
`complex-prompt`, `complex-with-context` y cuatro posturas del mismo proxy
(`baseline`, `gatekeeper`, `output`, `full`). El canal documental queda fuera
del estudio. Los fixtures multi-turn hacen que el número de ejecuciones y de
peticiones HTTP sea distinto; el runner imprime ambas cifras antes de empezar.
Anótalas junto al modelo y al Run Folder, sin reutilizar cifras de campañas anteriores.

> La ejecución completa puede durar horas en CPU. No cierres Docker ni reinicies
> `backend` mientras está en curso. Los Session Files se guardan incrementalmente:
> una corrida interrumpida se puede comprobar y completar sin borrar evidencia.

## 1. Lanzar la suite: comprobación funcional o resultado estadístico

Desde la raíz del repositorio:

```bash
cd lab
make run
# Comprobación funcional: una ejecución por fixture.
make suite REPEAT=1
```

Para obtener resultados que se puedan comparar con más confianza, ejecuta la
misma matriz con cinco repeticiones:

```bash
# Resultado para el informe final: cinco ejecuciones independientes por fixture.
make suite REPEAT=5
```

`REPEAT=1` es adecuado para comprobar que el stack, los endpoints y la
evaluación funcionan. No basta para sostener una conclusión sobre un modelo no
determinista. `REPEAT=5` es el mínimo recomendado para el reporte final: permite
observar si una tasa depende de una respuesta aislada del modelo. No convierte el
estudio en una validación estadística industrial; sí hace explícita su variabilidad.

### Guardar el log de ejecución

La suite puede durar horas. Guarda siempre su salida en un fichero: el Run Folder
es la evidencia primaria de cada turno y el log de consola documenta el progreso,
los timeouts y cualquier recuperación necesaria. Crea un fichero nuevo con `>`:

```bash
mkdir -p audit/logs
make suite REPEAT=5 > audit/logs/suite-final.log 2>&1
```

Si reanudas una corrida o quieres conservar una secuencia de intentos en el mismo
fichero, usa `>>` para añadir al final sin perder el registro anterior:

```bash
make suite SUITE_ENDPOINTS="proxy" PROXY_PROFILES="full" \
  ARGS="--resume-run $RUN --timeout 600 --id atk_001" \
  >> audit/logs/suite-final.log 2>&1
```

`2>&1` incluye los errores del proceso en el mismo log. No uses `>` al reintentar:
sobrescribiría la evidencia de consola del intento inicial.

`make suite` crea un Run Folder con este patrón:

```text
lab/audit/runs/AAAAMMDD_HHMMSS_qwen2.5-3b/
```

La cabecera tendrá esta forma; las cifras dependen del catálogo vigente y de la
matriz seleccionada:

```text
Modelo    : qwen2.5:3b (ollama)
Endpoints : simple-prompt, complex-prompt, complex-with-context,
            proxy-baseline, proxy-gatekeeper, proxy-output, proxy-full
Fixtures  : <catálogo vigente> · Ejecuciones totales: <calculado por runner>
Peticiones HTTP al backend: <calculado por runner>
Repeticiones: 5x por fixture
Run Folder: app/audit/runs/<timestamp>_qwen2.5-3b
```

Guarda el último componente del Run Folder:

```bash
RUN=<timestamp>_qwen2.5-3b
```

`Ejecuciones totales` son pares fixture–endpoint. `Peticiones HTTP` incluye
cada Step de un fixture multi-turn. Varios Steps se acumulan en un único
Session File, por lo que no se deben comparar esas cifras directamente.

## 2. Detectar una corrida incompleta

Al terminar el runner, ejecuta siempre:

```bash
make check-suite RUN="$RUN"
```

El comando solo lee catálogo y Session Files; no llama al modelo. Lee
`suite-config.json`, por lo que exige exactamente los escenarios y perfiles que
formaron parte de esa campaña. Devuelve código `0` si está completa y `1` si hay
huecos. La salida tendrá esta forma:

```text
Esperadas  : <combinaciones de la matriz>
Evidencia  : <combinaciones escritas> · <Session Files>

FALTAN (<n>):
  - <fixture_id> --endpoint <escenario_o_perfil>
```

Una fila visible en el SOC prueba que se recibió un Turn; un Session File prueba
además que se escribió evidencia primaria. Para cerrar una Suite Run, el
verificador debe declarar `COMPLETA`.

## 3. Reintentar solo los casos fallidos

El runner acepta:

- `--resume-run RUN_FOLDER`: escribe en el Run Folder existente.
- `--timeout SEGUNDOS`: espera por petición HTTP. El valor por defecto es
  300; súbelo para un fixture lento con varias tools. También puede usarse la
  variable `SUITE_REQUEST_TIMEOUT`.

Para reintentar huecos de un escenario de prompt:

```bash
make suite ARGS="--resume-run $RUN --timeout 600 \
  --id atk_034 --id atk_060 --endpoint complex-prompt"
```

Agrupa los huecos por escenario. Para una postura concreta del proxy, conserva
el perfil que figura en `suite-config.json`:

```bash
make suite SUITE_ENDPOINTS="proxy" PROXY_PROFILES="full" \
  ARGS="--resume-run $RUN --timeout 600 --id atk_001"
```

Después de cada reintento:

```bash
make check-suite RUN="$RUN"
```

Un timeout mayor soluciona una espera corta, no una excepción funcional. Si un
caso sigue faltando, conserva el Run Folder, anota fixture, escenario/perfil,
modelo y error, y no presentes la corrida como completa. La traza SOC ayuda a
investigar, pero no sustituye al Session File que falta.

## 4. Auditar los Session Files

Los ficheros quedan agrupados por endpoint:

```text
lab/audit/runs/$RUN/
├── simple-prompt/
├── complex-prompt/
├── complex-with-context/
├── proxy-baseline/
├── proxy-gatekeeper/
├── proxy-output/
├── proxy-full/
└── suite-config.json
```

Para abrir uno:

```bash
sed -n '1,220p' "audit/runs/$RUN/complex-prompt/ARCHIVO.md"
```

Un Session File real de `atk_040` contiene estas partes:

| Parte | Qué revisar |
|---|---|
| Cabecera | sesión, usuario, modelo y hora. |
| `System Prompt` | instrucciones internas realmente activas. |
| `Turno N` / `Fixture` | id, kind y resultado esperado. |
| `Prompt` | texto exacto recibido. |
| `Tools invocadas` | argumentos, resultado y denegaciones. |
| `Respuesta` | dato finalmente entregado. |
| `Metadatos` | latencia y, tras evaluación, Verdict. |

No deduzcas una brecha solo por el prompt. En ataques, busca si se entregó el
dato prohibido o se ejecutó la tool; en controles legítimos, busca respuesta útil
sin bloqueo espurio.

## 5. Analyze Pass y Run Report

Solo cuando el verificador declare la corrida completa:

```bash
make evaluate RUN="audit/runs/$RUN/"
make report RUN="audit/runs/$RUN/"
```

El Analyze Pass añade `## Evaluación ·` a los Session Files. El Report crea:

```text
audit/runs/$RUN/
├── <endpoint>/<session>.md  # evidencia primaria + Verdict
├── run.json                 # datos por endpoint y fixture
└── run.md                   # lectura humana y comparación
```

En `run.md`, revisa el consolidado por escenario y la segmentación por familia
de ataque. En `proxy-*`, compara la progresión `baseline → gatekeeper → output
→ full`; no atribuyas una mejora al system prompt si solo aparece en una postura
del proxy. En `run.json`, usa `summary`, `by_category`, `by_family` y `fixtures`
para automatización. Para un ataque, `passed` significa que se logró la
resistencia esperada; para un prompt legítimo, que se atendió correctamente.

No lances este paso sobre una corrida incompleta: el agregado podría confundir
una ausencia con un resultado.

## 6. Auditoría visual en el SOC

Abre http://localhost:3000/soc.html#/runs.

1. En **Corridas**, localiza `$RUN`, verifica `Origen: suite` y sus contadores.
2. Pulsa el identificador: abre **Eventos** con `run_id=$RUN` aplicado.
3. En **Buscar en prompt o respuesta…**, escribe un id, por ejemplo `atk_040`,
   `atk_034`, `atk_060` o `leg_001`.
4. Despliega el Turn. Revisa postura efectiva, cadena de componentes, acción
   (`ALLOW`, `SUSPICIOUS` o `BLOCK`), regla, prompt y respuesta.
5. Pulsa **Ver sesión completa** y contrasta con el Session File. Si falta,
   vuelve a la sección 3.

El SOC conserva cada Turn, incluidos reintentos y los perfiles efectivos del
proxy. Por ello puede contener más Turns que las peticiones previstas por el
runner. El verificador de ficheros es la autoridad para declarar que la corrida
está completa; el SOC sirve para investigar por qué un caso fue bloqueado,
permitido o falló.

![Fila de la campaña completa en Corridas](docs/reports/demo-full-suite/01-soc-runs-full-suite.png)

La siguiente captura ilustra el filtro por Run y el detalle de un ataque. En la
matriz actual, verifica que la postura del Turn coincide con el directorio
`proxy-baseline`, `proxy-gatekeeper`, `proxy-output` o `proxy-full` de su
Session File. El mismo procedimiento sirve para cualquier fixture de la Suite.

![Búsqueda y detalle de un ataque de la Suite](docs/reports/demo-full-suite/03-soc-attack-detail.png)

## 7. Criterio de cierre

Una campaña exhaustiva está lista para presentar solo si:

1. `make check-suite RUN="$RUN"` imprime `COMPLETA`.
2. `make evaluate` y `make report` generaron Verdicts y `run.json`/`run.md`.
3. Cada hallazgo relevante se puede rastrear desde **Corridas** hasta Turn,
   Session File y Verdict.

Para incorporar resultados a la memoria, consolida solo Run Folders completos:

```bash
make final-report RUNS="$RUN"
```

El informe `audit/final-results.md` presenta primero el consolidado por
configuración y después la segmentación por familia de ataque. Para resultados
finales, usa Run Folders ejecutados con `REPEAT=5`; conserva `REPEAT=1` como
comprobación funcional y evidencia de depuración.
