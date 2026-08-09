# daniel-tfm — Defensa de cuatro vectores

Workspace del capítulo de **Daniel Ortiz** para el TFM colectivo **PromptGuard FinTech**
(Máster en Ciberseguridad, UCM).

**Alcance:** implementación, medición y análisis de la defensa de cuatro vectores del catálogo,
seleccionados uno por nivel del ranking de dificultad.

| # | Vector | Dificultad | Estado inicial | Aportación |
|---|---|---|---|---|
| 2 | LLM02 — PII Harvesting | ★★☆☆☆ | ❌ esqueleto no-op | **PII Shield completo** (entrada + salida) |
| 4 | LLM07 — System Prompt Leakage (API key) | ★★★☆☆ | ⚠️ evadible con un guion | **Output Auditor endurecido** |
| 6 | LLM06 — Confused Deputy | ★★★★☆ | ✅ cubierto | Regresión + contrafactual |
| 9 | LLM01 — Injection Indirecta (documento) | ★★★★★ | ⚠️ solo eje instrucción | **Cierre del cruce documento × PII** |

## Por dónde empezar

| Si quieres… | Lee |
|---|---|
| El encuadre y las reglas de trabajo | [`00-INSTRUCCIONES.md`](./00-INSTRUCCIONES.md) |
| La prosa para el documento final | [`CAPITULO.md`](./CAPITULO.md) |
| **Por qué los casos 2 y 4 daban 0% y los payloads que sí explotan** | [`01-vectores/investigacion-0pct/`](./01-vectores/investigacion-0pct/README.md) |
| Qué defendía el lab antes (la medición) | [`01-vectores/estado-inicial.md`](./01-vectores/estado-inicial.md) |
| Qué se construyó y por qué así | [`02-defensa/README.md`](./02-defensa/README.md) |
| Cómo se midió y cómo leer las cifras | [`02-defensa/evidencia/README.md`](./02-defensa/evidencia/README.md) |
| Lo normativo específico | [`03-normativa/README.md`](./03-normativa/README.md) |
| Lo que salió mal por el camino | [`bitacora/BITACORA.md`](./bitacora/BITACORA.md) |
| El checklist por fases | [`ROADMAP.md`](./ROADMAP.md) |

## Relación con el resto de la documentación del repo

Este workspace **no duplica** ninguno de los dos cuerpos documentales existentes:

```
docs/ataques/     → qué amenaza existe        (taxonomía, threat model, casos reales)
docs/defensas/    → qué control habría que construir (invariantes, arquitectura, límites)
daniel-tfm/       → qué se construyó, qué mide y qué salió
```

> **Dependencia pendiente:** `docs/defensas/` todavía no está en esta rama — vive en el PR
> [#6](https://github.com/master-cyber-ucm/promptguard-fintech-lab/pull/6), abierto contra `main`.
> Los enlaces de este workspace hacia esa carpeta resolverán cuando ese PR se integre. `docs/ataques/`
> sí está presente y sus enlaces funcionan.

Cuando este capítulo necesita una afirmación de los otros dos, la enlaza. Cuando los **contradice**
—porque la implementación reveló algo que el diseño sobre el papel no había previsto— lo dice
explícitamente y explica por qué. Eso es contenido propio, no duplicación.

## Resultados en una página

| Caso | Fuga real sin defensa | Fuga real con defensa | Falsos positivos |
|---|---|---|---|
| 2 — PII Harvesting | 0% * | **0%** | 0/2 |
| 4 — System Prompt Leakage | 0% * | **0%** | 0/1 |
| 6 — Confused Deputy | **100%** | **0%** | 0/4 |
| 9 — Injection Indirecta (documento) | **100%** | **0%** | 0/3 |

`*` El modelo ya rechaza esos payloads por su cuenta (alignment implícito). La aportación de la
defensa ahí es determinismo, coste (bloqueo en 0 s sin llamar al modelo) y trazabilidad.

- **150 tests en verde** (63 preexistentes + 87 nuevos).
- **Un hallazgo metodológico:** los cuatro vectores no eran cuatro problemas. Las defensas del
  lab cubrían el eje *instrucción* y el eje *autorización*; el hueco estaba entero en el eje
  *dato que sale*.
- **Tres errores de implementación propios**, dos de ellos falsos positivos que solo se
  manifiestan contra tráfico legítimo (el patrón de teléfono casando dentro de un IBAN; dos
  importes redondos de cliente contando como volcado de configuración).
- **Tres artefactos de medición que afectan a todo el proyecto:** los eventos de los fixtures se
  disparan con la invocación de una tool (aunque el Gatekeeper la deniegue, o aunque ni siquiera
  retorne) y con la mención del *nombre* de un secreto (aunque la respuesta sea un rechazo). En
  configuraciones defendidas sobrestiman el éxito de los ataques. El capítulo introduce una
  métrica de **fuga real** que no depende del criterio del fixture.
- **Deuda encontrada en el trabajo compartido:** 8 tests rotos en la rama base y
  `banking_patterns.yaml` declarado pero nunca conectado a código.

## Reproducir

```bash
# Tests (no requieren LLM)
cd lab/backend && python -m pytest tests/ -q

# Evidencia contra modelo real
cd lab/backend && LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://localhost:11434/v1 \
  OLLAMA_MODEL=qwen2.5:3b OLLAMA_API_KEY=ollama \
  python -m uvicorn src.main:app --host 127.0.0.1 --port 8010 &
cd daniel-tfm/02-defensa/evidencia && python ejecutar_evidencia.py --puerto 8010
```
