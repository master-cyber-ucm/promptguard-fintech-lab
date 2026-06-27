# Sesiones de auditoría como ficheros Markdown, una por sesión

Cada sesión de chat con Clara genera un fichero `.md` en `lab/audit/sessions/`. El Audit Repository hace append de cada turn al fichero en cuanto se completa, sin esperar al fin de la sesión.

Se eligió Markdown sobre JSONL o SQLite porque el objetivo inmediato es evidencia auditable a nivel de debug — un fichero `.md` es legible directamente sin herramientas, facilita la revisión manual de ataques, y puede incluirse literalmente como anexo en la memoria del TFM. La estructura por turn (prompt → razonamiento → tools → respuesta) es suficiente para los pasos 1–3 del roadmap.

## Considered Options

- **JSONL por sesión**: más fácil de parsear programáticamente, menos legible sin herramientas.
- **SQLite**: permite queries y agregaciones, pero añade dependencia de infraestructura y no genera artefactos directamente citables en la memoria.
- **Markdown por sesión (elegida)**: cero dependencias, legible en cualquier editor, citeable directamente, extensible con secciones nuevas sin romper el formato.
