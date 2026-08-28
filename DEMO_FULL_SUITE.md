# DEMO — campaña exhaustiva y auditoría de resultados

Esta guía ejecuta la biblioteca completa de PromptGuard, recupera casos sin
evidencia y explica cómo auditar el resultado. Complementa `DEMO_BY_COMMANDS.md`
(revisión técnica) y `DEMO_BY_FRONT.md` (recorrido visual curado).

La corrida no es una demostración rápida. Con `qwen2.5:3b` local se verificaron
**110 fixtures**, **381 combinaciones fixture–endpoint** y **511 peticiones HTTP**.
Los fixtures multi-turn hacen que ambas cifras sean distintas. El runner las
imprime antes de empezar; anótalas junto al modelo y al Run Folder.

> La ejecución completa puede durar horas en CPU. No cierres Docker ni reinicies
> `backend` mientras está en curso. Los Session Files se guardan incrementalmente:
> una corrida interrumpida se puede comprobar y completar sin borrar evidencia.

## 1. Lanzar la suite completa

Desde la raíz del repositorio:

```bash
cd lab
make run
make suite
```

`make suite` crea un Run Folder con este patrón:

```text
lab/audit/runs/AAAAMMDD_HHMMSS_qwen2.5-3b/
```

La cabecera real observada fue:

```text
Modelo    : qwen2.5:3b (ollama)
Fixtures  : 110 · Ejecuciones totales: 381
Peticiones HTTP al backend: 511
Run Folder: app/audit/runs/20260827_133926_qwen2.5-3b
```

Guarda el último componente del Run Folder:

```bash
RUN=20260827_133926_qwen2.5-3b
```

`Ejecuciones totales` son pares fixture–endpoint. `Peticiones HTTP` incluye
cada Step de un fixture multi-turn. Varios Steps se acumulan en un único
Session File, por lo que no se deben comparar esas cifras directamente.

## 2. Detectar una corrida incompleta

Al terminar el runner, ejecuta siempre:

```bash
make check-suite RUN="$RUN"
```

El comando solo lee catálogo y Session Files; no llama al modelo. Devuelve
código `0` si está completa y `1` si hay huecos. En la corrida real observada:

```text
Esperadas  : 381 combinaciones fixture-endpoint
Evidencia  : 379 combinaciones únicas · 379 Session Files

FALTAN (2):
  - atk_034 --endpoint complex-prompt
  - atk_060 --endpoint complex-prompt
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

Para los dos huecos anteriores, que comparten endpoint:

```bash
make suite ARGS="--resume-run $RUN --timeout 600 \
  --id atk_034 --id atk_060 --endpoint complex-prompt"
```

Agrupa los huecos por endpoint. Por ejemplo, para un documento:

```bash
make suite ARGS="--resume-run $RUN --timeout 600 \
  --id atk_035 --endpoint complex-with-document"
```

Después de cada reintento:

```bash
make check-suite RUN="$RUN"
```

Un timeout mayor soluciona una espera corta, no una excepción funcional. En la
ejecución verificada, `atk_034` y `atk_060` provocaron
`Exceeded maximum output retries (3)` en `complex-prompt`. Si siguen faltando,
conserva el Run Folder, anota fixture, endpoint, modelo y error, y no presentes
la corrida como completa. La traza SOC ayuda a investigar, pero no sustituye al
Session File que falta.

## 4. Auditar los Session Files

Los ficheros quedan agrupados por endpoint:

```text
lab/audit/runs/$RUN/
├── simple-prompt/
├── complex-prompt/
├── complex-with-context/
├── proxy/
└── complex-with-document/
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

En `run.md`, revisa por endpoint total, pasados/fallados, bloqueo de ataques,
brechas, atención legítima y falsos positivos. En la tabla por fixture compara
baseline con `proxy`. En `run.json`, usa `summary`, `by_category` y `fixtures`
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

La corrida observada muestra 514 Turns, 384 sesiones y 68 bloqueos. Los 110
identificadores de fixture son localizables en el SOC; cinco Turns contienen el
error de reintento de salida para `atk_034`, `atk_040` o `atk_060`. Hay más
Turns que las 511 peticiones iniciales porque hubo tres reintentos. El SOC
conserva esos Turns; el verificador de ficheros es la autoridad para declarar
que la corrida está completa.

![Fila de la campaña completa en Corridas](docs/reports/demo-full-suite/01-soc-runs-full-suite.png)

La siguiente captura muestra el filtro por Run y el detalle real de `atk_040`:
postura baseline, `output_auditor → ALLOW`, prompt Base64 y respuesta entregada.
El mismo procedimiento sirve para cualquier fixture de la Suite.

![Búsqueda y detalle de un ataque de la Suite](docs/reports/demo-full-suite/03-soc-attack-detail.png)

## 7. Criterio de cierre

Una campaña exhaustiva está lista para presentar solo si:

1. `make check-suite RUN="$RUN"` imprime `COMPLETA`.
2. `make evaluate` y `make report` generaron Verdicts y `run.json`/`run.md`.
3. Cada hallazgo relevante se puede rastrear desde **Corridas** hasta Turn,
   Session File y Verdict.

`20260827_133926_qwen2.5-3b` queda como evidencia de una campaña larga y su
recuperación parcial: aún no satisface el primer criterio por los dos fixtures
indicados en la sección 2.
