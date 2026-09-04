# Matriz de ablaciones y gate de reproducibilidad para baseline/full

Estado: **aceptado** (perfiles); **gate retirado 2026-09-02** (ver
[pr-11-gate-de-arbol-limpio-por-defecto.md § Corrección posterior](../reports/pr-11-gate-de-arbol-limpio-por-defecto.md#corrección-posterior-2026-09-02--el-gate-se-retira));
**decisión diferida documentada** (desacoplar `vulnerable` de las comparaciones
causales — ver Consequences).

## Contexto

`causal_comparison` (report.py) ya calcula un delta pareado entre `proxy-baseline` y
cada postura defendida, y `TargetPosture.comparable_fingerprint`
(`backend/src/models/posture.py`) ya rechaza la comparación cuando los dos targets
difieren en algo que no sea uno de los `DEFENSE_CONTROLS` declarados — el validador
existe y funciona: es precisamente el que marcó `causal_comparison.proxy-full.comparable
=false` en la ejecución `20260831_193511_qwen2.5-3b`, citada en
[PR 5](../reports/pr-05-baseline-full-y-ablaciones.md), porque `vulnerable` difiere
entre baseline (`true`) y full (`false`) y ese campo no está en `DEFENSE_CONTROLS`.

El problema no es que falte un validador — es que hoy no existe ninguna forma de que
baseline y full compartan `vulnerable` y sigan siendo dos posturas realmente
distintas: `vulnerable=True` en `chat.py::chat_proxy` no solo apaga los 5 controles
declarados, también condiciona protecciones de denegación de servicio (§LLM10), el
bypass de propiedad de cuenta (`enforce_gatekeeper`) y ramas de `leak_guard`/`pii_shield`
fuera de los flags declarados (`request.vulnerable` aparece en más de 15 condicionales
de `chat.py`). `defense_marginals` está vacío porque nunca ha corrido más que
baseline/full — no hay ramas `only-*` que ejecutar.

## Decisión

1. **Matriz de ablaciones** (`chat.py::chat_proxy` `profiles`, `run_attack_suite.py`
   `REQUESTED_CONTROLS`/`PROXY_PROFILES`): se añaden `only-input`, `only-pii`,
   `only-gatekeeper`, `only-auditor`, `only-leak`. Los cinco fijan `vulnerable=False`
   —igual que `full`— y activan un único control declarado, así que son comparables
   entre sí y contra `full`/`baseline` en los cinco flags que `comparable_fingerprint`
   ya vigila. `only-leak` actúa también sobre `tool_gatekeeper` porque `leak_guard`
   está condicionado a él en el pipeline (`defensa_leak_guard and defensa_tool_gatekeeper
   and not request.vulnerable`): es una ablación condicionada, documentada como tal,
   no una independencia fingida (el propio informe descarta "todas las 2⁵ combinaciones
   sin priorizar" — de-primer-orden y las condicionadas conocidas responden antes).
2. **Gate de reproducibilidad accionable** *(retirado 2026-09-02 — ver nota de
   Estado arriba)*: `--require-clean-tree` en `run_attack_suite.py` convertía el
   aviso histórico de árbol sucio (que solo imprimía una advertencia y
   continuaba) en un abort previo a abrir tráfico. Se decidió que esa dependencia
   no aportaba valor suficiente a este proyecto (laboratorio de un único
   investigador) frente a su coste (suites abortadas por ficheros sucios ajenos
   al código evaluado); queda solo el aviso pasivo, sin abortar. El resto del
   gate que pide el informe —digest de modelo/juez, hashes de fixtures/policy/
   evaluador, plan sellado antes de la primera petición— ya existe en
   `provenance.build()`/`artifact_digests()` y se persiste en `provenance.json` antes de
   la primera request; no requería cambio de código, solo confirmarlo (ver Consequences).

## Considered Options — desacoplar `vulnerable`

- **Eliminar `vulnerable` y expresar baseline como los 5 flags en `False`, ajustando
  cada condicional que hoy lee `request.vulnerable` para que dependa solo de flags
  declarados** (elegida para el diseño, diferida para la implementación): es la única
  opción que hace a baseline/full comparables por construcción en vez de solo
  detectarlos como no comparables. Requiere auditar y reescribir más de 15 puntos de
  `chat.py` que hoy acoplan protección DoS, `enforce_gatekeeper` y `leak_guard`/
  `pii_shield` a un interruptor global, cada uno con su propia superficie de prueba
  (rate limiting, ownership bypass). El riesgo de regresión en una ruta de seguridad
  activa (autorización, DoS) sin ventana para regresión completa es alto; se prioriza
  documentar el mapa exacto de condicionales afectados (arriba) para que el PR que lo
  ejecute no tenga que redescubrirlos.
- **Mantener `vulnerable` pero excluirlo de `comparable_fingerprint`** (descartada):
  haría "comparables" baseline/full artificialmente, ocultando exactamente el defecto
  que el informe denuncia — es debilitar el validador, no arreglar el sistema medido.
- **Mantener el estado actual y solo documentar el bloqueo** (parcialmente elegida
  como paso intermedio): el validador ya produce el resultado correcto
  (`comparable=false`); lo que cambia en este PR es que ahora hay ablaciones que SÍ son
  comparables entre sí (ninguna usa `vulnerable=True`), así que `defense_marginals` deja
  de estar vacío para ellas aunque el par baseline/full siga bloqueado hasta que se
  ejecute la opción elegida arriba.

## Consequences

- `defense_marginals` puede calcularse ya para cualquier par de perfiles `only-*`/`full`
  (ninguno usa `vulnerable=True`); baseline sigue bloqueado hasta que se desacople
  `vulnerable`, correctamente, porque ese es el defecto real.
- Lanzar la matriz completa (7+ posturas × repeticiones × fixtures) es una campaña
  nueva con su propio coste/duración — **no se ejecuta en este PR** (el propio informe
  lo excluye explícitamente de su alcance). `--require-clean-tree` deja el gate listo
  para cuando se apruebe.
- Añadir `document-baseline`/`document-full` comparables y ataques directos de
  `SYSTEM_LEAK` contra el proxy (los otros dos pendientes del informe) requiere
  fixtures nuevos en el catálogo (`backend/tests/fixtures/`), no solo código de
  runner/backend — se deja como trabajo de catálogo, fuera del alcance de código de
  este PR.
- El desacoplamiento de `vulnerable` queda como el primer ítem de trabajo del
  siguiente PR de esta serie, con el mapa de condicionales de `chat.py` ya
  identificado arriba en vez de tener que re-auditar el fichero desde cero.
