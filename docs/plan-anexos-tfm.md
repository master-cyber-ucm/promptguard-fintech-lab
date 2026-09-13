# Plan de trabajo sobre la sección de anexos del TFM

Documento de planificación. **No aplica ningún cambio al TFM**: define el orden en que
se abordarán, qué material existe para cada uno y cuándo se considera cerrado cada paso.
Las propuestas concretas de redacción se entregarán en iteraciones posteriores, una fase
por iteración.

- **Documento de referencia:** `TFM Grupo 2 - actualizado 13-9-26.docx` (443 párrafos, 19 tablas).
- **Reportes de revisión de partida:** 01 números y métricas (20 entradas), 02 contenido
  técnico (23), 03 revisión académica (31), 04 narrativa y alcance (35). Total: 109 recomendaciones.
- **Material de apoyo en el repositorio:** rama `doc-tfm`, `docs/evidencias/`, `log-examples/`,
  `docs/anexo-catalogo-ataques-llm.md`.
- **Fecha:** 13 de septiembre de 2026.

---

## 1. Punto de partida: qué hay hoy en el capítulo 10

El capítulo de anexos existe y tiene estructura, pero su grado de terminación es muy desigual.
Conviene verlo como una casa con las habitaciones construidas y solo algunas amuebladas.

| Anexo | Estado real | Contenido |
|---|---|---|
| A. Catálogo de ataques y criterios de selección | **Vacío** | Cinco párrafos (A.1–A.5) que describen lo que debería contener. Cero tablas. Es una promesa, no un anexo. |
| B. Tablas de resultados por vector | **Lleno pero sin sanear** | B.1 a B.8, con 14 tablas reales. Es donde se concentran las cifras que los cuatro reportes señalan (100 %, 0 falsos positivos, 85-100 %, semáforo de cumplimiento). B.7.b dice literalmente «Pendiente de completar». |
| C. Reproducibilidad | **Lleno, con rutas caducadas** | C.1 a C.6, con comandos. Varios apuntan a rutas que hoy son entradas del ZIP histórico, no directorios operativos. |
| D. Evidencia y trazas | **Lleno, con el mismo problema** | D.1 a D.7, lista de rutas del repositorio. No menciona `log-examples/` ni `docs/evidencias/`. |
| E. Notas de ingeniería y limitaciones | **Lleno, con dos afirmaciones a corregir** | E.1 a E.5. |

Lo que **no existe** y hace falta:

- El anexo de la matriz MITRE ATLAS (petición del equipo).
- Un anexo de aportaciones individuales del equipo (lo piden los reportes 3.22 y 4.33; hoy vive
  suelto como apartado 8.6, con una nota de redacción pendiente).
- Un anexo que diga dónde está realmente la evidencia entregada: el cuerpo remite a «los anexos C y D»,
  pero ninguno de los dos nombra el ZIP histórico, el manifiesto ni la ejecución de ejemplo.

**Por qué esto importa más de lo que parece.** La guía limita el cuerpo a 20 caras y excluye los
anexos de ese cómputo. Cada tabla, captura y bloque de comandos que baja al anexo libera espacio
en el cuerpo. Los anexos son el desahogo del documento, y hoy están a medio usar.

---

## 2. Hallazgo que condiciona el orden de las fases

Se contrastaron los identificadores ATLAS del documento contra el catálogo oficial
(`mitre-atlas/atlas-data`, versión **2026.08**, 170 técnicas y 16 tácticas). El resultado obliga a
empezar por ahí, porque esos identificadores aparecen en los títulos del capítulo 5, en el cuerpo,
en la bibliografía y serían el eje del anexo de la matriz.

### 2.1. Identificadores incorrectos en el cuerpo del TFM

