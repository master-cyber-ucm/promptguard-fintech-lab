# Persistir el veredicto de cada capa defensiva

## Descripción del problema

El informe final sólo contiene el veredicto del evaluador. Cuando un caso falla, no se sabe sin abrir manualmente logs si la causa fue Input Sanitizer, Gatekeeper, PII Shield, Output Auditor, modelo o juez.

## Evidencia observada

El caso [`leg_021`](../lab/audit/runs/20260829_151324_qwen2.5-3b/proxy-full/20260829_233901_ses_783104617691_1788046741.md) revela el Input Sanitizer por texto visible; otros casos requieren inferirlo. El [run.json](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.json) no ofrece una estructura uniforme de decisiones por capa.

## Explicación técnica

Cada capa ya genera o conoce una decisión, pero esa información se dispersa entre logs, respuesta y tool result. El agregador sólo consume `passed`, `verdict` y `detail`, por lo que pierde atribución causal.

## Alternativas de mejora

### A. Traza estructurada por turno (recomendada)

Añadir `defense_decisions` con componente, acción, regla, latencia, confianza y efecto en la respuesta. El evaluador agrega su resultado como capa separada.

### B. Parsear texto de logs

Es frágil y no tiene contrato de compatibilidad.

## Solución propuesta

Definir un esquema versionado por turno y propagarlo a `run.json`. Renderizar en Markdown una vista compacta y una tabla de atribución por endpoint.

## Pruebas de aceptación

1. Cada turno de proxy contiene una decisión por capa activa.
2. Un FP puede filtrarse por componente y regla.
3. La ausencia de una capa se representa explícitamente como `not_enabled`.
