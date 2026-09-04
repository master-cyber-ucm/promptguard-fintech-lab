# Contrato versionado de evidencia de Tools

Estado: **aceptado**.

Las Tools, los Session Files y el Analyze Pass compartirán un contrato de resultado JSON versionado con estados canónicos, y distinguirán los argumentos solicitados por el modelo de los atributos resueltos por el backend. Se elige esta frontera porque las métricas y los controles de autorización no pueden inferirse con seguridad desde texto libre ni atribuir al modelo valores que determina la sesión autenticada.

## Considered Options

- Relajar fixtures o inferir éxito desde la respuesta conversacional: menor cambio inmediato, pero no prueba el efecto ni distingue denegación, fallo técnico y éxito.
- Mantener estados y mezcla actual de argumentos/resultado: conserva compatibilidad superficial, pero produce falsos positivos y deja ambigua la autoridad de `from_account`.
- Contrato versionado con lectura legada compatible (elegida): requiere adaptar productores y evaluador, pero preserva la evidencia histórica y establece una base verificable para las nuevas corridas.