| Dónde | Dice | Qué es en realidad | Debería decir |
|---|---|---|---|
| Título 5.1 y §5.2.1 | `AML.T0055` para System Prompt Leakage | `AML.T0055` es **Unsecured Credentials** (táctica Credential Access) | `AML.T0056` — **Extract LLM System Prompt** (Exfiltration) |
| Bibliografía | «`AML.T0055` — LLM Prompt Self-Replication / system prompt extraction» | Mezcla tres técnicas distintas: `AML.T0061` es LLM Prompt Self-Replication | Entrada corregida con `AML.T0056` |
| Título 5.3 y §5.3.1 | `AML.T0024` para Cross-Context Leakage | `AML.T0024` es **Exfiltration via AI Inference API**, descrita sobre datos de entrenamiento | `AML.T0057` — **LLM Data Leakage** (Exfiltration) |
| Mensaje del equipo | «`AML.T0051.000` y `.001` dentro de la táctica `TA0043` (Initial Access)» | `TA0043` es un identificador de ATT&CK (Reconnaissance), no de ATLAS. Y la inyección de prompt pertenece a `AML.TA0005` (Execution) | `AML.T0051` bajo `AML.TA0005` — Execution |

### 2.2. Identificadores del catálogo (`docs/anexo-catalogo-ataques-llm.md`) que no existen

El catálogo declara «MITRE ATLAS v4» en su cabecera. Tres de sus identificadores no existen en
ninguna versión actual y dos apuntan a técnicas sin relación con el ataque descrito.

| Ataque del catálogo | Dice | Problema | Candidato correcto |
|---|---|---|---|
| Adversarial Patch (físico) | `AML.T0023` | No existe | `AML.T0041` Physical Environment Access |
| Model Extraction vía Queries | `AML.T0026` | No existe | `AML.T0024.002` Extract AI Model |
| Supply Chain Compromise | `AML.T0045` | No existe | `AML.T0010` AI Supply Chain Compromise |
| Token Cost Harvesting | `AML.T0021` | Es **Establish Accounts** | `AML.T0034` Cost Harvesting (Impact) |
| Plugin / Extension Exploitation | `AML.T0052` | Es **Phishing** | `AML.T0053` AI Agent Tool Invocation o `AML.T0110` AI Agent Tool Poisoning |

### 2.3. Técnicas que hoy existen y el proyecto no está aprovechando

ATLAS ha crecido mucho desde la v4. Hay técnicas que describen con precisión vectores que el TFM
mapea de forma vaga o deja sin mapear:

- **Excessive Agency y Confused Deputy** (ataques 1 y 4 del catálogo, hoy solo con etiqueta OWASP):
  `AML.T0053` AI Agent Tool Invocation (Execution, Privilege Escalation).
- **Evasión por ofuscación**: `AML.T0068` LLM Prompt Obfuscation (Defense Evasion).
- **RAG Poisoning**: `AML.T0070` RAG Poisoning (Persistence).
- **Reconocimiento del prompt de sistema**: `AML.T0069.002` Discover LLM System Information — System Prompt.
- **Exfiltración a través de herramientas**: `AML.T0086` Exfiltration via AI Agent Tool Invocation.

Esto es una oportunidad, no solo una corrección: permite que la matriz del anexo muestre una cadena
de ataque completa (reconocimiento → ejecución → evasión → exfiltración) en lugar de cinco etiquetas sueltas.

---

## 3. Las fases

Cada fase se aborda en una iteración independiente. El criterio de orden es la dependencia: nada
se toca antes de que esté fijado aquello de lo que depende.

### Fase 0 · Congelar el marco de referencia ATLAS

**Por qué primero.** Los identificadores están en títulos de capítulo, en el cuerpo, en la
bibliografía, en el catálogo y serían el contenido de la matriz. Corregirlos después obligaría a
rehacer todo lo construido encima.

**Qué se hace.**
1. Declarar la versión de ATLAS usada (2026.08) en el apartado 2.1 y en la bibliografía.
2. Corregir los cuatro identificadores del apartado 2.1 de este plan, en todos sus puntos de aparición.
3. Decidir el mapeo definitivo de los siete vectores del escenario base, incluidas las técnicas
   del apartado 2.3 que hoy no se usan.
4. Congelar esa tabla de mapeo como fuente única para el resto del trabajo.

**Fuente.** `dist/v6/ATLAS-latest.yaml` del repositorio `mitre-atlas/atlas-data`, ya verificado.

**Entregable.** Una tabla de mapeo de siete filas (vector, OWASP, técnica ATLAS, táctica, dónde
aparece en el documento) y la lista exacta de sustituciones a aplicar.

