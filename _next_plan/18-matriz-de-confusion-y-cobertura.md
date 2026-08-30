# Publicar matriz de confusión y cobertura del evaluador

## Descripción del problema

Los porcentajes de bloqueo y FP no indican cuántos casos están mal clasificados ni cuántos no pudieron evaluarse. Sin TP, FP, TN, FN e inconclusos, no se puede saber si una variación mejora detección o sólo cambia el sesgo del juez.

## Evidencia observada

El [informe de la run](../lab/audit/runs/20260829_151324_qwen2.5-3b/run.md) muestra bloqueo, brechas y FP, pero no presenta cobertura ni causa de evaluación. Los errores del juez y las defensas que se registran como brecha quedan absorbidos por el mismo porcentaje.

## Explicación técnica

Para ataques, “positivo” significa brecha entregada o acción prohibida completada; para legítimos, “positivo” significa servicio útil y seguro. Los inconclusos deben permanecer fuera de la matriz hasta resolverlos, con cobertura visible.

## Alternativas de mejora

### A. Matrices separadas por objetivo (recomendada)

Publicar una matriz de seguridad para ataques y otra de utilidad para tráfico legítimo, ambas con `INCONCLUSIVE` y enlaces a casos. Desglosar por endpoint, familia y defensa.

### B. Un porcentaje global

Es compacto, pero no permite detectar compensaciones entre FN y FP.

## Solución propuesta

Derivar las matrices de resultados estructurados y del golden set. Guardar numeradores, denominadores y cobertura; nunca calcular porcentajes a partir de texto renderizado.

## Pruebas de aceptación

1. Cada celda de la matriz enlaza a sus Session Files.
2. Los inconclusos se muestran fuera del denominador principal.
3. La suma de celdas coincide con el número de sesiones procesadas.
