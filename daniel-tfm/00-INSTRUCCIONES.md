# Instrucciones permanentes — TFM Daniel — Defensa de 4 vectores

> Contexto que se lee (y se mantiene actualizado) al empezar cualquier sesión de trabajo sobre
> este capítulo. Vive en `daniel-tfm/`, en la raíz del repo, y se commitea a la rama
> `feat/daniel-defensas-4-vectores`.

## 0. Encuadre

Máster en Ciberseguridad — UCM. TFM colectivo: **PromptGuard FinTech** (evaluación y defensa de
ciberseguridad en un chatbot bancario basado en LLM). Cada alumno toma uno o varios vectores del
catálogo y los lleva de punta a punta.

**Escenario:** VerdaBank S.A. (neobank español ficticio) y **Clara**, su asistente conversacional
construido con PydanticAI, con acceso a 5 tools bancarias mock (`consulta_saldo`,
`transferencia_nacional`, `bloquear_tarjeta`, `consulta_producto`, `abrir_reclamacion`).

**Rama:** `feat/daniel-defensas-4-vectores`, partida de `feat/suite-improvements`.
**Worktree:** este capítulo se desarrolla en un git worktree separado
(`../software-daniel`) porque hay otros agentes trabajando sobre el árbol principal y el backend
del lab corre en Docker con `--reload` sobre el código montado: editar `lab/backend/src` en el
árbol compartido habría alterado en caliente las corridas de otros. Ver §5.

## 1. Alcance — los 4 vectores asignados

Seleccionados del ranking de dificultad de los 9 escenarios del catálogo, uno por nivel:

| # ranking | Vector | Fixtures | Dificultad | Estado de la defensa al empezar |
|---|---|---|---|---|
| 2 | **LLM02 — PII Harvesting** | `atk_011`, `atk_012` | ★★☆☆☆ | ❌ `pii_shield.py` era un esqueleto no-op |
| 4 | **LLM07 — System Prompt Leakage (API key)** | `atk_015` | ★★★☆☆ | ⚠️ parcial — 3 cadenas literales, evadible |
| 6 | **LLM06 — Confused Deputy** | `atk_010`, `atk_020` | ★★★★☆ | ✅ cubierto por el Tool Gatekeeper |
| 9 | **LLM01 — Injection Indirecta (PDF)** | `atk_035`–`atk_037`, `atk_069` | ★★★★★ | ⚠️ cubre override, no exfiltración de datos |

La heterogeneidad del punto de partida **no es un problema del encargo, es el resultado del
encargo**: la primera tarea fue medir qué existía de verdad antes de escribir una línea (ver
`01-vectores/estado-inicial.md`). Un capítulo que hubiera asumido "hay que implementar cuatro
defensas desde cero" habría reimplementado dos que ya funcionaban.

## 2. Regla de oro de este capítulo — qué NO se documenta aquí

El repo ya tiene dos cuerpos documentales sobre estos mismos vectores. **No se duplica ninguno.**

| Dónde | Qué contiene | Relación con este capítulo |
|---|---|---|
| `docs/ataques/<LLMxx>/<variante>/` | Qué es el ataque: mapeo taxonómico OWASP/ATLAS, threat modeling, casos reales, análisis técnico, cumplimiento, contexto VerdaBank, playbook de respuesta | **Se referencia.** No se repite taxonomía, CVSS, ni narrativa del incidente |
| `docs/defensas/<LLMxx>/<variante>.md` | Cómo debería defenderse: invariantes de seguridad, principio de diseño, arquitectura del control, límites conocidos, criterios de validación, mapeo normativo | **Se referencia.** No se repite el diseño ni el mapeo normativo genérico |
| `daniel-tfm/` (este workspace) | **Qué se construyó de verdad, qué mide y qué salió** | Lo propio |

En una frase: *`docs/ataques` dice qué amenaza existe, `docs/defensas` dice qué control habría
que construir, y `daniel-tfm` dice qué se construyó, con qué evidencia y qué se aprendió al
hacerlo — incluidos los huecos que el diseño sobre el papel no había previsto.*

