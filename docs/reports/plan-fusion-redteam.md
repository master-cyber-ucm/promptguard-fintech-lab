# Plan de fusión: `Red Team_/` (Norma) + `lab/redteam-agent/` (Daniel)

> Plan aprobado antes de implementar — ver
> [`plan-fusion-redteam-validacion.md`](plan-fusion-redteam-validacion.md) para qué
> se implementó realmente, qué se desvió del plan y por qué, y las instrucciones de
> reproducción manual.

## Veredicto rápido

**Sí, tiene sentido y es técnicamente viable sin reescribir nada de cero.** Los dos
proyectos no compiten por el mismo problema: `lab/redteam-agent/` es un **harness**
maduro (taxonomía, verificación estructural del juez, multi-turno real, integración
con el SOC/auditoría del lab) que le falta variedad de origen de prompts; `Red Team_`
aporta justo eso — dos **fuentes externas y académicamente citables** de prompts
(HarmBench vía PyRIT, y la cobertura de probes de Garak) — pero corriendo sobre un
harness más débil (sin verificación estructural, sin multi-turno real, sin
integración con el Run Folder/SOC del lab).

La fusión que más aprovecha ambos no es "juntar los archivos": es usar el harness de
Daniel como columna vertebral y conectarle las fuentes de Norma como **fuentes de
semillas intercambiables**, en el mismo punto de extensión que ya usan los tres
motores de evolución (`evolution/get_engine`).

Aviso de alcance: Garak **no está instalado ni en `requirements.txt`** de `Red Team_`
— solo existen dos ficheros de configuración (`garak_clara_config.json`,
`garak_run_config.yaml`). No hay código funcionando que lo invoque hoy. La parte de
PyRIT/HarmBench sí es código real y ejecutable (`run_redteam.py`, `clara_target.py`).
Esto cambia la estimación de esfuerzo: la vía HarmBench es "portar código que ya
funciona"; la vía Garak es "construir la integración desde el config, no desde código
que ya corre".

---

## Principio rector

`lab/redteam-agent/` se queda como la **columna vertebral única** de ejecución:

- Es el único de los dos que escribe Session Files reales vía el backend
  (`audit_repository.append_turn`), visibles en el SOC — cualquier cosa que no pase
  por `target_client.py` queda fuera del sistema de evidencia auditable del lab.
- Es el único con verificación estructural del veredicto contra `tools_used` real y
  contra verdad de terreno (`ground_truth.py`) — sin esto, cualquier prompt que se
  añada (de HarmBench o de Garak) hereda el mismo problema que ya se documentó:
  jueces LLM pequeños alucinando SUCCESS/FAILED sin relación con lo que pasó de
  verdad.
- Es el único con sesión multi-turno real contra `/chat/proxy` — `Red Team_`
  aplana los ataques multi-step en un solo mensaje (limitación declarada en su
  propio código).

Por tanto: **no se migra el harness de Norma, se migran sus fuentes de prompts al
harness de Daniel.** Esto no descarta su trabajo — al contrario, hace que sus
prompts de HarmBench/Garak se evalúen con el juez más riguroso que existe en el
proyecto, en vez del evaluador híbrido regex+LLM-de-una-palabra actual.

---

## Qué se conserva de cada uno, y a dónde va

