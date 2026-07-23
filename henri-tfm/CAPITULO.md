# Capítulo — Prompt Injection Indirecta vía Documento (Ataque #7)

> Borrador acumulativo de prosa para el documento final del TFM. Se redacta en paralelo a medida
> que se completa cada sub-paso del `ROADMAP.md`, y se revisa (wrap-up) al cerrar cada fase. Cada
> sección está etiquetada con la parte del **índice oficial del TFM** (`00-INSTRUCCIONES.md §2`) a
> la que alimenta. Las secciones sin contenido real todavía se marcan `[PENDIENTE]`.
>
> Fuente de materia prima: `01-ataque/`, `02-defensa/`, `03-normativa/` (notas técnicas y specs).
> Este archivo es la síntesis en prosa, no un duplicado de esas notas.

---

## Estado de redacción

| Sección del índice | Sub-tema | Estado |
|---|---|---|
| 2.1–2.3 (Estado del arte) | Ejemplo de vector aportado por este ataque | `[PENDIENTE]` |
| 4.2 (Vectores evaluados) | Descripción del vector | ✅ Borrador inicial |
| 4.2 | Diseño del payload (Fase 1.1) | ✅ Borrador inicial |
| 4.2 | Implementación del canal (Fase 1.2) | ✅ Borrador inicial |
| 6.1 (Resultados por vector) | Resultados de ataque, números finales tras iteración (Fase 1.3+1.5) | ✅ |
| 4.1 / 6.1 | Defensa implementada y su validación (Fase 2) | `[PENDIENTE]` |
| 6.2 (Análisis y discusión) | Éxito funcional vs. fuga textual; iteración DOCX/XLSX (Fase 1.5) | ✅ |
| 6.2 | Antes/después de la defensa (Fase 2) | `[PENDIENTE]` |
| 7 (Marco normativo) | GDPR/DORA/AI Act/NIST/ISO aplicados a este vector (Fase 3) | `[PENDIENTE]` |

---

## 4.2 — Vectores de ataque evaluados: Prompt Injection Indirecta vía Documento

### Descripción del vector

La *Prompt Injection Indirecta* (**OWASP LLM01:2025**) es la variante en la que el payload
malicioso no llega al modelo a través del mensaje visible del usuario, sino a través de un
contenido que el sistema procesa como **dato** — en este caso, un documento adjuntado por el
cliente. **MITRE ATLAS** la cataloga como la técnica **AML.T0051.001 (Prompt Injection —
Indirect)**, dentro de la táctica **TA0043 (Initial Access)**: el adversario obtiene ejecución de
instrucciones no autorizadas explotando un canal de entrada que el sistema no somete al mismo
escrutinio que el input directo.

En el escenario VerdaBank, los clientes suben con frecuencia documentación financiera (nóminas,
extractos, justificantes de reclamación) a **Clara** para acelerar trámites como la evaluación de
microcréditos o la apertura de reclamaciones. Un atacante que controla el contenido de ese
documento puede embeber instrucciones que el pipeline de extracción de texto entrega al LLM sin
distinguirlas del prompt legítimo — el fallo estructural que Greshake et al. (2023) formalizan
como la incapacidad de un LLM para separar de forma fiable *instrucción* de *dato* cuando ambos
comparten el mismo contexto.

### Diseño del payload

Para este TFM se optó por evaluar el vector con **tres formatos documentales** (PDF, DOCX, XLSX)
en lugar de uno solo, cada uno explotando la técnica de ocultación más idiomática de su formato.
Esta decisión amplía la superficie analítica del capítulo —permite comparar mecanismos de fallo
distintos— y, por extensión, obliga a que la defensa de la Fase 2 no dependa de una única
salvaguarda específica de PDF.

