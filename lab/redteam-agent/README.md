# Agente de red-team

> Primera sesión de campañas reales, con auditoría de cada hallazgo contra la
> evidencia (no solo el juicio del agente): **[HALLAZGOS-SESION-20260816.md](HALLAZGOS-SESION-20260816.md)**.
> Un hallazgo confirmado (Excessive Agency), tres bugs corregidos, y una limitación
> central sin resolver (el juez local de 3B no es fiable para todas las técnicas).
>
> Plan de excelencia derivado de esos hallazgos, con DoD y test por punto:
> **[docs/reports/plan-excelencia-redteam-y-defensas.md](../../docs/reports/plan-excelencia-redteam-y-defensas.md)**.
> Implementación P0/P1 y cierre del ciclo (`acciones-no-autorizadas` pasó de superada a
> contenida): **[HALLAZGOS-SESION-20260817.md](HALLAZGOS-SESION-20260817.md)**.

Módulo de aprendizaje: un agente autónomo e iterativo que ataca el pipeline de
defensa del lab (`/chat/proxy` por defecto) generando y mutando payloads en vivo,
en vez de reproducir los 108 fixtures estáticos de `run_attack_suite.py`. Construido
desde cero sobre Ollama — ver `docs/adr/0008-redteam-agent-desde-cero.md` para el
porqué, y `CONTEXT.md` § "Agente de red-team" para el vocabulario (Campaña, Ejercicio,
Intento, Objetivo, Motor de evolución, Modo, Modelo atacante).

## Requisitos

- El stack del lab corriendo (`make run` desde `lab/`, o ya levantado).
- Un modelo Ollama para el Modelo atacante, ya descargado — por defecto `qwen3.5:9b`
  (más capaz que `qwen2.5:3b`, que es el modelo de Clara en el lab por defecto).
- Dependencias Python: `pip install -r requirements.txt` (`httpx` + `PyYAML`, nada
  más — deliberadamente ligero, ver `sources/README.md` § por qué las fuentes de
  semillas externas no añaden nada aquí).

## Uso

```bash
cd lab/redteam-agent
python cli.py                                   # proxy defendido, caja negra, motor autorreflexivo, 20 intentos/ejercicio
python cli.py --vulnerable                       # control: mismo target, defensas OFF
python cli.py --mode caja-gris                   # lee también los Analysis Events del SOC
python cli.py --engine genetico --max-attempts 12
python cli.py --engine taxonomia
python cli.py --techniques directa cross-context-leakage   # subconjunto de la taxonomía
python cli.py --attacker-model llama3.1:8b
python cli.py --seed-source garak                          # abre cada Ejercicio con una semilla externa si existe
```

Ver todas las flags: `python cli.py --help`.

## Qué produce

Un Run Folder normal, con `origen=redteam-agent` visible en el SOC:

```
lab/audit/runs/{timestamp}_redteam-agent/
├── directa/{timestamp}_{session_id}.md              ← Session Files (los escribe el backend)
├── cross-context-leakage/...
├── ...
├── run.json                                          ← Informe de Campaña, estructurado
└── run.md                                            ← Informe de Campaña, legible
```

## Alcance de v1 — decisiones explícitas, no recortes silenciosos

- **6 de las 7 técnicas del catálogo.** `indirecta-documento` (ataque #7, LLM01) queda
  fuera: requiere generar documentos adversarios (PDF/DOCX/XLSX) en vivo, y el lab ya
  tiene un motor de mutación de PDF dedicado en `henri-tfm/01-ataque/payloads/`.
  Combinarlo es trabajo futuro.
- **Catálogo de tácticas del motor `taxonomia` es genérico**, no una lista por técnica
  (`evolution/taxonomy_guided.py::TACTICAS`) — autorar tácticas específicas por técnica
  es trabajo futuro si el motor genérico no converge bien.
- **Los Objetivos de `taxonomy.yaml`** se escribieron a mano una vez, con fuente en
  `docs/ataques/`, siguiendo el mismo user_id atacante (`usr_001`) contra el mismo
  usuario objetivo (`usr_002`) en todas las técnicas cross-usuario.

## Fuentes de semillas externas

`--seed-source garak` conecta payloads reales de probes de [Garak](https://github.com/NVIDIA/garak)
(no generados por el modelo atacante) como apertura del primer Intento de cada
Ejercicio — resultado de fusionar este agente con las fuentes externas que exploraba
`Red Team_/` (PyRIT/HarmBench, Garak). Ver
[`sources/README.md`](sources/README.md) para el diseño, el mapeo curado
Técnica↔probe, y por qué HarmBench se evaluó y se descartó como Fuente (dataset de
generación de contenido dañino, no de manipulación interactiva del agente — mapeo
forzado sin relación con lo que miden las Técnicas). Historial completo de la
decisión y las pruebas realizadas:
[`docs/reports/plan-fusion-redteam.md`](../../docs/reports/plan-fusion-redteam.md) y
[`docs/reports/plan-fusion-redteam-validacion.md`](../../docs/reports/plan-fusion-redteam-validacion.md).

## Diseño

- `taxonomy.yaml` — el harness: 6 Ejercicios, cada uno con su Objetivo en lenguaje
  natural y su tipo (`single`/`multi` turno).
- `attacker.py::AttackerBrain` — el Modelo atacante: genera payloads y **juzga sus
  propios intentos** (SUCCESS/CONTINUE/FAILED) con memoria acotada al Ejercicio en
  curso — nunca cruza a otro Ejercicio.
- `evolution/` — los tres Motores de evolución acordados, intercambiables por
  `--engine`: `self_reflect.py` (PAIR/TAP), `genetic.py` (población + fitness +
  cruce), `taxonomy_guided.py` (catálogo de tácticas acotado). `SeededEngine`
  envuelve cualquiera de los tres con una Fuente de semillas externa (`sources/`,
  `--seed-source`) sin modificarlos — ver `sources/README.md`.
- `orchestrator.py` aplica un atajo barato antes de invocar al juez LLM cuando
  `ground_truth.py::parece_rechazo()` ya es inequívoco y no hay tool confirmada
  (fusión con el evaluador híbrido de `Red Team_/attack_loop.py` — ahorra llamadas a
  Ollama sin tocar el rigor del veredicto, ver `docs/reports/plan-fusion-redteam-validacion.md`).
- `target_client.py` / `soc_client.py` — hablan con el backend del lab y, en Modo
  caja gris, con la API de lectura del SOC. Nunca escriben Session Files
  directamente: eso lo sigue haciendo el backend (`audit_repository.append_turn`),
  igual que para cualquier otro Turn.
- `orchestrator.py` / `reporting.py` — el bucle de Campaña y el Informe de Campaña
  (mismo formato `run.json`/`run.md` que un Run Report, generado por el agente en
  vez de por `analyze.py` — no hay Fixture Indicators que cargar).