| Pieza | Origen | Destino en la fusión |
|---|---|---|
| Taxonomía, orquestador, `AttackerBrain`, 3 motores de evolución, salvaguardas estructurales, modo caja-gris, Run Folder/SOC | Daniel | Se queda igual — es la columna vertebral |
| Dataset HarmBench (académico, no inventado) | Norma (`run_redteam.py`) | Nueva **fuente de semillas** (`sources/harmbench_source.py`) que alimenta `abrir_intento()` |
| Cobertura de probes de Garak (taxonomía externa de jailbreaks) | Norma (config, sin código aún) | Nueva fuente de semillas (`sources/garak_source.py`) — **construir desde cero**, ver Fase 3 |
| Evaluador híbrido regex + LLM de una palabra | Norma (`attack_loop.py::evaluate_attack`) | Las regex (`REFUSAL_PATTERNS`, `IBAN_PATTERN`, `TRANSFER_CONFIRM_PATTERNS`, `SYSTEM_LEAK_PATTERNS`) se fusionan como **pre-filtro barato** en `ground_truth.py`, antes de invocar al juez LLM — optimización de coste, no de rigor |
| `ClaraTarget`/`OllamaNativeTarget` (adaptadores PyRIT) | Norma | Se retiran — `target_client.py` y `OllamaClient` de Daniel ya cubren lo mismo con más rigor (audit_subdir, tools_used, latencia) |
| `PromptSendingOrchestrator` + `SelfAskTrueFalseScorer` (PyRIT) | Norma | Se retira el orquestador; el scorer se retira porque las 5 salvaguardas de `orchestrator.py`/`ground_truth.py` de Daniel son estrictamente más rigurosas |
| Loop adaptativo por mutación simple | Norma (`attack_loop.py`) | Se retira — subsumido por los 3 motores de evolución de Daniel (autorreflexivo/genético/taxonomía), que son más sofisticados |
| `learning_loop.py` (dedup por uuid) | Norma | Se retira — el Run Folder de Daniel ya es la fuente de verdad histórica; no hace falta un segundo almacén de memoria |
| Config de Garak (`.json`/`.yaml`) | Norma | Referencia para Fase 3, pero sin código que las use hoy |

---

## Arquitectura fusionada

```
lab/redteam-agent/
├── taxonomy.yaml                    ← sin cambios
├── attacker.py                      ← sin cambios (genera + juzga)
├── ground_truth.py                  ← + pre-filtro regex (fusión de Norma)
├── orchestrator.py                  ← sin cambios estructurales
├── target_client.py / soc_client.py ← sin cambios
├── cli.py / config.py               ← + flag --seed-source
├── evolution/
│   ├── self_reflect.py              ← sin cambios
│   ├── genetic.py                   ← sin cambios
│   └── taxonomy_guided.py           ← sin cambios
└── sources/                         ← NUEVO — fuentes de semillas externas
    ├── __init__.py                  ← get_source(nombre) -> SeedSource, mismo
    │                                    patrón que evolution/get_engine
    ├── harmbench_source.py          ← Fase 2, código ya probado por Norma
    └── garak_source.py              ← Fase 3, construir desde cero
```

Punto de integración concreto: `EvolutionEngine.abrir_intento()` ya es la interfaz
(`Protocol`) que decide el payload de apertura de cada Intento. Una `SeedSource` no
sustituye a un motor — lo **precede**: en el primer Intento (o en los primeros N)
usa un prompt semilla de HarmBench/Garak en vez de generarlo desde cero; a partir
de ahí, el motor de evolución configurado (autorreflexivo/genético/taxonomía) toma
el control para mutar esa semilla igual que ya hace con sus propios payloads. Así
la fuente externa hereda gratis: multi-turno real, verificación estructural,
Run Folder, SOC.

```python
# evolution/self_reflect.py (o un wrapper genérico "SeededEngine")
def abrir_intento(self, *, tecnica, historial, brain):
    if not historial and self._seed_source:
        semilla = self._seed_source.siguiente(tecnica)
        if semilla:
            return semilla
    # ... comportamiento actual sin cambios
```

---

## Fases

### Fase 1 — Pre-filtro regex barato (bajo esfuerzo, ganancia inmediata)

Fusionar `REFUSAL_PATTERNS` / `IBAN_PATTERN` / `TRANSFER_CONFIRM_PATTERNS` /
`SYSTEM_LEAK_PATTERNS` de `attack_loop.py` en `ground_truth.py`, como una función
`rechazo_evidente(respuesta) -> bool` que se consulta **antes** de llamar a
`brain.juzgar()` cuando el patrón es inequívoco (p.ej. rechazo explícito sin tools
invocadas) — ahorra llamadas a Ollama en campañas grandes sin tocar el rigor del
veredicto (las salvaguardas estructurales siguen aplicando igual sobre lo que sí
llega al juez).

- **DoD**: test unitario que confirma que un rechazo evidente no gasta una llamada
  a Ollama, y que los casos ambiguos siguen yendo al juez sin cambios de
  comportamiento respecto a hoy.
