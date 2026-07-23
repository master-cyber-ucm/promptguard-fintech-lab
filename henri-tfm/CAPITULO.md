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
| 4.2 | Implementación del canal (Fase 1.2) | `[PENDIENTE]` |
| 6.1 (Resultados por vector) | Resultados de ataque (Fase 1.3) | `[PENDIENTE]` |
| 4.1 / 6.1 | Defensa implementada y su validación (Fase 2) | `[PENDIENTE]` |
| 6.2 (Análisis y discusión) | Antes/después de la defensa | `[PENDIENTE]` |
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
sobre qué exactamente extraerá el pipeline de extracción de texto (aún no implementado — Fase
1.2); en el vehículo XLSX, en cambio, se usan dos variantes de texto distintas para la fila oculta
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

`[PENDIENTE — Fase 1.3, alimenta también la sección 6.1]`

---

## 6.1 — Resultados por vector: Prompt Injection Indirecta vía Documento

`[PENDIENTE]`

## 6.2 — Análisis y discusión

`[PENDIENTE]`

## 4.1 / Defensa aplicada a este vector

`[PENDIENTE — Fase 2]`

## 7 — Marco normativo aplicado a este vector

`[PENDIENTE — Fase 3]`

## Aporte a 2.1–2.3 (Estado del arte)

`[PENDIENTE — se redacta al final, seleccionando qué de este capítulo sirve como ejemplo ilustrativo]`
