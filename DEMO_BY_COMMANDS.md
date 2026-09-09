# Demostración por comandos

Guía de la versión de entrega. Los resultados del modelo pueden variar: se comprueba
la evidencia de cada ejecución, sin exigir una frase o porcentaje predeterminados.
La [guía visual](DEMO_BY_FRONT.md) permite inspeccionar esos mismos eventos.

## 1. Arrancar

Desde la raíz del repositorio:

```bash
cd lab
make run
make test
make smoke
```

`make run` genera `.env` y descarga el modelo de Clara. Para conservar un `.env`
propio o arrancar sin Make, seguir [la guía de operación](lab/README.md).
`make test` comprueba lógica sin inferencia; `make smoke` contacta con el modelo.

## 2. Comparar texto

```bash
make suite SUITE_ENDPOINTS=proxy PROXY_PROFILES='baseline full' DOCUMENT_PROFILES= ARGS='--id atk_010 --id leg_001'
```

Esta muestra compara un intento de *confused deputy* y una petición legítima con dos
posturas del mismo proxy. No representa toda la biblioteca. Guardar el nombre del
Run Folder impreso; se usará al evaluar y consultar el SOC.

`baseline` desactiva los controles de la matriz, mientras `full` los activa.
`vulnerable` es un factor experimental separado: no se debe deducir su valor del
nombre del perfil. Consultar `suite-config.json` y la postura efectiva.

## 3. Comparar documentos

```bash
make suite SUITE_ENDPOINTS=proxy PROXY_PROFILES='baseline full' ARGS='--id atk_035 --id leg_030'
```

Se envían la nómina comprometida y la sana de `lab/payloads/` con los perfiles
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

Abrir `lab/audit/runs/NOMBRE/run.md` desde el host. Comprobar cobertura, errores,
resultado de seguridad, utilidad y las sesiones que sustentan cada resultado.
En el SOC (`http://localhost:3000/soc.html`), buscar la corrida y desplegar los
Turns para ver los controles evaluados. El Input Sanitizer aplica firmas reales;
`ALLOW` significa que esa etapa no bloqueó ese turno, no que sea un componente vacío.

## 5. Consumo de recursos (LLM10)

El runner específico permite una comparación acotada del límite de salida:

```bash
docker compose exec -T backend python scripts/run_llm10_suite.py --id llm10_002 --vulnerable
docker compose exec -T backend python scripts/run_llm10_suite.py --id llm10_002
```

Revisar los informes que imprime el runner. Este experimento no equivale a un ensayo
de capacidad de producción. El catálogo de escenarios está en
[llm10_scenarios.yaml](lab/backend/tests/fixtures/llm10_scenarios.yaml).

## 6. Campaña autónoma

Con el stack en marcha y el modelo `qwen3.5:9b` descargado, abrir otro terminal.
Desde la raíz, con Python 3.11+ y un entorno virtual activo:

```bash
python -m pip install -r lab/redteam-agent/requirements.txt
cd lab/redteam-agent
python cli.py --techniques acciones-no-autorizadas --max-attempts 3 --attacker-model qwen3.5:9b
```

El agente imprime el Run Folder con las sesiones y el informe de campaña. Consultar
sus resultados en el SOC y contrastar cualquier hallazgo con la evidencia de las
herramientas. Esta muestra limita intentos; no mide una tasa estable de ataque.
Más opciones en [el README del agente](lab/redteam-agent/README.md).

## 7. Cierre

Las evidencias locales permanecen en `lab/audit/`. Para detener el stack desde `lab/`:

```bash
docker compose --profile ollama down
```

La [suite completa](DEMO_FULL_SUITE.md) describe la matriz de resultados y la
[documentación de alcance](docs/alcance-y-limitaciones.md) limita las conclusiones.
