# PromptGuard FinTech Lab

Laboratorio del TFM **Evaluación de la Ciberseguridad en Entornos de IA Generativa**
(Máster en Ciberseguridad, UCM). Simula VerdaBank, un banco ficticio, y Clara, su
asistente con herramientas bancarias sobre datos sintéticos.

El laboratorio permite reproducir ataques, comparar configuraciones de defensa y
examinar las evidencias de cada interacción. No representa un servicio bancario real.

## Reproducir la entrega

Requisitos: Docker Engine o Docker Desktop con Docker Compose, Git para clonar y
Make para los comandos abreviados. La primera ejecución necesita conexión para
descargar imágenes, dependencias y el modelo; la inferencia predeterminada es local.
También se documenta el [arranque sin Make](lab/README.md#sin-make).

Desde la raíz del repositorio:

```bash
cd lab
make run
```

El arranque utiliza `qwen2.5:3b` mediante Ollama. La velocidad y el consumo de memoria
dependen del equipo; las pruebas con múltiples repeticiones pueden ser largas en CPU.
`make run` genera de nuevo `lab/.env`: para conservar una configuración personalizada,
seguir el arranque manual de la guía de operación.

| Superficie | Dirección local | Función |
|---|---|---|
| VerdaBank | http://localhost:3000 | Aplicación bancaria simulada |
| Playground | http://localhost:3000/playground.html | Cargar fixtures y comparar respuestas |
| LLM-SOC | http://localhost:3000/soc.html | Consultar trazas, controles y documentación |
| API | http://localhost:8000/docs | Contrato interactivo de los endpoints |

## Recorrido para el evaluador

1. [Guía por comandos](DEMO_BY_COMMANDS.md): arranque, comprobaciones y una muestra de pruebas.
2. [Guía visual](DEMO_BY_FRONT.md): banco, Playground y SOC.
3. [Suite completa](DEMO_FULL_SUITE.md): matriz de ablaciones, evaluación e informes.
4. [Evidencias entregadas](docs/evidencias/README.md): resultados históricos, procedencia e integridad.
5. [Alcance y limitaciones](docs/alcance-y-limitaciones.md): qué se implementa y qué puede concluirse.
6. [Validación de entrega](docs/validacion-entrega.md): pruebas realizadas y sus resultados.

## Sistemas y metodología

- **Clara y VerdaBank**: agentes y operaciones bancarias simuladas con cuentas,
  movimientos y clientes sintéticos.
- **Proxy de defensa**: firmas de inyección, protección de PII, permisos de herramientas,
  auditoría de salida, guardia de fugas y controles documentales. El Input Sanitizer
  aplica firmas declarativas; su existencia no implica cobertura universal.
- **LLM-SOC**: muestra decisiones y eventos del proxy. La evaluación del resultado
  experimental se realiza en el análisis de las evidencias.
- **Suite de fixtures**: compara peticiones legítimas y ataques en endpoints y posturas
  declarados. Distingue efectos de herramientas, respuestas, errores técnicos y utilidad.
- **Agente de red-team**: genera y muta ataques con Ollama, con semillas propias,
  de Garak/HarmBench o de memoria de campañas anteriores.

La matriz incluye texto y documentos PDF, DOCX y XLSX. Los casos LLM10 de consumo
se ejecutan mediante su runner específico, descrito en la guía por comandos.

## Verificación y evaluación

Desde `lab/`:

```bash
make test
make smoke
# El juez semántico utiliza otro modelo, que hay que descargar antes de evaluar.
docker compose exec ollama ollama pull qwen3.5:9b
make suite REPEAT=5
```

La suite imprime un Run Folder. Con su nombre, ejecutar `make check-suite
RUN=<nombre> LEVEL=execution`, `make evaluate RUN=audit/runs/<nombre>` y
`make report RUN=audit/runs/<nombre>`. El [protocolo completo](DEMO_FULL_SUITE.md)
explica cómo leer cobertura, errores, seguridad, utilidad e incertidumbre.

## Estructura

```text
lab/
  backend/        API, agentes, defensas, configuración, fixtures y tests
  frontend/       Banco, Playground y SOC
  payloads/       Documentos de prueba y sus generadores
  scripts/        Ejecución, evaluación, calibración e informes
  redteam-agent/  Agente autónomo, semillas y tests
  audit/          Resultados de ejecuciones locales; fuera de Git
docs/
  ataques/        Taxonomía, análisis y playbooks
  defensas/       Diseño de controles
  adr/            Decisiones de arquitectura y metodología
  metricas/       Contrato de las métricas
  evidencias/     Anexo histórico con manifiesto de integridad
  reports/        Análisis y evidencia experimental documentada
```

[Operación del laboratorio](lab/README.md) · [Glosario](CONTEXT.md) ·
[Diseño del SOC](docs/soc/README.md) · [Historial de desarrollo](docs/historial-desarrollo.md)

## Alcance académico

Todos los datos bancarios son sintéticos. Los ataques están preparados para este
laboratorio controlado. Los modelos y las fuentes externas conservan sus propias
licencias; la procedencia de las semillas se documenta en el
[módulo de fuentes](lab/redteam-agent/sources/README.md).
