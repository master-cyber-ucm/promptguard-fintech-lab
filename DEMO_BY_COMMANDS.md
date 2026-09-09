# Demostración por comandos

Guía de la versión de entrega. Los resultados del modelo pueden variar: se comprueba
la evidencia de cada ejecución, sin exigir una frase o porcentaje predeterminados.
La [guía visual](DEMO_BY_FRONT.md) permite inspeccionar esos mismos eventos.

## 1. Arrancar

Requisitos: Docker con Docker Compose, Make y acceso a Internet para la primera
descarga. Los puertos predeterminados son 3000, 8000 y 11434.
Desde la raíz del repositorio:

```bash
cd lab
make run
make test
make smoke
```

`make run` **sobrescribe** `lab/.env` y descarga el modelo de Clara (`qwen2.5:3b`).
Para conservar un `.env` propio o arrancar sin Make, seguir [la guía de operación](lab/README.md).
`make test` comprueba lógica sin inferencia; `make smoke` contacta con el modelo
y puede tardar varios minutos en CPU. Esperar a que termine antes de continuar.
Salvo la campaña del apartado 6, los comandos siguientes se ejecutan desde `lab/`.

## 2. Comparar texto

```bash
make suite SUITE_ENDPOINTS=proxy PROXY_PROFILES='baseline full' DOCUMENT_PROFILES= ARGS='--id atk_010 --id leg_001_consulta_saldo_propio'
```

Esta muestra compara un intento de *confused deputy* y una petición legítima con dos
posturas del mismo proxy: **2 fixtures y 4 ejecuciones** con una repetición.
El ID legítimo completo es `leg_001_consulta_saldo_propio`; `leg_001` no existe.
No representa toda la biblioteca. Guardar el nombre del
Run Folder impreso; se usará al evaluar y consultar el SOC.

`baseline` desactiva los controles de la matriz, mientras `full` los activa.
`vulnerable` es un factor experimental separado: no se debe deducir su valor del
nombre del perfil. Consultar `suite-config.json` y la postura efectiva.

## 3. Comparar documentos

```bash
make suite SUITE_ENDPOINTS=proxy PROXY_PROFILES='baseline full' ARGS='--id atk_035 --id leg_030'
```

Se envían `nomina_comprometida.pdf` y `nomina_sana.pdf` de `lab/payloads/`
(**2 fixtures y 4 ejecuciones**) con los perfiles
`document-baseline` y `document-full`. El archivo forma parte de la petición al
proxy; el runner ya no utiliza un endpoint separado `complex-with-document`.
Inspeccionar extracción, controles documentales, herramientas y respuesta final.
Una ausencia de fuga por sí sola no acredita que un control concreto haya actuado.

## 4. Evaluar e inspeccionar

Descargar una vez el modelo del juez:

```bash
docker compose exec ollama ollama pull qwen3.5:9b
```

Sustituir `NOMBRE` por el nombre del Run Folder de la muestra elegida:

```bash
make check-suite RUN=NOMBRE LEVEL=execution
make evaluate RUN=audit/runs/NOMBRE
make report RUN=audit/runs/NOMBRE
make check-suite RUN=NOMBRE LEVEL=evaluation
```

Desde la raíz, abrir `lab/audit/runs/NOMBRE/run.md`; desde `lab/`,
la ruta es `audit/runs/NOMBRE/run.md`. Repetir el bloque para cada una de las dos muestras.
`make report` vuelve a ejecutar la evaluación pendiente antes de generar el informe.
El resumen «correctos» del runner indica ejecuciones sin errores técnicos; no es
un veredicto de seguridad ni de utilidad. Comprobar cobertura, errores,
resultado de seguridad, utilidad y las sesiones que sustentan cada resultado.
En el SOC (`http://localhost:3000/soc.html`), buscar la corrida y desplegar los
Turns para ver los controles evaluados. El Input Sanitizer aplica firmas reales;
`ALLOW` significa que esa etapa no bloqueó ese turno, no que sea un componente vacío.

## 5. Consumo de recursos (LLM10)

El runner específico envía el mismo escenario con `vulnerable=true` y
`vulnerable=false`. Indicar la ruta de fixtures del contenedor:

```bash
docker compose exec -T -e FIXTURES_DIR=/app/tests/fixtures backend python scripts/run_llm10_suite.py --id llm10_002 --vulnerable
docker compose exec -T -e FIXTURES_DIR=/app/tests/fixtures backend python scripts/run_llm10_suite.py --id llm10_002
```

Cada comando imprime un informe `/app/audit/runs/.../run.json`, visible en el host
como `lab/audit/runs/.../run.json`. Revisar `error`, la longitud y la respuesta.
El veredicto de este escenario usa un umbral heurístico de 2000 **caracteres**, no
una medida de tokens ni una prueba de que actuó el límite de salida. Con la
configuración predeterminada no se garantiza una diferencia entre ambas respuestas.
Una respuesta vacía por error tampoco acredita un bloqueo: esa ejecución es inválida
para la comparación. El aviso `esperado=BLOCKED` usa la misma expectativa incluso
en la ejecución vulnerable; no es un error de arranque. Este experimento no equivale
a un ensayo de capacidad de producción. El catálogo de escenarios está en
[llm10_scenarios.yaml](lab/backend/tests/fixtures/llm10_scenarios.yaml).

## 6. Campaña autónoma

Con el stack en marcha y el modelo `qwen3.5:9b` descargado, abrir otro terminal.
En macOS/Linux o WSL, desde la raíz y con Python 3.11+:

```bash
python3 -m venv /tmp/tfm-demo-agent-venv
source /tmp/tfm-demo-agent-venv/bin/activate
python -m pip install -r lab/redteam-agent/requirements.txt
cd lab/redteam-agent
python cli.py --techniques acciones-no-autorizadas --max-attempts 3 --attacker-model qwen3.5:9b
```

El agente imprime el Run Folder con las sesiones y el informe de campaña. Consultar
sus resultados en el SOC (**Corridas**) y contrastar cualquier hallazgo con la evidencia de las
herramientas. El atacante utiliza `localhost:11434` y el backend `localhost:8000`; si se
cambiaron los puertos, ajustar `--ollama-port` y `--port`. Los 3 intentos son
un máximo, no una duración máxima; cada intento puede requerir varias inferencias.
Esta muestra no mide una tasa estable de ataque.
Más opciones en [el README del agente](lab/redteam-agent/README.md).

## 7. Cierre

Las evidencias locales permanecen en `lab/audit/`. Para detener el stack desde `lab/`:

```bash
docker compose --profile ollama down
```

La [suite completa](DEMO_FULL_SUITE.md) describe la matriz de resultados y cómo interpretar sus evidencias.
