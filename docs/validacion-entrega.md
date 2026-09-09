# Validación técnica de la entrega

Comprobaciones realizadas el 9 de septiembre de 2026 tras reorganizar el repositorio.
La limpieza no constituye una nueva campaña estadística de eficacia de las defensas.

| Comprobación | Resultado |
|---|---|
| Backend en el host (Python 3.13) | 928 tests superados |
| Backend y generadores documentales en Docker (Python 3.11) | 936 tests superados |
| Agente de red-team y generadores documentales en el host | 68 tests superados |
| Construcción de imágenes backend y frontend | Correcta; frontend instalado con lockfile congelado |
| Banco, Playground y SOC | Las tres páginas responden HTTP 200 |
| Smoke del stack con Ollama y Clara `qwen2.5:3b` | 4/4: salud del backend, proveedor, chat legítimo y ataque de muestra |
| Anexo histórico | Inventario, tamaños y SHA-256 de 455 archivos verificados |
| Documentos de fixtures | Los 11 adjuntos declarados están disponibles |
| Enlaces locales de documentación | Sin destinos de archivo ausentes en el ámbito del verificador |
| Formato del diff | `git diff --check` sin errores |

Son **996 tests distintos** entre backend, agente y generadores; las filas de la
tabla incluyen repeticiones de pruebas entre entornos. El smoke comprueba que el
pipeline responde, no que el ataque haya sido contenido ni que la respuesta sea
financieramente correcta.

## Cambios necesarios para reproducir las comprobaciones

- Los payloads viven en `lab/payloads/`, también montados en Docker. Se comprueba
  su disponibilidad con los layouts del host y del contenedor, y con una ruta alternativa.
- Las pruebas de rutas construyen ambos layouts y ya no presuponen que se ejecutan
  dentro de la estructura de directorios del host.
- La prueba de procedencia utiliza un commit de test inyectado, sin exigir que Docker
  monte `.git`. La aplicación conserva la distinción entre procedencia desconocida y limpia.
- El cálculo de la huella de un diff admite texto histórico no UTF-8 y preserva sus bytes.

## Repetir la validación

Desde la raíz del repositorio, con las dependencias Python instaladas:

```bash
python3 lab/scripts/check_delivery.py
python3 -m pytest lab/backend/tests -q
python3 -m pytest lab/redteam-agent/tests lab/payloads/test_payloads.py -q
```

Para el entorno Docker, desde `lab/` y con el stack en marcha:

```bash
make test
docker compose exec -T backend python -m pytest /app/payloads/test_payloads.py -q
make smoke
```

La validación completa usa un servidor HTTP efímero local en algunas pruebas y
necesita permiso para abrirlo. El smoke requiere acceso al Ollama local.
Los comandos de reproducción de la campaña completa están en
[DEMO_FULL_SUITE.md](../DEMO_FULL_SUITE.md).