**Cerrado cuando.** No queda ningún identificador ATLAS en el documento que no esté en esa tabla.

**Alimenta:** reporte 3.12, 3.28.

---

### Fase 1 · Anexo A: convertir la promesa en contenido

**Por qué aquí.** El cuerpo remite al Anexo A tres veces (apartados 3.2, 5.3.1 y 8.5) para justificar
el alcance del proyecto. Es la remisión más comprometida del documento: si un miembro del tribunal
pregunta «¿por qué estos siete y no otros?», la respuesta está en un anexo que hoy no contiene la lista.

**Qué se hace.**
1. Portar el contenido de `docs/anexo-catalogo-ataques-llm.md` (ya tiene los 29 ataques en tres
   tablas: 22 relevantes, 4 no relevantes, 3 no practicables) aplicando las correcciones de la fase 0.
2. Resolver una discrepancia de fondo: el catálogo del repositorio ordena los 22 relevantes e
   incluye entre ellos ataques que el TFM asigna a extensiones. Hay que hacer explícito el corte
   entre los 7 del escenario base y los 15 de extensión, que hoy solo existe en el cuerpo.
3. Completar A.4 (las cuatro extensiones y su condición de activación), que el cuerpo cita en 8.5
   pero el catálogo no documenta.
4. Decidir el formato: la tabla del repositorio tiene seis columnas muy densas; en Word habrá que
   condensarla o partirla.

**Entregable.** Anexo A completo, con A.1 a A.5.

**Cerrado cuando.** Las tres remisiones del cuerpo al Anexo A encuentran lo que prometen.

**Alimenta:** reportes 2.01, 4.02.

---

### Fase 2 · Anexo nuevo: matriz MITRE ATLAS

**Por qué aquí.** Es la petición concreta del equipo y depende por completo de la fase 0.

**Qué se decide antes de dibujar nada.** Hay tres formatos posibles, con costes distintos:

| Opción | Qué es | A favor | En contra |
|---|---|---|---|
| Captura del Navigator | Exportar la matriz oficial desde el ATLAS Navigator con las técnicas resaltadas | Rápido; imagen reconocible | 170 técnicas en 16 tácticas; a tamaño de página A4 es ilegible |
| Matriz recortada propia | Tabla de columnas = tácticas implicadas, celdas = técnicas, resaltadas las del proyecto | Legible; se controla el contenido | Hay que construirla a mano |
| Tabla de mapeo + diagrama de cadena | Tabla vector → técnica → táctica, más un diagrama del recorrido del adversario por el pipeline | Es lo que el cuerpo dice que ATLAS aporta («en qué fase puede interrumpirse») | Dos piezas en lugar de una |

**Recomendación a discutir.** La tercera, o una combinación de la segunda y la tercera. El cuerpo
justifica el uso de ATLAS diciendo que sirve «para situar cada módulo de defensa en el punto exacto
del pipeline»; una matriz completa con cinco celdas pintadas no demuestra eso, mientras que una
cadena que vaya de la técnica al módulo que la interrumpe, sí.

**Qué se hace.**
1. Elegir formato.
2. Construir la pieza a partir de la tabla congelada en la fase 0.
3. Añadir la columna que hoy falta en todo el documento: qué módulo de PromptGuard actúa contra
   cada técnica y en qué punto del pipeline.
4. Decidir su numeración (probablemente Anexo A.6, por continuidad con el catálogo, o anexo propio).

**Entregable.** La matriz o el par tabla-diagrama, con su pie y su fuente.

**Cerrado cuando.** Cada vector del escenario base tiene técnica, táctica y módulo de defensa
localizados en la misma pieza.

**Alimenta:** petición del equipo; reporte 3.12.

---

### Fase 3 · Anexo B: sanear denominadores, etiquetas y alcance

**Por qué aquí.** Es la fase más pesada y la que concentra el riesgo académico. Se aborda después
de A y de la matriz porque esas dos son aditivas (añaden lo que falta) mientras que esta es
correctiva (cambia lo que ya está escrito), y conviene tener el marco cerrado antes de reescribir cifras.

**Qué se hace, tabla por tabla.**