- Riesgo: ninguno relevante — es aditivo y no reemplaza el juez, solo evita
  invocarlo en el caso trivial.

### Fase 2 — Fuente de semillas HarmBench (esfuerzo medio, código ya probado)

Portar `load_seed_prompts()` de `run_redteam.py` a `sources/harmbench_source.py`,
usando solo la utilidad de dataset de PyRIT (`pyrit.datasets.fetch_harmbench_dataset`)
sin el resto del framework — o vendorizar el dataset filtrado como YAML/JSON estático
para no arrastrar `pyrit` como dependencia de todo el agente si el equipo prefiere
mantenerlo ligero (hoy solo depende de `httpx`/`pyyaml`).

Diseño: cada prompt de HarmBench (filtrado por categoría afín a la Técnica —
privacidad para `pii-harvesting`/`cross-context-leakage`, jailbreak/roleplay para
`directa`) se ofrece como semilla de apertura de un Intento nuevo; el resto del
Intento (turnos, juicio, salvaguardas) es exactamente el flujo actual sin ningún
cambio.

- **DoD**: `python cli.py --seed-source harmbench --techniques pii-harvesting`
  produce un Run Folder normal con al menos un Intento cuyo primer turno es un
  prompt de HarmBench, juzgado con las mismas 5 salvaguardas estructurales que
  cualquier otro Intento.
- Riesgo: `pyrit==0.8.1` fija una versión — validar que sigue disponible o
  vendorizar el subconjunto de prompts usado para no depender de un paquete pesado
  en producción del agente.
- Valor para el TFM: permite decir "las mismas salvaguardas frente a un dataset
  académico publicado, no solo frente a los propios fixtures" — refuerza la
  objetividad del capítulo de validación.

### Fase 3 — Fuente de semillas Garak (esfuerzo alto, construir desde cero)

A diferencia de la Fase 2, aquí no hay código que portar — solo dos ficheros de
config sin ejecutar. Dos sub-opciones, de menor a mayor esfuerzo:

**3a (recomendada primero) — extracción de prompts, sin correr el harness de Garak.**
Instanciar en un script offline las clases de probes de Garak que interesen
(jailbreak, promptinject, encoding) y volcar sus prompts generados a un YAML/JSON
estático, igual que se vendorizaría HarmBench. Se integra exactamente como la Fase 2
(`sources/garak_source.py`), sin añadir `garak` como dependencia del agente en
producción — solo como herramienta de generación de semillas, ejecutada una vez.

**3b (opcional, mayor alcance) — Garak como generador contra `TargetClient`.**
Escribir un plugin `Generator` de Garak (`garak.generators.base.Generator`, a
validar contra la versión exacta que se fije en `requirements.txt`, porque esa
API cambia entre versiones) que delegue las llamadas en `TargetClient.enviar(...)`,
para poder lanzar barridos completos de Garak (`garak --model_type ...`) contra
Clara real, con Session Files y `audit_subdir` correctos. Los veredictos de esos
barridos los daría Garak con sus propios detectores — se etiquetan como
`origen=garak-sweep`, deliberadamente **no** mezclados con los veredictos del juez
de Daniel (dos metodologías distintas, comparables lado a lado, no fusionadas en
una sola cifra).

- **DoD (3a)**: `python cli.py --seed-source garak --techniques directa` produce un
  Run Folder con semillas extraídas de al menos 2 familias de probes de Garak.
- **DoD (3b, opcional)**: un barrido `garak` completo produce un Run Folder con
  `origen=garak-sweep` visible en el SOC, sin romper el contrato de Run Folder
  existente (mismo `run.json`/`run.md`).
- Riesgo principal: la superficie de Garak es genérica (no bancaria) — hay que
  calibrar cuántos probes son relevantes al dominio VerdaBank antes de gastar tiempo
  de cómputo en probes irrelevantes.

### Fase 4 — CLI y config unificados (bajo esfuerzo)

