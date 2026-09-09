# Alcance y limitaciones

## Implementación entregada

El laboratorio simula operaciones bancarias con datos sintéticos y evalúa prompt
injection directa e indirecta, fuga de datos, uso indebido de herramientas y fuga
del system prompt. Incluye experimentos acotados de consumo de recursos (LLM10).

El proxy aplica firmas de entrada, protección de PII, control de herramientas,
auditoría de salida y guardia de fuga. El canal documental añade extracción,
sanitización y detección estructural. La configuración de cada ejecución identifica
qué controles se activaron; `baseline` y `vulnerable` son dimensiones diferentes.
Véanse [ADR-0017](adr/0017-matriz-de-ablaciones-y-gate-de-reproducibilidad.md) y
[ADR-0018](adr/0018-documento-como-capacidad-de-los-endpoints-existentes.md).

La evaluación distingue resultado de ejecución, evidencia de efecto, seguridad y
utilidad. El [contrato de métricas](metricas/contrato-metricas.md) define los
criterios y denominadores que deben acompañar las cifras.

## Límites de las conclusiones

- Una tasa experimental describe el modelo, las fixtures, la postura y las
  repeticiones de esa medición. No garantiza seguridad frente a ataques desconocidos.
- Las firmas deterministas cubren patrones declarados. La ofuscación y los ataques
  nuevos pueden evadirlos; los controles posteriores aportan defensas adicionales.
- El modelo puede rechazar un ataque por su propio entrenamiento. Para atribuir el
  resultado a una defensa se necesitan posturas comparables y evidencia del control.
- Un juez semántico también puede equivocarse. Los casos sin evidencia suficiente y
  los errores técnicos deben permanecer visibles; no son éxitos de la defensa.
- Los resultados de campañas antiguas no describen automáticamente el código final.
  El [anexo histórico](evidencias/README.md) conserva los originales sin reinterpretarlos.
- La autenticación usa un emisor de pruebas. En modo de compatibilidad se admite
  identidad no verificada; no equivale a un proveedor de identidad de producción.
- El SOC almacena prompts y respuestas en claro. Los datos son sintéticos; una
  implantación real requeriría políticas de minimización, retención y acceso.
- Las pruebas de consumo son acotadas. No constituyen una validación de capacidad
  bajo carga de producción ni de resistencia a bombas ZIP o documentos arbitrarios.

## Trabajo futuro

Ampliar la muestra y los modelos, calibrar el juez con revisión humana, estudiar
variantes no vistas, medir carga en un entorno aislado y completar controles de
tamaño documental y patrones de extracción. Estas líneas no se presentan como
funcionalidad validada de la entrega.
