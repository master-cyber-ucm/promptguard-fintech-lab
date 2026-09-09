# Operación del laboratorio

Todos los comandos de esta página se ejecutan desde `lab/`. El [README principal](../README.md)
presenta el proyecto y el [protocolo de evaluación](../DEMO_FULL_SUITE.md) explica las métricas.

## Requisitos y arranque

Docker con Docker Compose. Make es opcional. La primera ejecución descarga imágenes,
dependencias y `qwen2.5:3b`; no necesita una clave de API comercial.

```bash
make run
# Si los puertos predeterminados están ocupados:
# make run BACKEND_PORT=9000 FRONTEND_PORT=4000
```

Este comando vuelve a generar `.env`. Para conservar ajustes propios, copiar
`.env.example` a `.env` y utilizar el procedimiento siguiente.

## Sin Make

```bash
cp .env.example .env
docker compose --profile ollama up -d ollama
docker compose exec ollama ollama pull qwen2.5:3b
docker compose up -d --build backend frontend
```

El frontend está en `http://localhost:3000`, el Playground en `/playground.html`,
el SOC en `/soc.html` y la documentación de API en `http://localhost:8000/docs`.

## Verificar

```bash
make test
make smoke
```

Equivalentes sin Make:

```bash
docker compose exec -T -e FIXTURES_DIR=/app/tests/fixtures backend python -m pytest tests/ -q
docker compose exec -T -e FIXTURES_DIR=/app/tests/fixtures backend python scripts/smoke_test.py
```

Los tests no necesitan inferencia real. El smoke sí utiliza el modelo y puede tardar
varios minutos en CPU. Para comprobar además generadores documentales y agente:

```bash
docker compose exec -T backend python -m pytest /app/payloads/test_payloads.py -q
# En el host, con Python 3.11+ y un entorno virtual activo:
python -m pip install -r redteam-agent/requirements.txt pytest
python -m pytest redteam-agent/tests/ -q
```

## Suite y evaluación

```bash
# Descargar el juez antes de utilizar la evaluación semántica.
docker compose exec ollama ollama pull qwen3.5:9b
# Muestra breve: un caso documental sano y otro comprometido.
make suite SUITE_ENDPOINTS=proxy PROXY_PROFILES='baseline full' ARGS='--id atk_035 --id leg_030'
# Matriz completa, con cinco repeticiones por caso y postura aplicable:
# make suite REPEAT=5
```

La matriz predeterminada incluye `simple-prompt`, `complex-prompt`,
`complex-with-context`, siete perfiles de proxy (`baseline`, `full`, `only-input`,
`only-pii`, `only-gatekeeper`, `only-auditor`, `only-leak`) y dos perfiles documentales
(`document-baseline`, `document-full`). Las fixtures y capacidades determinan qué
combinaciones son aplicables. Los documentos se leen de `payloads/`.

Tras la suite, copiar el nombre del Run Folder que se imprime:

```bash
# Sustituir NOMBRE por el nombre real, sin el prefijo audit/runs/.
make check-suite RUN=NOMBRE LEVEL=execution
make evaluate RUN=audit/runs/NOMBRE
make report RUN=audit/runs/NOMBRE
make check-suite RUN=NOMBRE LEVEL=evaluation
```

`evaluate` puede reintentar peticiones y juicios inconclusos. `report` ejecuta antes
`evaluate`. `RETRY_ROUNDS=3` es el límite predeterminado; `FORCE=1` fuerza reevaluación.
Para agregar corridas compatibles: `make final-report RUNS='NOMBRE_1 NOMBRE_2'`.
La documentación detallada y los equivalentes por CLI están en
[DEMO_FULL_SUITE.md](../DEMO_FULL_SUITE.md).

## Comandos de operación

| Comando | Función |
|---|---|
| `make up` | Construir y arrancar backend/frontend con el `.env` existente |
| `make down` | Detener y eliminar los contenedores del proyecto |
| `make restart` | Reiniciar backend/frontend |
| `make logs` | Seguir los logs |
| `make logs-backend` | Seguir los logs del backend |
| `make help` | Consultar comandos y opciones |

`make up` presupone que el proveedor ya está accesible. Para detener también Ollama:
`docker compose --profile ollama down`. Los resultados de `audit/` y el volumen de
modelos permanecen salvo que se borren expresamente.

## Configuración

`.env.example` contiene la configuración documentada. Clara usa `OLLAMA_MODEL`; el
juez semántico usa `JUDGE_MODEL` y su URL `JUDGE_BASE_URL`. Descargar cada modelo elegido
con `docker compose exec ollama ollama pull <modelo>`.

Para Ollama en el host, usar `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1`
y `JUDGE_BASE_URL=http://host.docker.internal:11434`, con Ollama iniciado en el host.
Los proveedores OpenRouter o compatibles son opcionales y se configuran con
`LLM_PROVIDER` y sus variables en `.env`; no forman parte del arranque local exigido.

## Datos y evidencias

Los usuarios `usr_001`, `usr_002`, `usr_003` y `usr_admin` son ficticios. El login del
frontend es una selección de usuario de laboratorio, no un sistema de autenticación
para producción. La suite emite credenciales de test y registra la postura efectiva.

Cada interacción deja un Session File; cada corrida agrupa sus datos bajo `audit/runs/`.
La base de datos del SOC reside en `audit/soc.db`. Ninguno de estos resultados locales
se incluye automáticamente en Git. Las evidencias adjuntas a esta entrega están en
[docs/evidencias](../docs/evidencias/README.md).

## Resolución de problemas

| Síntoma | Comprobación |
|---|---|
| Modelo no responde | `make logs-backend` y `docker compose exec ollama ollama list` |
| Evaluación semántica inconclusa | Disponibilidad del modelo y URL del juez; revisar su error |
| Documento no encontrado | Ejecutar `python3 scripts/check_delivery.py` desde el host |
| Puerto ocupado | Configurar `BACKEND_PORT` y `FRONTEND_PORT` al arrancar |
| Cambios de montaje no visibles | `docker compose up -d backend frontend` para recrear lo necesario |