| Tabla | Problema señalado | Acción |
|---|---|---|
| B.1.a | 15/15 y «0 falsos positivos» presentados como eficacia actual | Rotular como resultado histórico con su fecha; separar de la campaña integrada |
| B.2.a | Columna «Tasa final» con 100 % derivada de secuencias fallo-éxito | Sustituir por intentos, éxitos y presupuesto de reintentos declarado |
| B.3.a y B.3.b | 6/6 SUCCESS sin distinguir etiqueta del juez de evidencia de acceso | Dos columnas: evidencia de acceso y clasificación automática |
| B.4.a | 85-100 % con denominadores de tandas distintas | Denominador explícito por fila; separar campaña histórica de la integrada |
| B.4.b | Ablación con «0 % y 0 falsos positivos» | Acotar a las nueve observaciones que la sustentan |
| B.5 | Semáforo verde/amarillo de cumplimiento | Sustituir por columnas de evidencia técnica y alcance de la conclusión |
| B.6.a | Base64 «no concluyente» contradice el capítulo 5.5 | Identificar campaña, objetivo y postura de cada variante |
| B.7.a | Latencias de hasta 438,1 s sin cohorte | Separar por recorrido (bloqueo previo al modelo frente a turno permitido) |
| B.7.b | «Pendiente de completar» | Decidir: completar desde la corrida limpia, o retirar la fila y declararlo limitación |
| B.8.a–c | Tablas normativas con obligaciones dadas por resueltas | Reformular como aportación técnica y límite, sin semáforos |

**Decisión de fondo que hay que tomar antes de empezar.** Los reportes 01 y 03 proponen recalcular
cifras desde `run.json` y `executions.json`; el reporte 04 recomienda no recalcular nada y limitar
las afirmaciones. Son estrategias incompatibles y cuesta distinto tiempo cada una. Hay que elegir
una y aplicarla a las diez tablas por igual.

**Cerrado cuando.** Ninguna tabla del Anexo B publica un porcentaje sin denominador, ni una
etiqueta del juez presentada como hecho confirmado.

**Alimenta:** reportes 1.03 a 1.15, 1.19; 3.04, 3.05, 3.18; 4.10, 4.14, 4.17, 4.18, 4.20, 4.30.

---

### Fase 4 · Anexos C y D: que las rutas lleven a donde dicen

**Por qué aquí.** Es independiente de las fases anteriores y podría adelantarse si conviene por
reparto de trabajo dentro del equipo.

**Problema.** `docs/evidencias/README.md` establece que las rutas `henri-tfm/`, `odile-tfm/`,
`daniel-tfm/` y `Red Team_/` son **entradas dentro de `evidencias-historicas.zip`**, no directorios
del repositorio entregado. El Anexo C las usa como si fueran ejecutables:

- C.4: `python henri-tfm/01-ataque/payloads/generar_pdf.py` y cuatro comandos más.
- C.6: `python attack_loop.py`, `ver_respuestas.py`, `run_redteam.py` (viven en `Red Team_/`, rama `doc-tfm`).
- C.6: `pytest tests/ -q` con el recuento 59/59, sin ejecución que lo respalde.

**Qué se hace.**
1. Separar C en dos bloques: procedimientos vigentes (contra el `main` entregado) y procedimientos
   históricos (contra el ZIP), sin mezclarlos en la misma lista de comandos.
2. Incorporar a D el material que existe y no está citado: `log-examples/` (ejecución completa con
   sus tres logs de fase y el Run Folder `20260907_193559_qwen2.5-3b`), `docs/evidencias/evidencias-historicas.zip`
   (455 archivos) y `docs/evidencias/manifest.json` (inventario con SHA-256).
3. Resolver el punto que el README del repositorio advierte expresamente: `lab/audit/` está fuera de
   Git, así que la campaña citada en el cuerpo solo viaja en la entrega si se adjunta su Run Folder.
   `log-examples/` parece ser precisamente esa solución; hay que confirmarlo y decirlo en el anexo.
4. Retirar o fechar el 59/59.

**Cerrado cuando.** Cada comando del Anexo C es ejecutable contra lo entregado, o está rotulado
como histórico; y cada ruta del Anexo D existe en la entrega.