Cuando este capítulo necesita una afirmación de los otros dos, la enlaza. Cuando **contradice**
lo que dicen (porque la implementación reveló algo distinto), lo dice explícitamente y explica
por qué — eso es contenido propio, no duplicación.

## 3. Índice oficial del TFM y encaje de este capítulo

1. Introducción y motivación
2. Estado del arte · 2.1 OWASP/ATLAS · 2.2 Defensas y red teaming · 2.3 Vectores
3. Objetivos, alcance y metodología
4. Diseño e implementación de PromptGuard · 4.1 Arquitectura · 4.2 Vectores evaluados
5. Red teaming automatizado y continuo
6. Validación experimental y resultados · 6.1 Métricas por vector · 6.2 Análisis
7. Marco normativo (DORA, AI Act, RGPD)
8. Conclusiones y trabajo futuro
9. Bibliografía

**Dónde alimenta este capítulo:**

- **4.1** — implementación real del **PII Shield** (entrada + salida) y endurecimiento del
  **Output Auditor**; cómo encajan en el pipeline junto a Tool Gatekeeper y las capas documentales.
- **4.2** — los 4 vectores, con el detalle de qué control los cubre y cuál no.
- **6.1** — métricas antes/después por vector, falsos positivos sobre tráfico legítimo, latencia.
- **6.2** — el análisis transversal: los tres ejes de defensa y por qué el hueco estaba en uno.
- **7** — lo específico de estos vectores (GDPR Art. 5.1.c / 32 / 33 sobre el PII Shield; AI Act
  Art. 13/14/15).

## 4. Reglas de trabajo

1. **Medir antes de construir.** Ninguna defensa se implementa sin haber comprobado primero, con
   una sonda ejecutable, qué hace el sistema hoy. El fichero `01-vectores/estado-inicial.md`
   contiene esa medición y es la línea base de todo lo demás.
2. **Reproducibilidad estricta.** Toda cifra viene con el procedimiento exacto: comando, fixture
   ID, commit, modelo/proveedor, y ruta del resultado. Ver `02-defensa/evidencia/`.
3. **Los tests son parte del entregable, no un extra.** Cada defensa lleva su regresión atada a
   los payloads reales del catálogo, no a ejemplos inventados.
4. **Los falsos positivos se miden igual que los bloqueos.** Una defensa que bloquea el 100% de
   los ataques y el 30% del tráfico legítimo no es una defensa, es una caída de servicio. Todos
   los conjuntos de prueba incluyen prompts legítimos.
5. **No romper el trabajo del resto del equipo.** Las capas nuevas que tocan superficies
   compartidas (el canal documental del ataque #7) se añaden desactivadas por defecto, siguiendo
   el precedente de `defensa_separacion_tool_framing`. Ver `02-defensa/README.md`.
6. **Alcance ético/legal.** Todo se ejecuta en local, contra el lab del propio TFM, en contexto
   académico autorizado.

## 5. Entorno de trabajo

```bash
# Worktree aislado (el árbol principal lo usan otros agentes)
git worktree add ../software-daniel feat/daniel-defensas-4-vectores

# Tests — no requieren LLM
cd lab/backend && python -m pytest tests/ -q

# Backend aislado en :8010 (el compartido corre en :8000 vía Docker)
cd lab/backend && LLM_PROVIDER=ollama OLLAMA_BASE_URL=http://localhost:11434/v1 \
  OLLAMA_MODEL=qwen2.5:3b OLLAMA_API_KEY=ollama \
  python -m uvicorn src.main:app --host 127.0.0.1 --port 8010

# Evidencia experimental
cd daniel-tfm/02-defensa/evidencia && python ejecutar_evidencia.py --puerto 8010
```

## 6. Estructura del workspace

```
daniel-tfm/
├── 00-INSTRUCCIONES.md      ← este archivo
├── ROADMAP.md               ← checklist por fases
├── CAPITULO.md              ← prosa acumulada para el documento final
├── bitacora/BITACORA.md     ← diario cronológico
├── 01-vectores/             ← medición del estado inicial y análisis del hueco
├── 02-defensa/              ← implementación + evidencia experimental
└── 03-normativa/            ← lo normativo específico de estos 4 vectores
```