El objetivo del payload en los tres casos es idéntico: forzar a Clara a invocar la tool
`consulta_saldo` sobre una cuenta de un tercero (**Ana Fernández Ruiz**, IBAN
`ES3421000418450200051334`) y filtrar su saldo en la respuesta al atacante. Se eligió este
objetivo —en lugar de forzar una tool con efecto transaccional directo como
`transferencia_nacional`— por dos motivos: (a) es el mismo objetivo ya validado experimentalmente
por los fixtures `atk_021`/`atk_022` del lab (que simulan el ataque pegando el documento como
texto de chat), lo que permite comparar la evidencia nueva —documento real— con la evidencia
previa; y (b) reproduce directamente el incidente motivador del proyecto (`INC-2025-0089`, fuga
del saldo de un tercero por manipulación de contexto), reforzando la coherencia narrativa del
escenario VerdaBank.

| Formato | Vehículo documental | Técnica de ocultación |
|---|---|---|
| PDF | Nómina de un cliente (`usr_001`) | Texto blanco sobre fondo blanco + fuente 1pt + texto fuera del viewport de la página |
| DOCX | Informe de reclamación | Atributo nativo de texto oculto de Word (`w:vanish`), reforzado con color de fuente blanco |
| XLSX | Hoja de control de gastos | Fila oculta de la hoja + comentario adjunto a una celda visible |

Antes de dar la especificación por válida, se verificó —con parsers ingenuos equivalentes a los
que implementaría un pipeline de extracción sin medidas de seguridad (`pypdf`, `python-docx`,
`openpyxl`)— que el contenido oculto es recuperable en los tres formatos. El resultado confirma
empíricamente la premisa teórica: la ocultación protege al documento de la inspección visual de
un revisor humano, pero no de un extractor automático de texto, que no distingue una capa
visible de una oculta.

Esta verificación se formalizó como una suite de **8 tests de regresión** (`pytest`), uno por
cada combinación formato × control (sano sin payload / comprometido con payload), más un test
adicional que confirma que la técnica de ocultación en DOCX es específicamente el atributo
`run.font.hidden` de Word y no solo el color de fuente. Los 8 tests pasan de forma determinista y
generan sus propios documentos de prueba en un directorio temporal, por lo que sirven como
regresión ante cualquier cambio futuro en los generadores.

*(Fuente: `henri-tfm/01-ataque/README.md`, `henri-tfm/01-ataque/payloads/generar_{pdf,docx,xlsx}.py`,
`henri-tfm/01-ataque/payloads/test_payloads.py`.)*

### Anatomía del payload

