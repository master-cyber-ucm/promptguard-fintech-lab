# Ejecutar la matriz completa de perfiles del proxy

## Descripción del problema

La comparación actual usa `baseline` y `full`; muestra el efecto combinado de todas las defensas, pero no atribuye qué capa aporta bloqueo, utilidad o falsos positivos.

## Evidencia observada

La [configuración de la run](../lab/audit/runs/20260829_151324_qwen2.5-3b/suite-config.json) declara únicamente `proxy-baseline` y `proxy-full`. El informe no permite distinguir el impacto aislado de Gatekeeper, Output Auditor/PII Shield e Input Sanitizer.

## Explicación técnica

Los perfiles disponibles son `baseline`, `gatekeeper`, `output` y `full`. Si faltan perfiles intermedios, una mejora puede atribuirse erróneamente al sanitizer cuando procede del Gatekeeper, o esconder el coste de una defensa de salida.

## Alternativas de mejora

### A. Ablación completa con misma suite y semilla (recomendada)

Ejecutar cada fixture/repetición contra los cuatro perfiles, con mismo modelo, versión de fixtures y configuración. Comparar diferencias por familia y tráfico legítimo.

### B. Comparación binaria

Es más rápida, pero no ofrece causalidad por capa.

## Solución propuesta

Hacer de la matriz completa el modo estándar de evaluación de cambios defensivos. Añadir una tabla de deltas `baseline → gatekeeper → output → full`, no sólo porcentajes absolutos.

## Pruebas de aceptación

1. La run contiene los cuatro directorios de perfil.
2. Todos tienen mismo número de fixtures y repeticiones aplicables.
3. El informe atribuye cambios de métrica al salto de perfil correspondiente.
