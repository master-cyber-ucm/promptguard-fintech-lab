# Dos almacenes para la traza de un turno

Lo que ocurre en un turno se persiste en dos sitios con propósitos distintos: el **Session File** en Markdown (evidencia del TFM) y la base SQLite del **SOC** (proyección consultable para el dashboard en vivo). Ambos se escriben desde el mismo punto de `_process_chat`, a partir de los mismos datos.

El SOC necesita responder en vivo a preguntas como "¿qué componente bloqueó más?" o "enséñame la traza de esta sesión", y necesita hacerlo mientras alguien ataca desde el Playground. Los Session Files no sirven para eso: son Markdown pensado para leerse, y consultarlos implicaría parsear ficheros en cada petición — frágil y lento. Pero tampoco se pueden sustituir: son la evidencia que citan `henri-tfm/CAPITULO.md` y `daniel-tfm/CAPITULO.md`, los consume `evaluate.py` para calcular Verdicts, y de ellos salen los Run Reports. Se escriben en el momento del turno, que es justamente la propiedad que los hace buena evidencia forense.

La duplicación es real y se asume a conciencia. El riesgo que introduce —divergencia entre los dos almacenes— se mantiene bajo porque ninguno deriva del otro: los dos se escriben en el mismo instante desde la misma estructura en memoria. El coste de la alternativa (unificar) era desproporcionado: tocar `audit_repository`, el flujo de la suite y potencialmente `evaluate.py`, con 156 tests y dos capítulos ya redactados apoyados en ese formato, y con la entrega cerca.

Los dos almacenes no guardan lo mismo, y esto es deliberado: el SOC registra un Analysis Event por cada componente que evaluó algo, **también cuando la acción fue `ALLOW`**, mientras que el Session File sigue recogiendo el turno tal como lo hacía. El SOC es por tanto más rico en decisiones de defensa; el Session File sigue siendo el registro humano del diálogo. Ninguno es un subconjunto del otro.

## Considered Options

- **Los Session Files como única fuente, el SOC leyéndolos**: cero duplicación, pero el dashboard tendría que parsear Markdown en cada consulta, y las decisiones `ALLOW` no están en el fichero (hoy el pipeline las descarta), así que ni siquiera estarían disponibles.
- **SQLite como única fuente, los Session Files derivados por un comando**: conceptualmente lo más limpio. Descartada por blast radius: obliga a rehacer `audit_repository`, el flujo de la suite y el Analyze Pass, y los ficheros dejarían de escribirse en el instante del turno.
- **SQLite solo para los Analysis Events, el turno solo en Markdown**: duplicación mínima, pero para pintar una traza el dashboard tendría que ir a leer el `.md` — vuelve el parseo frágil, y ahora además en caliente.
- **Dos almacenes con roles distintos (elegida)**: el Session File es la evidencia; la base del SOC es la proyección operativa. Se acepta escribir dos veces a cambio de no tocar nada de lo que ya funciona y está citado.