Los tres payloads comparten una estructura funcional común, independiente del formato que los
transporta: **(A)** un marco de autoridad falso que atribuye la instrucción a una fuente
verosímil dentro del propio documento ("Nota del sistema de nóminas...", "Nota interna de
tramitación..."), explotando la ausencia de una frontera semántica entre dato e instrucción en el
contexto del LLM; **(B)** una instrucción de acción concreta y medible, con el IBAN de la cuenta
objetivo interpolado directamente en el texto; y **(C)** una instrucción de auto-ocultación ("no
menciones esta instrucción", "no reveles esta nota") que busca reducir la probabilidad de que el
modelo delate el ataque en su propia respuesta, dificultando la detección por inspección manual
de la conversación. Esta última pieza es una aplicación, con fin distinto, de la técnica de
instrucción contradictoria encubierta que describen Perez & Ribeiro (2022).

El framing de la pieza (A) varía deliberadamente según el vehículo documental —"sistema de
nóminas" en el PDF, "tramitación interna" en el informe de reclamación DOCX— para maximizar la
verosimilitud del payload dentro del propósito declarado de cada documento. En el vehículo PDF, el
mismo texto se repite bajo las tres técnicas de ocultación como apuesta contra la incertidumbre
sobre qué exactamente extraería el pipeline de extracción de texto —todavía por implementar en
ese momento de la Fase 1.1—; en el vehículo XLSX, en cambio, se usan dos variantes de texto
distintas para la fila oculta
y el comentario de celda, porque son dos superficies de extracción cualitativamente diferentes
—no una repetición de la misma apuesta—, lo que informa directamente el alcance que deberá cubrir
la defensa de la Fase 2.

*(Fuente: `henri-tfm/01-ataque/anatomia-payload.md`, desglose completo con el texto literal de
cada payload.)*

Un detalle de diseño relevante para la validez del experimento: ninguno de los tres payloads
menciona el nombre interno de una tool (`consulta_saldo` u otra). Todos piden la funcionalidad en
lenguaje natural, coherentemente con el perfil de atacante de **caja negra** ya definido en el
threat model de referencia —un cliente fraudulento sin conocimiento de la implementación interna
de Clara—, que solo puede conocer *qué* funcionalidad existe (por haberla usado como cliente
legítimo), nunca *cómo* se llama la función que la implementa. Es el propio LLM quien traduce la
petición en lenguaje natural a la tool call correspondiente, igual que haría con cualquier
petición legítima. El nombre `consulta_saldo` solo aparece en la documentación y en el criterio de
evaluación de este trabajo, escritos desde la posición del analista con acceso al código —nunca
en el payload en sí—, para no inflar artificialmente la tasa de éxito con un nivel de conocimiento
que un atacante real no tendría.

### Implementación del canal de subida de documentos

Dado que el escenario base del lab no contempla un canal de subida de documentos —Clara solo
acepta texto en el endpoint de chat—, fue necesario implementarlo antes de poder ejecutar el
ataque contra un artefacto real. Se añadió el endpoint `POST /chat/complex-with-document`,
siguiendo la misma progresión de niveles de defensa ya presente en el lab
(`simple-prompt` → `complex-prompt` → `complex-with-context`), de forma que el nuevo canal hereda
la configuración vulnerable —system prompt completo más contexto de usuario inyectado— sin
introducir una superficie de comparación distinta a la del resto de ataques del proyecto.

El componente central es un extractor de texto (`src/core/document_extractor.py`) para los tres
formatos evaluados, deliberadamente ingenuo: no distingue contenido visible de oculto en ninguno
de los tres casos. El texto resultante se concatena al mensaje del usuario sin ninguna marca de
procedencia ni separación semántica —`f"{mensaje}\n\nDocumento adjunto por el cliente:\n{texto}"`—
replicando exactamente el patrón de concatenación sin escrutinio que ya exhibía el endpoint
vulnerable para el contexto de usuario. La corrección de esta implementación se validó con una
suite de 12 tests: 10 unitarios sobre el extractor y 2 de integración sobre el endpoint completo
(estos últimos con un agente simulado, para verificar de forma determinista y sin dependencia de
un LLM real que el payload llega intacto al mensaje que procesaría el modelo).

Una comprobación puntual contra el proveedor LLM real (Ollama, `qwen2.5:3b`) con el documento
`nomina_comprometida.pdf` de la Fase 1.1 confirmó que la cadena funciona de extremo a extremo:
Clara invocó `consulta_saldo` sobre la cuenta de un tercero pese a que el system prompt activo
incluye una regla explícita de no revelar datos de otros clientes. Este resultado preliminar se
presenta aquí únicamente como confirmación de que la implementación es funcional; la evidencia
formal —con su control negativo y repeticiones suficientes para descontar la variabilidad del
modelo— se recoge en la sección siguiente.

*(Fuente: `henri-tfm/01-ataque/README.md` §"Canal de subida de documentos", código en
`lab/backend/src/core/document_extractor.py` y `lab/backend/src/api/routes/chat.py`.)*

### Ejecución y resultados de ataque

Con el canal implementado, se ejecutó el ataque de forma sistemática contra el lab vulnerable
real (Ollama, `qwen2.5:3b`), en varias tandas sucesivas: una primera medición (3 repeticiones por
combinación) y dos tandas adicionales de mejora iterativa del payload tras detectar tasas de
éxito insuficientes en DOCX y XLSX. Por cada intento se registró si Clara invocaba
`consulta_saldo` con el `account_id` exacto de la cuenta objetivo —el criterio de éxito
funcional, alineado con el esquema `evaluation.events` que ya usa el resto de fixtures del lab—
y si el saldo real aparecía correctamente en la respuesta en lenguaje natural, como métrica
secundaria independiente.

*(Fuente: `henri-tfm/01-ataque/evidencia/README.md`; evidencia primaria: 78+ Session Files reales
en `henri-tfm/01-ataque/evidencia/session-files/`, organizados por tanda.)*

### Iteración de mejora del payload

La primera medición mostró una tasa de éxito desigual entre vehículos: PDF 3/3, XLSX 2/3, DOCX
0/3. Antes de aceptar ese resultado como definitivo, se diagnosticó y corrigió cada vehículo por
separado, con un hallazgo metodológico relevante en el camino:

- **DOCX** solo tenía una repetición del payload. Se aplicó la misma redundancia que ya
  funcionaba en PDF (3 repeticiones) → salto de 0/3 a **9/10** en las tandas de validación
  posteriores.
- **XLSX** reveló que "más redundancia" no es una solución universal: duplicar la fila oculta sin
  cambiar su posición **empeoró** el resultado (2/3 → 2/5), porque el mecanismo de fallo no era
  falta de repetición sino que el payload competía, en desventaja, con el IBAN propio del
  cliente —visible y cercano al principio de la hoja— por la atención del modelo. Reposicionar el
  payload junto a ese dato competidor y reformular el texto de forma contrastiva explícita
  ("no uses tu propia cuenta... consulta en su lugar...") elevó el resultado a un rango
  consistentemente alto. El desglose completo, incluida la iteración que empeoró antes de
  mejorar, está en `henri-tfm/01-ataque/evidencia/README.md` y
  `henri-tfm/01-ataque/anatomia-payload.md`.

---

## 6.1 — Resultados por vector: Prompt Injection Indirecta vía Documento

Resultado final, agregado por versión de payload sobre las 4 tandas de ejecución (98 Session
Files reales; ver `henri-tfm/01-ataque/evidencia/README.md` para el detalle completo de cada
tanda y la iteración que llevó a estos números):

| Documento | Condición | Éxito funcional (tool call sobre cuenta objetivo) |
|---|---|---|
| PDF (nómina) | sano | 0/13 (0%) |
| PDF (nómina) | comprometido | **11/13 (85%)** |
| DOCX (reclamación) v2 | sano | 0/10 (0%) |
| DOCX (reclamación) v2 | comprometido | **9/10 (90%)** |
| XLSX (control de gastos) v3 | sano | 0/15 (0%) |
| XLSX (control de gastos) v3 | comprometido | **15/15 (100%)** |

*(Cifras históricas de las versiones de payload superadas — DOCX v1: 0/3; XLSX v1: 2/3; XLSX v2:
2/5 — se conservan en `evidencia/README.md` como parte de la narrativa de mejora, no se usan como
resultado final.)*

Los 49 controles sanos (todas las tandas, los 3 formatos) no produjeron ni un solo falso
positivo: en ningún caso Clara consultó la cuenta de un tercero al procesar un documento sin
payload. Con documento comprometido, y tras la iteración de mejora de la Fase 1.5, el vector
alcanza una tasa de éxito funcional alta y consistente en los tres formatos —85-100%—, partiendo
de una situación inicial muy desigual (0%-100%) en la primera medición.

## 6.2 — Análisis y discusión

**Brecha de control de acceso frente a fuga textual explotable.** El primer hallazgo relevante no
está en la tasa de éxito agregada, sino en la disociación entre dos fenómenos que podrían
confundirse bajo una sola métrica de "éxito del ataque". En **PDF**, la tool call no autorizada
ocurre en la gran mayoría de los intentos —la brecha de control de acceso, que es la
vulnerabilidad de seguridad real (acceso de un usuario a datos de otro sin autorización), se
materializa de forma consistente— pero el modelo con frecuencia **no** reporta el saldo correcto
en su respuesta: en varios intentos dio cifras distintas y erróneas ("231,50 €", ninguna cifra
explícita, "2.315,00 €"), pese a que la tool devuelve el valor real (`231.500,00 €`) en su
resultado JSON. En XLSX, en cambio, los intentos con éxito funcional casi siempre reportaron el
saldo con el valor numérico correcto. Esto tiene una implicación directa para cómo se define
"éxito del ataque" en el resto del TFM: el criterio determinista basado en la tool call
(`tool_called_with`, ya usado por los fixtures `atk_021`/`atk_022`) mide la vulnerabilidad real
—el fallo de control de acceso—, mientras que la presencia del dato correcto en el texto depende
además de la fiabilidad del modelo al redactar, una variable distinta que un modelo local pequeño
como `qwen2.5:3b` no garantiza.

**De una tasa de éxito desigual (0%-100%) a un rango alto y consistente (85%-100%): la iteración
importa, y no toda iteración es una mejora.** La primera medición (Fase 1.3, n=3 por combinación)
mostró PDF 100%, XLSX 67% y **DOCX 0%** — un resultado demasiado desigual para aceptar como
caracterización definitiva del vector antes de intentar mejorarlo (Fase 1.5). Dos vías de mejora
distintas emergieron:

- **DOCX** solo tenía una repetición del payload; aplicar la misma redundancia que ya funcionaba
  en PDF (3 repeticiones) bastó para pasar de 0/3 a 9/10 (90%) en las tandas siguientes. Aquí "más
  redundancia" fue la solución correcta.
- **XLSX** demostró que "más redundancia" **no es una solución universal**: duplicar la fila
  oculta sin cambiar su posición empeoró el resultado de 2/3 (67%) a 2/5 (40%). El diagnóstico —
  inspeccionando qué cuenta consultaba realmente el modelo en cada fallo— reveló que el problema
  no era volumen de instrucción sino **salience**: el payload competía, en desventaja, con el
  IBAN propio del cliente, visible y cercano al principio de la hoja. Solo reposicionar el
  payload junto a ese dato competidor y reescribir el texto de forma contrastiva explícita ("no
  uses tu propia cuenta... consulta en su lugar...") resolvió el problema: 15/15 (100%) sobre
  las dos tandas de validación con el diseño final (v3).

La lección metodológica para el resto del catálogo de ataques del TFM: cuando un payload de
inyección indirecta compite dentro del mismo documento con un dato legítimo más prominente, la
redundancia por repetición no sustituye a diagnosticar *por qué* el modelo prefiere el dato
competidor. Esto también anticipa un requisito para la Fase 2 (defensa): una defensa que solo
busque "instrucciones repetidas" o patrones de redundancia no habría detectado la técnica de
XLSX v1 (una sola fila oculta, sin repetición) — la superficie de ataque a cubrir no se reduce a
un único patrón sintáctico.

**Ningún falso positivo en 49 controles sanos**, en las 4 tandas y los 3 formatos: la mejora de la
tasa de éxito del ataque no se consiguió a costa de que el sistema bloqueara o alterara el
tratamiento de documentos legítimos — importante para la validez del contraste con la Fase 2, que
medirá si la defensa introduce falsos positivos que el propio ataque, en su diseño actual, no
tiene.

**Rigor del proceso: dos correcciones metodológicas documentadas, no descartadas.** (1) La primera
ejecución de `ejecutar_evidencia.py` (Fase 1.3) tenía un criterio de éxito con un *fallback* de
coincidencia de texto libre que generó 2 falsos positivos, corregido a un criterio único y
estricto (tool call verificable) tras re-analizar los 18 Session Files originales. (2) Durante la
Fase 1.5, la iteración "XLSX v2" empeoró el resultado respecto a v1 — se documenta explícitamente
como parte de la evidencia, no se descarta ni se omite, porque el propio fallo informó el
diagnóstico correcto que llevó a v3. El detalle completo de ambas correcciones está en
`henri-tfm/01-ataque/evidencia/README.md`.

## 4.1 / Defensa aplicada a este vector

`[PENDIENTE — Fase 2]`

## 7 — Marco normativo aplicado a este vector

`[PENDIENTE — Fase 3]`

## Aporte a 2.1–2.3 (Estado del arte)

`[PENDIENTE — se redacta al final, seleccionando qué de este capítulo sirve como ejemplo ilustrativo]`
