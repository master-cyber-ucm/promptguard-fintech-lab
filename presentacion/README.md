# Presentación de PromptGuard FinTech

Abre `index.html` en un navegador. La presentación contiene 25 diapositivas y funciona sin conexión, sin instalación y sin servidor. Conserva los SVG junto al HTML.

- Flechas, espacio o Page Down: avanzar. Flecha izquierda o Page Up: retroceder.
- `I`: índice. `N`: notas del ponente. `F`: pantalla completa.
- Inicio / Fin: primera / última diapositiva. Escape: cerrar un diálogo.
- En pantallas táctiles, desliza horizontalmente para navegar.
- El botón PDF abre la impresión del navegador. Selecciona guardar como PDF, papel A4 horizontal, sin encabezados/pies del navegador y con gráficos de fondo.

Propuesta de duración: 20–25 minutos. Las notas contienen matices y referencias para preparar la exposición; se abren sobre la presentación y son visibles en la pantalla proyectada. No constituyen una ventana privada de presentador.

## Contenido y fuentes

La narración sigue `../TFM Grupo 2 (2).md` y las correcciones acordadas durante su revisión. Para resultados cuantitativos usa las tablas reconciliadas de `../revision-final/tablas-corregidas.md`, distinguiendo clasificación automática de efecto confirmado. Conserva los límites de cobertura, procedencia y utilidad.

En particular, presenta 11/30 vulnerables automáticos para las diez variantes originales de inyección directa, en lugar del 23/30 histórico que aún figura en la memoria. No presenta como acreditados los 120 intentos del agente adaptativo cuyo directorio de campaña no está en la copia entregada.

El HTML incluye sus estilos y navegación; la diapositiva 6 utiliza una imagen SVG local. Los enlaces documentales de las notas y de la última diapositiva requieren mantener esta carpeta dentro del repositorio. El documento original y las evidencias no se modifican.

## Matriz MITRE ATLAS

La diapositiva 6 muestra un recorte legible de las técnicas seleccionadas y enlaza la matriz completa resaltada:

- `atlas-seleccion.svg`: cinco tácticas asociadas a la selección.
- `atlas-matriz-completa.svg`: las 16 tácticas, las 114 técnicas principales y las dos subtécnicas seleccionadas desplegadas. Las demás subtécnicas no están expandidas.
- `ATLAS-2026.08-oficial.yaml`: datos originales de la [publicación oficial v2026.08](https://github.com/mitre-atlas/atlas-data/releases/tag/v2026.08), descargados el 16/09/2026. El conjunto incluye 114 técnicas y 83 subtécnicas.

Ambos SVG son visualizaciones propias de los datos oficiales, no capturas de la web de MITRE. El verde identifica la selección, no resultados experimentales ni cobertura completa de una táctica. Se respeta el mapeo oficial: AML.T0053 figura también en Lateral Movement.

| Estudio | Técnica / subtécnica ATLAS |
| --- | --- |
| 5.1 · Prompt de sistema | AML.T0056 · Extract LLM System Prompt |
| 5.2 · Inyección directa | AML.T0051.000 · Direct |
| 5.3 · Contexto cruzado | AML.T0057 · LLM Data Leakage |
| 5.4 · Documentos | AML.T0051.001 · Indirect |
| 5.5 · Evasión | AML.T0054 · LLM Jailbreak |
| 5.6 · Agencia excesiva | AML.T0053 · AI Agent Tool Invocation |

El mapeo resume el foco de cada estudio; no es una equivalencia exhaustiva. En particular, el estudio 5.5 comparte también superficie con la inyección directa.

SHA-256 del YAML oficial: `a8d32f676854cc57721c217ec5b39f07db518076dee4a6c1335df0a7bc8271a2`.

## Edición

El contenido está en la constante `slides` de `index.html`. Cada diapositiva incluye título, sección, contenido HTML, fuente y notas. Los estilos y la navegación están en ese mismo archivo. Los gráficos conservan etiquetas numéricas y denominadores para permitir revisar las cifras.
