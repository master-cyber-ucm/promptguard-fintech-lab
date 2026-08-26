# 03 — Casos Reales y Referencias

> Cross-Context Data Leakage (#3). Solo se citan fuentes permitidas y verificables.

## 1. Referencia académica (fundamento teórico)

**Carlini, N., Tramèr, F., Wallace, E., Jagielski, M., Herbert-Voss, A., Lee, K., Roberts, A., Brown, T., Song, D., Raffel, C., Shokri, R., Troncoso, C. (2021). *"Extracting Training Data from Large Language Models"*. USENIX Security Symposium.**

- Demuestra que un LLM puede **memorizar y repetir** datos sensibles presentes en su entrenamiento mediante prompts dirigidos.
- **Relación con este ataque:** comparte la familia de riesgo *Information Disclosure*, pero el **mecanismo difiere**. Carlini extrae datos **memorizados en los pesos** del modelo base; este ataque extrae datos **en memoria de sesión / contexto en runtime**, sin necesidad de memorización. No requiere que el modelo haya sido entrenado con datos del banco.
- Lección aplicable: la revelación de información no depende solo del entrenamiento, sino del **acceso en tiempo de ejecución** a datos de otras identidades.

## 2. Incidente industrial (fuga vía LLM de terceros)

**Fuga de datos en Samsung vía ChatGPT (marzo 2023)** — caso de fuga reportado públicamente.

- Empleados introdujeron código fuente confidencial y datos internos en prompts de ChatGPT; la información quedó expuesta en el servicio externo.
- **Ilustración del patrón** (ejemplo representativo, no bancario): muestra cómo un LLM en el flujo de trabajo se convierte en canal de fuga de información sensible.
- **Paralelismo con VerdaBank:** aquí la fuga no es hacia el proveedor del LLM, sino **hacia otro cliente** a través de la propia respuesta del chatbot; la causa raíz es la misma: datos confidenciales tratados por el LLM sin aislamiento por identidad.

## 3. Incidente motivador del escenario (caso propio)

**INC-2025-0089 — VerdaBank (15 de marzo de 2025)**

- Contexto: chatbot bancario "Clara" (`docs/propuesta-formal-promptguard-fintech.md`, §2.2).
- Hecho: un cliente manipuló a Clara para que revelara el **saldo de otro usuario** mediante *context manipulation*.
- Clasificación: brecha de dato personal bajo **GDPR Art. 33**; notificado a la **AEPD**.
- Relevancia: es **el incidente que activa el proyecto PromptGuard** (`docs/anexo-catalogo-ataques-llm.md`, fila #3).

> Nota: INC-2025-0089 es un incidente **ficticio**, interno al escenario docente VerdaBank. No se asigna ningún identificador externo inventado.

## 4. Limitación de evidencia pública

No existe un incidente público documentado con identificación exacta de "cross-context leakage entre sesiones de un chatbot bancario" con ID asignado. Por rigor metodológico **no se inventan identificadores** de CVE, organismo o empresa. Los casos anteriores (Carlini 2021 y Samsung 2023) son las referencias verificables más próximas; INC-2025-0089 cubre el caso específico del laboratorio.

## 5. Fuentes

- Carlini et al., 2021, USENIX Security (extracción/memorización).
- Fuga de Samsung vía ChatGPT, 2023 (caso de fuga por LLM, reporte público).
- OWASP LLM Top 10 (2025), owasp.org — categoría LLM02.
- MITRE ATLAS v4, atlas.mitre.org — AML.T0024 (Collection).
- `docs/propuesta-formal-promptguard-fintech.md` §2.2 · `docs/anexo-catalogo-ataques-llm.md` #3.
