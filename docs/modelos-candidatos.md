# Modelos candidatos para la evaluación

Lista de modelos a ejecutar con la suite de ataques PromptGuard. Organizados por proveedor y prioridad para la fase de evaluación final (CPU + Docker).

---

## Criterios de selección

| Criterio | Detalle |
|----------|---------|
| Coste | Solo proveedores gratuitos (sin coste por token) |
| Evaluación final | La suite corre en CPU dentro de Docker — los modelos locales deben terminar en tiempo razonable |
| Cardinality mínima | 61 fixtures × 1 run = **61 requests** por modelo |
| Cardinality completa | 61 fixtures × 3 runs (o concurrencia 3) = **183 requests** |
| Rate limit mínimo | > 183 RPD para soportar la suite completa en un día |

---

## Proveedor 1 — Ollama (local)

Modelos descargados y ejecutados localmente vía `ollama serve`. Sin rate limits. Latencia depende del hardware del evaluador.

**Referencia de velocidad estimada en CPU (Docker, sin GPU):**
- 1B–3B: ~1–3 min por fixture → suite completa en ~1–3h
- 7B–9B: ~5–15 min por fixture → suite completa en ~5–15h (overnight viable)
- 12B–14B: >15 min por fixture → solo para validación puntual, no suite completa

### Tier A — Ultraligero (1B–4B) · Prioridad alta para evaluación final

| Modelo | Tag Ollama | Tamaño | Contexto | Notas |
|--------|-----------|--------|----------|-------|
| Llama 3.2 | `llama3.2:1b` | 1B | 128K | Candidato más ligero; referencia de comportamiento con mínimos recursos |
| Llama 3.2 | `llama3.2:3b` | 3B | 128K | Mejor calidad/velocidad en 3B; 74M pulls — muy popular |
| Qwen 2.5 | `qwen2.5:3b` | 3B | 128K | Buena calidad multilingual (español); familia madura |
| Qwen 3 | `qwen3:1.7b` | 1.7B | 32K | Reasoning nativo; mínima huella de memoria |
| Phi-4 Mini | `phi4-mini:3.8b` | 3.8B | 128K | Soporta function calling; muy eficiente por parámetro |
| Gemma 3 | `gemma3:1b` | 1B | 32K | Solo texto; Google; buena base para comparar |

### Tier B — Mediano (7B–9B) · Prioridad media

| Modelo | Tag Ollama | Tamaño | Contexto | Notas |
|--------|-----------|--------|----------|-------|
| Qwen 3 | `qwen3:8b` | 8B | 128K | **Modelo actual del lab** (`qwen3.5:9b`); referencia base |
| Llama 3.1 | `llama3.1:8b` | 8B | 128K | Referencia clásica 8B; ampliamente estudiado en seguridad |
| Mistral 7B | `mistral:7b` | 7B | 32K | 30.5M pulls; referencia histórica |
| Qwen 2.5 | `qwen2.5:7b` | 7B | 128K | Versión estable de la familia Qwen |
| Gemma 3 | `gemma3:4b` | 4B | 128K | Buena relación calidad/tamaño |

### Tier C — Grande (12B–14B) · Solo validación puntual (no suite completa en CPU)

| Modelo | Tag Ollama | Tamaño | Contexto | Notas |
|--------|-----------|--------|----------|-------|
| Qwen 2.5 | `qwen2.5:14b` | 14B | 128K | Techo de calidad local permitido; referencia para comparar vs. modelos online |
| Qwen 3 | `qwen3:14b` | 14B | 128K | Razonamiento avanzado; explorar si el thinking mejora la resistencia a ataques |
| Gemma 3 | `gemma3:12b` | 12B | 128K | 12B Google; comparación familiar Gemma |

---

## Proveedor 2 — OpenRouter (online, gratuito)

API OpenAI-compatible. Ya soportado por el backend (`LLM_PROVIDER=openrouter`).

### Rate limits gratuitos

| Tier | RPM | RPD | ¿Suficiente para la suite? |
|------|-----|-----|---------------------------|
| Sin créditos | 20 | 200 | ⚠️ 1 run OK (61 < 200), 3 runs NO (183 > 200) |
| Con $10 créditos | 20 | 1000 | ✅ 3 runs OK (183 < 1000); 3× seguidas NO (549 > 1000) |

> Para ejecutar la suite **3 veces seguidas o con concurrencia 3**, se necesitan créditos ($10). Con créditos: hasta ~5 runs diarios (5 × 183 = 915 < 1000).

### Modelos candidatos

