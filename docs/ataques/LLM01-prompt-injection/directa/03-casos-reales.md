# Casos Reales y Referencias — Prompt Injection Directa

> Ataque #2 del catálogo · Referencias limitadas a la lista permitida

---

## 1. Fuentes oficiales (frameworks)

| Fuente | URL | Aporte al ataque |
|--------|-----|------------------|
| **OWASP LLM Top 10 (2025)** | owasp.org | Cataloga LLM01:2025 *Prompt Injection* como la categoría nº1 de riesgo en aplicaciones LLM. Define directa vs. indirecta y lista vectores (override de instrucciones, redefinición de rol). |
| **MITRE ATLAS v4** | atlas.mitre.org | Recoge la técnica `AML.T0051.000` *Prompt Injection* (variante directa). La incluye en la matriz de tácticas como vía de *Initial Access* sobre sistemas de IA. |

Estas dos fuentes son el marco de referencia obligado para el capítulo 2 (Estado del arte) de la memoria del TFM.

## 2. Papers académicos clave

### Greshake et al. (2023)
- *"Not what you've signed up for: Compromising Real-World LLM Applications with Indirect Prompt Injection."*
- **Por qué es relevante aquí:** aunque describe **inyección indirecta** (vía documentos/páginas web), establece el mecanismo fundacional de por qué un LLM no distingue instrucciones de sistema de instrucciones embebidas en contenido. El mismo fallo de alineación subyace a la variante directa documentada en este ataque.
- **Uso en la memoria:** fundamento teórico de la sección "mecanismo del fallo" del análisis técnico (`04-analisis-tecnico.md`).

### Perez & Ribeiro (2022)
- *"Ignore Previous Prompt: Attack Techniques For Language Models."*
- **Por qué es relevante aquí:** trabajo fundacional sobre inyección y *jailbreak* directo. Acuña el patrón "ignore previous instructions" que es exactamente la firma del payload `atk_001` / `atk_002` del fixture.
- **Uso en la memoria:** referencia directa para la anatomía del payload en el análisis técnico.

> **Nota de honestidad:** no se citan DOIs ni identificadores arXiv concretos para evitar atribución imprecisa. En la bibliografía final de la memoria se completarán las fichas con los identificadores estables verificados en el repositorio académico correspondiente.

## 3. Incidentes públicos (ilustrativos)

No existe un incidente público confirmado idéntico al escenario VerdaBank (filtrado de saldo bancario vía inyección directa a un chatbot). Los dos siguientes son los incidentes reales más cercanos y se usan como **ejemplos ilustrativos** del patrón:

### Bing "Sydney" prompt leak (2023)
- Un usuario consiguió que el chatbot de Microsoft revelara fragmentos de su system prompt ("internal rules") mediante instrucciones de override.
- **Paralelismo con este ataque:** valida que la técnica de sobrescritura funciona contra productos comerciales en producción, no solo en laboratorio. Corresponde al ángulo *System Prompt Leakage* (#5 del catálogo), pero la vía de entrada es la misma: inyección directa LLM01.

### Ingenieros de Samsung filtrando código vía ChatGPT (2023)
- Empleados pegaron código fuente interno en ChatGPT para revisión; el incidente obligó a Samsung a restringir el uso de la herramienta.
- **Paralelismo con este ataque:** ilustra el riesgo de exfiltración involuntaria/intencionada a través de un canal LLM y por qué un canal conversacional bancario es una superficie crítica.

## 4. Síntesis

La literatura académica (Perez & Ribeiro, Greshake et al.) y los incidentes públicos convergen en una conclusión: **la inyección de prompts es un riesgo demostrado en productos reales, no una curiosidad de laboratorio.** El escenario VerdaBank lo traslada al dominio financiero, donde el activo comprometido (datos de cuenta) tiene consecuencia regulatoria directa.