Añadir a `config.py`:
```python
p.add_argument("--seed-source", dest="fuente_semillas", choices=("ninguna", "harmbench", "garak"), default="ninguna")
```
y `sources/__init__.py::get_source(nombre)` con el mismo patrón que
`evolution/get_engine`. Cero cambios de comportamiento si no se pasa el flag —
retrocompatible con las campañas actuales.

- **DoD**: `python cli.py --help` documenta el flag; sin `--seed-source`, el
  comportamiento es idéntico byte a byte al actual.

### Fase 5 — Reporting: trazabilidad de procedencia (bajo esfuerzo)

Añadir un campo `fuente` (`propio` / `harmbench` / `garak`) al `Intento` en
`models.py`, propagado a `run.json`/`run.md` por `reporting.py`. Permite, en el
capítulo del TFM, desglosar la tasa de bypass por procedencia del prompt —
argumento fuerte: "¿las defensas fallan más ante ataques inventados por el propio
equipo o ante ataques de un dataset académico/una herramienta externa?".

- **DoD**: `run.json` de una campaña mixta permite agrupar resultados por `fuente`
  sin tocar `analyze.py`/`report.py` del resto del lab (el contrato de Run Folder
  no cambia, solo se añade un campo informativo).

### Fase 6 — Retirar lo redundante, documentar lo histórico

`attack_loop.py`, `run_redteam.py`, `clara_target.py`, `ollama_native_target.py`,
`learning_loop.py` pasan a **archivo histórico** (se documentan en el capítulo del
TFM de Norma como la exploración que originó las Fases 2-3, no se borran del
repo — son evidencia de trabajo real y parte de la bitácora). El código vivo queda
solo en `lab/redteam-agent/`.

- **DoD**: un README en `Red Team_/` (o un ADR nuevo, siguiendo el patrón de
  ADR-0008) que explique que el proyecto fue absorbido por
  `lab/redteam-agent/sources/`, con el enlace a las Fases 2-3 como continuación.

---

## Orden recomendado y por qué

1. **Fase 1** primero — cero riesgo, gana algo ya.
2. **Fase 4** justo después (o en paralelo) — el flag vacío es el andamiaje que
   necesitan las Fases 2 y 3 para no invadir `orchestrator.py`.
3. **Fase 2** (HarmBench) — es la que más valor entrega por esfuerzo: código ya
   probado por Norma, dataset académico citable, cero trabajo de extracción.
4. **Fase 5** en paralelo a la 2 — sin `fuente` no se puede argumentar nada en el
   TFM sobre procedencia.
5. **Fase 3a** (extracción de semillas de Garak) — mismo patrón que la 2, pero hay
   que generar el YAML de semillas primero.
6. **Fase 3b** (Garak como generador completo) — opcional, solo si sobra tiempo:
   es la de mayor esfuerzo y la de mayor riesgo de API inestable entre versiones
   de Garak.
7. **Fase 6** al final, cuando 2 y 3a ya estén corriendo en campañas reales.

## Riesgos transversales

- **Dependencias**: si se vendoriza HarmBench/Garak como YAML estático en vez de
  mantener `pyrit`/`garak` como dependencias vivas, el agente sigue siendo tan
  ligero como hoy (`httpx`+`pyyaml`) — recomendado, salvo que el equipo quiera
  poder re-muestrear los datasets con nuevas versiones sin re-generar el YAML a mano.
- **Coordinación de autoría**: las Fases 2-3 dependen de que Norma participe (conoce
  el filtrado de HarmBench y la intención original de Garak) — no es solo trabajo
  de Daniel portando código ajeno sin contexto.
- **Calibración de falsos positivos/negativos**: los prompts de HarmBench/Garak no
  fueron escritos para el dominio bancario — es esperable una tasa más alta de
  Intentos "no aplicables" (el modelo atacante puede no saber adaptar un prompt
  genérico de HarmBench al escenario VerdaBank). Vale la pena revisar manualmente
  la primera campaña de la Fase 2 antes de generalizar.
- **Tests existentes**: `lab/redteam-agent/tests/` ya cubre `attacker.py`,
  `ground_truth.py`, `ejercicio_writer.py`, `analyze_campania.py` — cada fase debe
  añadir sus propios tests en ese mismo directorio, no un `tests/` paralelo.