| Modelo | ID OpenRouter | Tamaño | Contexto | Notas |
|--------|--------------|--------|----------|-------|
| Llama 3.2 3B | `meta-llama/llama-3.2-3b-instruct:free` | 3B | 131K | Contraparte online del tier local 3B; comparación directa |
| LFM 1.2B Instruct | `liquid/lfm-2.5-1.2b-instruct:free` | 1.2B | 33K | El modelo más pequeño disponible en OpenRouter gratis |
| Nemotron Nano 9B | `nvidia/nemotron-nano-9b-v2:free` | 9B | 128K | NVIDIA; buena opción en el rango 7B-9B online |
| GPT-OSS 20B | `openai/gpt-oss-20b:free` | 20B | 131K | Frontera superior del rango; OpenAI open-source |
| Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct:free` | 70B | 131K | Fuera del rango de tamaño pero interesante como referencia de calidad alta |

---

## Proveedor 3 — Groq (online, gratuito) · Recomendado añadir

API OpenAI-compatible con hardware LPU (inferencia muy rápida). **No requiere tarjeta de crédito.** Integración inmediata con el backend usando `LLM_PROVIDER=custom` + `LLM_BASE_URL=https://api.groq.com/openai/v1`.

### Rate limits

| Modelo | RPM | RPD | ¿Suficiente para la suite? |
|--------|-----|-----|---------------------------|
| `llama-3.1-8b-instant` | 30 | 14.400 | ✅ 3× seguidas + concurrencia 3 sin problema |
| `openai/gpt-oss-20b` | 30 | 1.000 | ✅ 3 runs (549 < 1000) |
| `qwen/qwen3-32b` | 60 | 1.000 | ✅ 3 runs; RPM alto (útil para concurrencia) |
| `meta-llama/llama-4-scout-17b-16e-instruct` | 30 | 1.000 | ✅ 3 runs; Llama 4 |

### Modelos candidatos

| Modelo | ID Groq | Tamaño | RPD | Notas |
|--------|---------|--------|-----|-------|
| Llama 3.1 8B Instant | `llama-3.1-8b-instant` | 8B | 14.400 | **El más cómodo para la suite**; mismo tamaño que `llama3.1:8b` local → comparación directa online vs. local |
| GPT-OSS 20B | `openai/gpt-oss-20b` | 20B | 1.000 | Disponible también en OpenRouter; comparar latencia entre proveedores |
| Qwen 3 32B | `qwen/qwen3-32b` | 32B | 1.000 | Fuera del rango local pero interesante como referencia de calidad alta online |
| Llama 4 Scout | `meta-llama/llama-4-scout-17b-16e-instruct` | 17B | 1.000 | MoE de Llama 4; comportamiento diferente a modelos densos |

---

## Proveedor 4 — NVIDIA NIM (online, gratuito) · API propia de NVIDIA

