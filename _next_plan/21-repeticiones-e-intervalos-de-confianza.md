# Repeticiones e intervalos de confianza para métricas de seguridad

## Descripción del problema

Cinco repeticiones permiten observar variabilidad, pero un porcentaje único puede ocultar incertidumbre. Una diferencia pequeña de FP entre perfiles puede ser ruido del modelo, juez o infraestructura.

## Evidencia observada

La [run](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md) usa cinco repeticiones por fixture. Por ejemplo, varios legítimos pasan sólo algunas repeticiones, y el FP de `proxy-full` (54,3%) está a pocos casos del baseline (51,4%). Sin intervalos no debe interpretarse esa diferencia como degradación causal.

## Explicación técnica

Cada repetición es una observación Bernoulli, aunque no totalmente independiente si comparte proveedor o estado. El informe debe conservar conteos y presentar un intervalo binomial, además de comparar perfiles por pares cuando usan el mismo fixture/repetición.

## Alternativas de mejora

### A. Diez repeticiones + intervalos Wilson y deltas pareados (recomendada)

Usar al menos diez ejecuciones para comparativas de cambio y publicar conteos, intervalo Wilson 95% y delta pareado por fixture.

### B. Sólo porcentaje redondeado

Es legible pero promueve conclusiones excesivas.

## Solución propuesta

Ampliar a diez repeticiones para experimentos de decisión, mantener cinco para smoke tests y no afirmar mejora si los intervalos/deltas pareados no sostienen la diferencia.

## Pruebas de aceptación

1. `run.json` conserva éxitos y total, no sólo porcentaje.
2. `run.md` muestra intervalo y número de repeticiones.
3. Un informe marca diferencias no concluyentes.
