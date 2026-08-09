# PromptGuard FinTech Lab

Laboratorio experimental del TFM **"Evaluación de la Ciberseguridad en Entornos de IA Generativa"** (Máster en Ciberseguridad, UCM).

Simula un banco ficticio —**VerdaBank**— con un asistente de IA, **Clara**, que tiene acceso real a herramientas bancarias: consultar saldos, transferir dinero, bloquear tarjetas. Sobre él se reproducen ataques del OWASP LLM Top 10, se construyen defensas deterministas y se mide qué funciona y qué no.

Todo con datos sintéticos, software libre y reproducible desde cero con un solo comando.

---

## Los tres sistemas

### LLM-SOC — observabilidad del proxy

Registra qué prompt entró, qué componente de defensa lo examinó, qué decidió y por qué. El proxy detecta y detiene; el SOC solo mira.

![Postura del sistema](docs/img/soc-postura.jpg)

El **mapa de cobertura** es la pieza central: cruza cada vector de ataque con el componente que debería defenderlo y con lo que de verdad ocurrió. Cuando un vector no tiene defensa implementada, lo dice —y dice qué otra capa lo detuvo en su lugar.

![Stream de eventos](docs/img/soc-eventos.jpg)

Cada fila del flujo cronológico lleva una **cadena de seis posiciones**, una por componente del pipeline. Relleno = evaluó; hueco punteado = no evaluó. Un turno en modo vulnerable son seis huecos en fila: la ausencia de defensa se ve sin desplegar nada.

![Base de conocimiento](docs/img/soc-conocimiento.jpg)

Desde cualquier evento se llega a los **72 documentos** de ataque y defensa del proyecto: playbook de respuesta a incidentes, análisis técnico, mapeo MITRE ATLAS, encaje normativo. El puente es estructural — fixtures y documentación comparten árbol de taxonomía.

### Playground — banco de pruebas de ataques

![Playground](docs/img/playground.jpg)

Chat contra Clara con las **108 fixtures** del catálogo cargables desde el panel lateral, selector de nivel de defensa y captura de conversaciones como fixtures nuevas.

### VerdaBank — la aplicación bajo ataque

![VerdaBank](docs/img/verdabank.jpg)

El banco ficticio: cuatro clientes con cuentas, tarjetas y movimientos sintéticos. Es lo que un atacante intenta comprometer a través de Clara.

---

## Arranque rápido

Un solo comando levanta Ollama, descarga el modelo y arranca el stack completo:

```bash
cd lab
make run
```

Después:

| Superficie | URL |
|---|---|
| VerdaBank | http://localhost:3000 |
| Playground | http://localhost:3000/playground.html |
| LLM-SOC | http://localhost:3000/soc.html |
| API | http://localhost:8000/docs |

Requisitos: Docker y Docker Compose. Nada más — ni claves de API ni servicios de pago. Detalle de operación en [`lab/README.md`](lab/README.md).

---

## Qué hay dentro

| | |
|---|---|
| **108 fixtures** | 76 de ataque · 20 legítimos · 12 *naive*, en 4 categorías OWASP + extensiones |
| **186 tests** | Unitarios y de integración sobre las defensas y el arnés de medición |
| **72 documentos** | 60 de ataque (7 por vector) y 12 de defensa, por taxonomía OWASP |
| **7 ADRs** | Decisiones de arquitectura con sus alternativas descartadas |
| **6 endpoints** | 5 niveles graduales de defensa + el proxy completo |

### Los siete vectores del escenario

| # | Vector | OWASP | Componente que defiende | Estado |
|---|---|---|---|---|
| 1 | Excessive Agency | LLM06 | Tool Gatekeeper | ✅ |
| 2 | Prompt Injection Directa | LLM01 | Input Sanitizer | ⚠️ **esqueleto** |
| 3 | Cross-Context Leakage | LLM02 | Guardia de fuga | ✅ |
| 4 | Confused Deputy | LLM06 | Tool Gatekeeper | ✅ |
| 5 | System Prompt Leakage | LLM07 | Output Auditor | ✅ |
| 6 | PII Harvesting | LLM02 | PII Shield | ✅ |
| 7 | Prompt Injection Indirecta (documento) | LLM01 | Document Sanitizer + detector estructural | ✅ |

