# PR 5 — Diseñar baseline/full comparables y añadir ablaciones

**Estado:** propuesta de diseño experimental  
**Prioridad:** P1 — necesaria para afirmaciones causales  
**Ejecución:** `20260831_193511_qwen2.5-3b`  
**Dependencias:** después de PR 1; coordinar fórmulas con PR 4 y contrato documental con PR 7

## Resumen ejecutivo

El efecto dañino observado pasa de 116/365 en `proxy-baseline` a 2/365 en `proxy-full`: diferencia pareada descriptiva de −31,2 pp, IC 95 % [−39,7; −23,0]. No puede atribuirse causalmente al bundle porque las posturas difieren también en el factor no defensivo `vulnerable`, tienen baja conclusividad y no existen ramas de un solo control.

Esta PR diseña la siguiente ejecución para responder: «¿funciona el bundle frente al mismo sistema sin controles?» y «¿qué aporta marginalmente cada control?». La arquitectura funcional y el experimento son capas distintas: PR 7 integra el documento opcional en los endpoints existentes; esta PR define pares comparables dentro de una superficie y un pipeline controlados. Que dos endpoints acepten el mismo documento no los convierte automáticamente en un par causal si lo procesan de forma diferente.

## Problemas que resuelve

1. Baseline/full no son contrafactuales comparables.
2. `vulnerable` modifica múltiples comportamientos fuera de los flags declarados.
3. `defense_marginals` está vacío por falta de ablaciones.
4. La latencia compara cohortes permitidas distintas.
5. Faltan cobertura documental por endpoint y system-prompt leakage directo en proxy.
6. Reproducibilidad débil: árbol sucio, digest ausente y seed no garantizada.
7. Se confunden endpoints de producto con posturas experimentales.

## Evidencia primaria

- [run.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/run.json): `delta_pct=-31.2`, 73 clusters y 365 observaciones.
- El mismo artefacto fija `causal_comparison.proxy-full.comparable=false`: factor `vulnerable` distinto y cobertura evaluable 39,5 %/49,2 %.
- `defense_marginals={}` confirma que no hay comparación de un control cada vez.
- Las posturas efectivas muestran baseline con `vulnerable=true` y full con `false`.
- [provenance.json](../../lab/audit/runs/20260831_193511_qwen2.5-3b/provenance.json): commit `3a9a46e…`, 199 archivos sucios, `diff_sha256=null`, digest del modelo nulo y `seed_honored=false`.
- El run no incluye capacidad documental en los endpoints existentes ni los once fixtures descritos en PR 4.

## Interpretación defendible hoy

La asociación es grande y justifica una réplica. No demuestra que las defensas causen por sí solas la reducción ni cuánto aporta cada componente. La supresión de ARR/RRR por el verificador es correcta.

## Diseño propuesto

### Arquitectura de endpoints frente a pares experimentales

La arquitectura futura conserva `simple-prompt`, `complex-prompt`, `complex-with-context` y `proxy`, todos con documento opcional conforme a PR 7. `/complex-with-document` deja de ser el destino conceptual y no se usa para definir una modalidad experimental.

Los endpoints baseline incorporan el contenido documental sin defensas documentales específicas, salvo controles técnicos mínimos; `proxy` ejecuta extracción, sanitización, detección estructural, separación semántica/tool framing y demás defensas aplicables antes de componer la petición al modelo. Esta diferencia sirve para medir el comportamiento real entre superficies, pero sus resultados son descriptivos salvo que el diseño controle explícitamente todos los factores divergentes.

Un par causal baseline/full se construye mediante posturas sobre el mismo endpoint y pipeline controlado, no escogiendo dos endpoints distintos solo porque acepten el mismo archivo. El plan identifica por separado `endpoint`, `pipeline_fingerprint` y `defense_vector`.

### Par baseline/full controlado

Ambas posturas comparten endpoint/pipeline, transporte, extracción y representación documental cuando aplique, prompt, contexto, catálogo/schema de tools, policy no defensiva, modelo, parámetros, budgets, timeouts, fixtures, bloques, repeticiones, infraestructura y código. Solo cambia el vector de controles bajo estudio. El perfil no dependerá de un interruptor global `vulnerable`; se compararán fingerprints efectivos.

La equivalencia fija prompt de sistema y usuario, configuración, modelo, contexto de confianza, herramientas y parámetros de inferencia. Permite diferenciar deliberadamente el pipeline documental baseline del pipeline protegido de `proxy` únicamente cuando esa diferencia sea el tratamiento declarado. En ese caso no se atribuye el delta a una defensa individual ni se mezcla con ablaciones que exigen pipeline común.