**Alimenta:** reportes 2.20, 2.23; 3.11; 4.31, 4.32.

---

### Fase 5 · Anexo E y anexo de aportaciones individuales

**Qué se hace en E.**
- E.1 (sustitución del modelo): la redacción atribuye la estabilización al mayor tamaño del modelo.
  El reporte 3.27 señala que no se repitió la línea base con el modelo final, así que la mejora no es
  atribuible. Hay que registrar versión anterior, versión nueva y condiciones, sin la inferencia causal.
- E.3 (defectos del arnés): dice «configuración por defecto inválida del modelo juez». El reporte 2.13
  señala que la campaña final declara `qwen3.5:9b` como juez y conserva su configuración, de modo que
  llamarlo inválido contradice la procedencia del run. Conservar la incidencia solo si se adjunta el log.
- E.5: ya está bien planteado; revisar que su última frase («lo que sí generaliza es la eficacia de
  las mitigaciones») no reintroduzca el absoluto que el reporte 3.07 pide retirar.

**Qué se hace con las aportaciones.** El apartado 8.6 lleva hoy el título «Aportaciones individuales
(en sugerencia de Norma)» y contiene un único bloque, el de Darwin. Es una nota de redacción visible
en el documento final. Los reportes 3.22 y 4.33 recomiendan convertirlo en una tabla de contribuciones
en el anexo, con una fila por persona.

**Cerrado cuando.** No queda ninguna nota de redacción ni nombre entre corchetes en el documento.

**Alimenta:** reportes 2.13; 3.07, 3.22, 3.27; 4.33.

---

### Fase 6 · Cierre: numeración, pies y coherencia cuerpo ↔ anexo

**Qué se hace.**
1. Renumerar figuras y tablas de forma global. El reporte 3.29 señala una «Figura X» y dos «Figura 6».
2. Reescribir los pies para que delimiten la prueba: campaña, fixture, repetición, postura y enlace
   al Session File (reportes 3.29, 4.35).
3. Sustituir la tabla de contenidos: la actual (párrafos 47 a 63) sigue siendo el guion de trabajo
   del borrador, con estimaciones de páginas, viñetas por persona y «5.6. Daniel — Ataque restante».
4. Corregir la numeración duplicada del capítulo 3: hay dos apartados «3.5» (Criterio de éxito y
   Trazabilidad), y los subapartados de 5.1 están numerados como 5.2.1 a 5.2.7.
5. Verificar que ninguna remisión del cuerpo apunte a un anexo inexistente y que ninguna afirmación
   del cuerpo sea más fuerte que la del anexo que la respalda.

**Cerrado cuando.** El índice refleja el documento, y toda remisión resuelve.

**Alimenta:** reportes 3.22, 3.29, 3.30; 4.33, 4.35.

---

## 4. Resumen del orden

| Fase | Título | Depende de | Naturaleza |
|---|---|---|---|
| 0 | Congelar el marco ATLAS | — | Correctiva, corta, bloqueante |
| 1 | Anexo A: catálogo | 0 | Aditiva, material ya existente |
| 2 | Anexo de matriz ATLAS | 0 | Aditiva, requiere decisión de formato |
| 3 | Anexo B: saneamiento | 0 | Correctiva, la más pesada |
| 4 | Anexos C y D: rutas y evidencia | — | Correctiva, paralelizable |
| 5 | Anexo E y aportaciones | 3 | Correctiva, corta |
| 6 | Cierre editorial | 1-5 | Verificación final |

---

## 5. Decisiones pendientes del equipo

Estas tres no se pueden resolver desde el documento y bloquean sus fases respectivas:

1. **Fase 2.** Formato de la matriz ATLAS: captura del Navigator, matriz recortada propia, o tabla
   de mapeo con diagrama de cadena.
2. **Fase 3.** Estrategia ante las cifras: recalcular desde los artefactos (reportes 01 y 03) o
   conservar y acotar (reporte 04). Son incompatibles entre sí.
3. **Fase 4.** Si `log-examples/` es la vía oficial por la que la campaña de referencia viaja en la
   entrega, dado que `lab/audit/` está fuera de Git.