El Input Sanitizer sigue siendo un esqueleto que devuelve `ALLOW` siempre. **No está escondido**: el SOC lo muestra en cada traza y el mapa de cobertura marca ese vector en rojo. Un panel que finge cobertura que no existe no sirve para nada.

### El pipeline de defensa

```
prompt ─▶ Input Sanitizer ─▶ PII Shield ─▶ Clara (LLM) ─▶ Output Auditor ─▶ respuesta
                                              │                  │
                                       Tool Gatekeeper      Guardia de fuga
                                       (RBAC determinista)   PII Shield salida
                                              │                  │
                                              └────────┬─────────┘
                                                       ▼
                                                    LLM-SOC
                                            (observa, no bloquea)
```

Cuatro principios, detallados en [`docs/defensas/README.md`](docs/defensas/README.md):

1. **La autoridad vive fuera del modelo.** Un LLM puede ser convencido; `user_id == account.owner_id` no.
2. **Todo texto es dato no confiable**, venga del usuario, de un PDF o del resultado de una tool.
3. **Asumir que el system prompt se filtra.** Es documentación, no un control de acceso.
4. **Verificar la salida, no solo la entrada.** Toda defensa de entrada es evadible.

---

## Medir, no solo atacar

```bash
make suite      # lanza las fixtures contra los endpoints
make analyze    # calcula Verdicts y genera el Run Report
make test       # 186 tests
```

Cada ejecución deja un **Run Folder** con un fichero Markdown por sesión —transcript turno a turno, tools invocadas, latencias— y un Run Report con métricas por categoría. El SOC captura ese mismo tráfico en paralelo y permite comparar dos corridas componente a componente.

Los dos almacenes conviven a propósito: el Markdown es la evidencia citable del TFM; la base del SOC es la proyección consultable. La decisión y sus alternativas descartadas están en [`docs/adr/0007`](docs/adr/0007-dos-almacenes-para-la-traza-de-un-turno.md).

---

## Mapa del repositorio

```
lab/
  backend/       FastAPI · Clara (pydantic-ai) · capas de defensa · SOC · 108 fixtures
  frontend/      VerdaBank · Playground · LLM-SOC (vanilla JS, sin build)
  scripts/       Suite de ataques, evaluador, generación de informes
  audit/         Session Files, Run Reports y la base del SOC (fuera de git)
docs/
  ataques/       60 documentos: taxonomía, threat model, casos reales, análisis, normativa, playbook
  defensas/      12 documentos de diseño de control
  soc/           Diseño del LLM-SOC
  adr/           7 decisiones de arquitectura
  reports/       Informes de red team y comparativas de campañas
henri-tfm/       Capítulo individual — ataque #7 (indirecta vía documento)
daniel-tfm/      Capítulo individual — vectores 2, 4, 6 y 9
```

---

## Estado y honestidad del laboratorio

Este repositorio documenta tanto lo que funciona como lo que no:

- El **Input Sanitizer no está implementado** y el panel lo enseña.
- **21 fixtures** (jailbreak, encadenados, ingeniería social, ofuscación) **no tienen documentación** asociada; el SOC lo declara explícitamente en vez de mostrar un hueco silencioso.
- El SOC guarda prompts y respuestas **en claro**. Los datos son sintéticos, pero el marco propuesto para empresas reales exige minimización, retención y control de acceso: se documenta como requisito, no se implementa aquí.
- Los diagramas Mermaid de la documentación se muestran como código fuente en el panel.

---

## Licencia y alcance

Trabajo académico con fines de investigación y docencia. Todos los datos —clientes, cuentas, IBANs, movimientos— son **sintéticos**. VerdaBank no existe.

Los ataques incluidos están pensados para ejecutarse contra este laboratorio local y controlado.
