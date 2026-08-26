# Fixtures servidos via endpoint de backend, no pre-generados como JSON estático

Los fixtures son archivos YAML en el árbol de tests del backend. El Playground necesita listarlos y cargarlos. Decidimos exponerlos mediante `GET /api/v1/fixtures` en el FastAPI existente, usando el `fixture_loader.py` ya disponible, en lugar de pre-generar un JSON estático en build time.

La razón principal es consistencia: añadir nuevos fixtures YAML queda reflejado en el Playground sin paso de build. Un JSON estático requeriría regenerarlo manualmente o añadir un script de sincronización que no aporta valor en un entorno de lab.

## Considered Options

- **JSON estático en build time**: más simple de servir (sin código nuevo en el backend), pero desincronizado con los fixtures hasta que alguien regenera.
- **Endpoint en backend (elegida)**: una línea de responsabilidad clara — el backend conoce sus propios fixtures y los expone con interpolación de variables ya resuelta.
