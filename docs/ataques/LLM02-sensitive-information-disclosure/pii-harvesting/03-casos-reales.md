# Casos Reales y Evidencia Científica — PII Harvesting vía Contexto

> Principio rector: este documento **solo** cita referencias incluidas en la lista permitida del TFM y ejemplos ilustrativos explícitamente marcados como tales. No se inventan CVEs ni IDs de incidente.

## 1. Referencia científica permitida

### Carlini et al. (2021)

- **Título:** *Extracting Training Data from Large Language Models.*
- **Foro:** USENIX Security Symposium 2021.
- **Autores:** Nicholas Carlini, Florian Tramèr, Eric Wallace, Milad Nasr, Surya Jagannath, Nicholas Carlini et al.
- **URL canónica:** `https://www.usenix.org/conference/usenixsecurity21/presentation/carlini`

**Paralelo conceptual con el ataque #6 (sin identidad técnica):**

El trabajo de Carlini demuestra que un LLM puede **emitir texto memorizado** cuando se le interroga de forma suficientemente dirigida y persistente. El patrón subyacente — *el modelo repite datos que ha procesado si el atacante construye el contexto adecuado* — es el mismo principio conceptual que aprovecha el PII Harvesting vía Contexto: en lugar de extraer de los pesos del modelo, se extrae de la **memoria de sesión** (el contexto activo que Clara acumula).

| Dimensión | Carlini et al. 2021 | PII Harvesting vía Contexto (#6) |
|-----------|---------------------|----------------------------------|
| Fuente del dato | Pesos del modelo | Contexto de sesión / output de tools |
| Acceso requerido | Consultas a la API del modelo | Sesión autenticada en Clara |
| Cadencia | Cientos de consultas | Multi-turno progresivo |
| Dato objetivo | Texto de entrenamiento memorizado | IBAN / saldo / nombre de titulares |

La diferencia es **dónde vive el dato**: entrenamiento vs. contexto activo. La similitud es **el mecanismo de extracción**: interrogación persistente que provoca emisión del dato procesado.

## 2. Marcos de referencia permitidos

| Marco | Cómo enmarca este ataque |
|-------|--------------------------|
| **OWASP LLM Top 10 2025** — LLM02:2025 | "Sensitive Information Disclosure" abarca la emisión no autorizada de datos sensibles procesados por el modelo, sea por entrenamiento o por contexto. `https://owasp.org` |
| **MITRE ATLAS v4** — AML.T0024 (Collection) | Táctica de recopilación: el adversario reúne información de interés del sistema objetivo. `https://atlas.mitre.org` |

## 3. Ejemplos ilustrativos (NO son incidentes reales)

> Lo siguiente es **ilustrativo y ficticio**, adaptado al escenario VerdaBank. No constituye evidencia de un caso real.

- [ILUSTRATIVO] Pretexto de "auditoría interna" — equivalente al payload `atk_011` (`lab/backend/tests/fixtures/attack_prompts.jsonl:11`).
- [ILUSTRATIVO] Pretexto de "reporte de compliance" — equivalente al payload `atk_012` (`lab/backend/tests/fixtures/attack_prompts.jsonl:12`).
- [ILUSTRATIVO] Construcción progresiva: turno 1 pide un IBAN "de referencia", turno 2 pide confirmación de saldo, turno 3 pide enumeración. Patrón comparable al reconocimiento incremental documentado en la literatura de model extraction.

## 4. Incidente motivador del TFM

El incidente ficticio **INC-2025-0089** descrito en `docs/propuesta-formal-promptguard-fintech.md:44-46` es la materialización canónica de la familia LLM02:2025 en el escenario VerdaBank. Aunque categorizado como Cross-Context (#3), comparte raíz con #6: la PII accesible al LLM acaba en la respuesta al usuario.

## 5. Limitaciones de la evidencia

- [ ] No se documenta CVE específico (la superficie depende de la integración particular del chatbot, no de una vulnerabilidad de producto).
- [ ] La transferibilidad de los hallazgos de Carlini et al. al dominio bancario es **conceptual**, no cuantitativa.
- [ ] La evidencia empírica directa se generará al ejecutar el lab (futuro), no en esta fase pre-implementación.

## Estado del análisis

- [x] Referencia científica permitida citada (Carlini 2021)
- [x] Marcos permitidos referenciados (OWASP, ATLAS)
- [x] Ejemplos ilustrativos marcados explícitamente
- [x] Limitaciones de evidencia declaradas
