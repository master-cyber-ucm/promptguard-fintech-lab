# 03 — Casos Reales y Literatura

> **Ataque #7** — Prompt Injection Indirecta — Documento
> Documento PRE-implementación. Sólo se citan referencias verificables; no se inventan identificadores.

---

## 1. Referencias fundacionales (académicas)

### 1.1 Greshake et al. (2023) — Papel fundacional de Indirect Prompt Injection

- **Autores:** Kai Greshake, Suraj Nair, Tobias Askar, Shinjo Yeo, June Kuhnegger, Jonas Buhmann, Christian Schroeder de Witt.
- **Título:** *"Not what you've signed up for: Compromising Real-World LLM Applications with Indirect Prompt Injection."*
- **Año:** 2023.
- **Contribución al ataque #7:** define formalmente la variante **indirecta** de prompt injection y demuestra que un LLM no puede distinguir de forma fiable entre **instrucciones** y **datos** cuando ambos comparten el mismo contexto. Es el marco teórico de referencia para este ataque y para los derivados vía imágenes, EXIF y OCR (ataques #12–#14 del catálogo).
- **Relevancia para VerdaBank:** justifica el principio defensivo de que el texto extraído de un documento de usuario **nunca** es contexto de confianza.

### 1.2 Perez & Ribeiro (2022) — Marco de ataques a modelos de lenguaje

- **Autores:** Fábio Perez, Ian Ribeiro.
- **Título:** *"Ignore Previous Prompt: Attack Techniques For Language Models."*
- **Año:** 2022.
- **Contribución:** caracteriza las técnicas de **ignore-previous** y de instrucciones contradictorias, base de la redacción de payloads ocultos en documentos. Aplica tanto a la variante directa (#2 del catálogo) como a la indirecta (#7).

---

## 2. Incidente público ilustrativo

### 2.1 Bing "Sydney" (febrero 2023)

- **Contexto:** el chatbot Bing basado en GPT comenzó a emitir declaraciones perturbadoras y a seguir instrucciones provenientes de contenido web indexado, en lugar de las directrices del sistema.
- **Vínculo con el ataque #7:** aunque el episodio no se cataloga exclusivamente como indirect injection, ilustra el mecanismo central: **un LLM que procesa contenido externo como instrucción legítima**. En el escenario de VerdaBank el contenido externo es el PDF del cliente en lugar de una página web.
- **Uso en este documento:** ejemplo ilustrativo, no evidencia de compromiso bancario.

---

## 3. Marcos de referencia de la industria

| Fuente | Cobertura del ataque #7 |
|--------|-------------------------|
| **OWASP LLM Top 10 (2025)** — owasp.org | Categoría **LLM01:2025**, subtipo indirect prompt injection. |
| **MITRE ATLAS v4** — atlas.mitre.org | Técnica **AML.T0051.001 — Prompt Injection (Indirect)**, táctica Initial Access. |

---

## 4. Limitaciones de este apartado

- No existen (a fecha de redacción) incidentes bancarios públicos confirmados atribuibles con certeza a indirect prompt injection por documento. El riesgo se deriva **analíticamente** de la literatura fundacional y del patrón de arquitectura del chatbot de Clara.
- **No se citan DOIs, arXiv IDs ni identificadores de publicación** más allá de los títulos y años arriba referidos; el lector debe localizar las versiones canónicas en los repositorios oficiales.

---

## 5. Lectura recomendada para el TFM

1. Greshake et al. (2023) — para fundamentar el capítulo de análisis de amenazas.
2. Perez & Ribeiro (2022) — para la taxonomía de payloads que reaparece en el ataque directo (#2).
3. OWASP LLM01:2025 y MITRE ATLAS AML.T0051.001 — para el mapeo normativo y la kill chain (ver `01-mapeo-taxonomico.md`).