API OpenAI-compatible alojada en DGX Cloud de NVIDIA. Acceso vía [build.nvidia.com](https://build.nvidia.com) con el programa de desarrolladores gratuito. **No requiere tarjeta de crédito.** API key con prefijo `nvapi-`.

### Rate limits y créditos

| Concepto | Valor | Notas |
|----------|-------|-------|
| RPM | 40 (compartido entre todos los modelos) | No es por modelo — la cuota global es 40 RPM |
| Créditos iniciales | 1.000 (hasta 5.000 bajo petición) | No se renuevan diariamente; son un pool que se consume |
| Coste por request (modelos ligeros) | ~0,05–0,1 créditos | Llama 3.2 1B/3B → estimado 10.000–20.000 requests con 1.000 créditos |
| RPM upgrade | 200 RPM (solicitable) | — |

**Análisis para la suite:**

| Escenario | Requests | Tiempo a 40 RPM | Créditos estimados | ¿Viable? |
|-----------|----------|-----------------|-------------------|----------|
| 1 run | 61 | ~2 min | ~6 créditos | ✅ |
| 3 runs | 183 | ~5 min | ~18 créditos | ✅ |
| 3× seguidas | 549 | ~14 min | ~55 créditos | ✅ |
| Concurrencia 3 | 183 total | ~5 min | ~18 créditos | ✅ RPM compartido no es problema |

> El límite real es el pool de créditos, no el RPM. Con 1.000 créditos iniciales y modelos pequeños la suite puede correr decenas de veces.

### Modelos candidatos

| Modelo | ID NVIDIA NIM | Tamaño | Contexto | Notas |
|--------|--------------|--------|----------|-------|
| Llama 3.2 1B | `meta/llama-3.2-1b-instruct` | 1B | 131K | **Comparación 3-vías**: mismo modelo que `llama3.2:1b` (Ollama) → local vs. cloud |
| Llama 3.2 3B | `meta/llama-3.2-3b-instruct` | 3B | 131K | **Comparación 3-vías**: mismo modelo que Ollama y OpenRouter → diferencias por proveedor |
| LlamaGuard 4 | `meta/llama-guard-4-12b` | 12B | 164K | Clasificador de seguridad de Meta — relevante para la capa de defensa PromptGuard; analizar cómo percibe los payloads de ataque |
| Nemotron Content Safety | `nvidia/nemotron-3.5-content-safety` | — | 128K | Clasificador de seguridad de NVIDIA — también disponible en OpenRouter; útil para comparar detectores en la capa de defensa |
| Nemotron Super 49B | `nvidia/llama-3.3-nemotron-super-49b-v1.5` | 49B | 131K | Fuera del rango principal; referencia de calidad alta NVIDIA |

> **Valor diferencial de NVIDIA NIM:** Los modelos `llama-guard-4-12b` y `nemotron-3.5-content-safety` son clasificadores de seguridad, no chatbots. Pasarles los payloads de ataque permite estudiar si estos guardias los detectan — información directamente útil para el diseño del Tool Gatekeeper.

---

## Resumen de candidatos prioritarios

Lista reducida para la primera ronda de evaluación (balance cobertura / tiempo):

| # | Modelo | Proveedor | Tamaño | Prioridad |
|---|--------|-----------|--------|-----------|
| 1 | `llama3.2:1b` | Ollama | 1B | 🔴 Alta — mínimo recurso, referencia base |
| 2 | `llama3.2:3b` | Ollama | 3B | 🔴 Alta — tier ligero más popular |
| 3 | `phi4-mini:3.8b` | Ollama | 3.8B | 🔴 Alta — mejor function calling en < 4B |
| 4 | `qwen3:8b` | Ollama | 8B | 🔴 Alta — **modelo actual del lab**, referencia |
| 5 | `llama3.1:8b` | Ollama | 8B | 🔴 Alta — referencia clásica 8B |
| 6 | `llama-3.1-8b-instant` | Groq | 8B | 🔴 Alta — misma arquitectura que #5, velocidad LPU; comparación local vs. cloud |
| 7 | `meta/llama-3.2-1b-instruct` | NVIDIA NIM | 1B | 🔴 Alta — comparación 3-vías con #1: mismo modelo en cloud NVIDIA vs. local |
| 8 | `meta/llama-3.2-3b-instruct` | NVIDIA NIM | 3B | 🟡 Media — comparación 3-vías con #2 y OpenRouter; diferencias por proveedor |
| 9 | `meta-llama/llama-3.2-3b-instruct:free` | OpenRouter | 3B | 🟡 Media — tercer vértice de la comparación 3B |
| 10 | `qwen2.5:14b` | Ollama | 14B | 🟡 Media — techo calidad local |
| 11 | `meta/llama-guard-4-12b` | NVIDIA NIM | 12B | 🟡 Media — clasificador de seguridad; estudiar si detecta los payloads de ataque |
| 12 | `nvidia/nemotron-nano-9b-v2:free` | OpenRouter | 9B | 🟡 Media — NVIDIA, rango 7B-9B online |
| 13 | `qwen/qwen3-32b` | Groq | 32B | 🟢 Baja — referencia de calidad alta online |

> **Comparaciones 3-vías**: `llama3.2:1b` (Ollama) = `meta/llama-3.2-1b-instruct` (NVIDIA NIM); `llama3.2:3b` (Ollama) = `meta/llama-3.2-3b-instruct` (NVIDIA NIM) = `meta-llama/llama-3.2-3b-instruct:free` (OpenRouter). Mismo modelo base, distinto proveedor — permite aislar el efecto del proveedor sobre el comportamiento ante ataques.

---

## Configuración de proveedores en el backend

### NVIDIA NIM (añadir soporte)

```bash
# lab/.env
LLM_PROVIDER=custom
LLM_BASE_URL=https://integrate.api.nvidia.com/v1
LLM_MODEL=meta/llama-3.2-3b-instruct
LLM_API_KEY=nvapi-...   # desde build.nvidia.com → Settings → API Keys
```

### Groq (añadir soporte)

```bash
# lab/.env
LLM_PROVIDER=custom
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=gsk_...   # desde console.groq.com
```

### OpenRouter (ya soportado)

```bash
LLM_PROVIDER=openrouter
LLM_MODEL=meta-llama/llama-3.2-3b-instruct:free
OPENROUTER_API_KEY=sk-or-...
```

### Ollama (ya soportado)

```bash
LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:1b   # cambiar al modelo deseado
```