### Matriz de ablaciones

| Postura | Sanitizer | PII | Gatekeeper | Auditor | Leak guard |
|---|---:|---:|---:|---:|---:|
| baseline | 0 | 0 | 0 | 0 | 0 |
| full | 1 | 1 | 1 | 1 | 1 |
| only-input | 1 | 0 | 0 | 0 | 0 |
| only-pii | 0 | 1 | 0 | 0 | 0 |
| only-gatekeeper | 0 | 0 | 1 | 0 | 0 |
| only-auditor | 0 | 0 | 0 | 1 | 0 |
| only-leak | 0 | 0 | 0 | 0 | 1 |

Si un control depende de otro, se modela como ablación condicionada; no se finge independencia. Añadir `full-minus-one` si el presupuesto permite estudiar interacciones.

### Bloques e incertidumbre

Mantener bloqueo aleatorizado por fixture/repetición. Dimensionar repeticiones antes del run usando efecto mínimo relevante y variabilidad observada. Intervalos agrupados por fixture y corrección por multiplicidad para marginales. NIST recomienda TEVV repetible, test sets/métricas documentados, benchmarks, incertidumbre y límites de generalización ([AI RMF — Measure](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)).

### Modalidad documental

Crear pares documentales dentro de los endpoints existentes y del mismo pipeline experimental. El mismo archivo, mensaje, contexto, herramientas, modelo y configuración se reutilizan entre ramas; se registran hash del archivo, extractor/representación, pipeline y vector de defensas.

Los once fixtures huérfanos y los ataques directos de extracción del prompt contra `proxy` entran en el plan conforme a la aplicabilidad de PR 4. Chat sin documento y entrada con documento son modalidades distintas; tampoco se equiparan causalmente los pipelines baseline y `proxy` si cambian extracción, framing o composición además de los controles estudiados.

### Latencia pareada

Medir sobre el mismo caso lógico y etapa, separando recepción/extracción, pre-modelo, inferencia, post-modelo, tools y autorización externa. Percentiles de conjuntos permitidos distintos siguen siendo descriptivos.

### Reproducibilidad

Gate previo: commit limpio; diff hash o cero cambios; digest de modelo/juez; hashes de prompts, fixtures, documentos, policy y evaluador; versión del extractor; imagen/dependencias fijadas; no determinismo declarado; plan sellado antes de la primera petición.

## Alternativas descartadas

- `simple-prompt` frente a `proxy` como par causal directo: cambia demasiados factores, aunque ambos sean superficies válidas de producto.
- `/complex-with-document` como target experimental permanente: contradice la integración transversal de PR 7.
- `vulnerable` como equivalente a controles off: el run demuestra efectos laterales.
- Solo tasas agregadas: pierde pareado y variabilidad.
- Todas las 2⁵ combinaciones sin priorizar: coste alto; first-order/full-minus-one responden antes.

## Pruebas y gates

- Fingerprints fallan si baseline/full difieren fuera del tratamiento declarado.
- Cada postura cambia solo flags declarados.
- El mismo documento y entradas lógicas producen hashes de entrada equivalentes entre ramas.
- El reporte distingue comparación arquitectónica descriptiva de par experimental causal.
- Dry-run con cero huérfanos injustificados.
- Estimación previa de coste/duración y smoke estratificado.
- Abort gate si error o inconclusividad excede umbral temprano.

## Criterios de aceptación

- `causal_comparison.comparable=true` antes de efectos causales.
- Baseline/full solo difieren en el tratamiento documentado.
- Comparación válida por control o dependencia documentada.
- La modalidad documental usa los endpoints existentes y tiene pares propios; no depende de `/complex-with-document`.
- Prompt, configuración, modelo, contexto y herramientas permanecen equivalentes en toda comparación que mida transporte, procesamiento o defensas.
- Las diferencias deliberadas del pipeline documental quedan fingerprintadas y limitan el claim causal correspondiente.
- `SYSTEM_LEAK` directo está representado en proxy.
- Latencia causal usa pares; lo demás se etiqueta descriptivo.
- Estado limpio y hashes completos.

## Fuera de alcance

La PR entrega diseño, perfiles, validadores y plan; lanzar la campaña requiere aprobación de coste/duración. El contrato de entrada y los cambios de frontend pertenecen a PR 7. Afinar utilidad pertenece a PR 6.
