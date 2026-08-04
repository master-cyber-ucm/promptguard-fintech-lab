# Fase 3 — Marco normativo

> Ver checklist completo y detallado en `../ROADMAP.md` (sección "Fase 3 — Marco normativo",
> subsecciones 3.1-3.8). Este archivo es para la investigación normativa cruda (citas verificadas,
> notas de lectura), antes de consolidar el aporte a la sección 7 del índice del TFM.

## Mini-checklist (ver detalle y justificación en ROADMAP.md §Fase 3)

- [x] 3.1 GDPR — verificado Art. 5.1.c/32/33/34 + reevaluada obligación de notificación con las
      defensas de Fase 2 puestas (89%→0% de riesgo residual medido, obligación sigue condicional).
- [x] 3.2 DORA — verificado Art. 9/10 + revisado el encaje de los Arts. 6/11/17 a la luz de
      (D)/guardia de salida (Art. 10 cambia de forma sustantiva, 6 y 17 se mantienen fuera).
- [x] 3.3 EU AI Act — verificado Art. 9/15 + estado verde/amarillo/rojo por requisito con evidencia
      real de Fase 2.
- [x] 3.4 EBA guidelines / PSD2 — no aplica, justificado explícitamente (EBA/GL/2019/04 subsumida
      en DORA; PSD2 no aplica por razón de materia ni de sujeto).
- [x] 3.5 NIST AI RMF — ampliado el mapeo GOVERN/MAP/MEASURE/MANAGE con métricas reales de Fase 2.
- [x] 3.6 ISO 27001 — controles del Anexo A realmente aplicables (no lista genérica).
- [x] 3.7 Impacto económico — multas potenciales, orden de magnitud, explícitamente ilustrativo.

## Fuentes oficiales a consultar

- GDPR (Reglamento UE 2016/679) — EUR-Lex.
- DORA (Reglamento UE 2022/2554) — EUR-Lex.
- EU AI Act (Reglamento UE 2024/1689) — EUR-Lex.
- Directrices EBA / PSD2, si aplica.
- NIST AI RMF 1.0.
- ISO/IEC 27001, si aplica.

## Notas de investigación

### 3.1 GDPR (Reglamento UE 2016/679)

**Texto verificado** (fuentes: EUR-Lex CELEX:32016R0679, cruzado con `privacy-regulation.eu` y
`gdpr-text.com` por dificultades de acceso al artículo íntegro directamente en EUR-Lex):

| Artículo | Texto exacto (relevante) |
|---|---|
| **Art. 5.1.c** | Los datos personales serán "adecuados, pertinentes y limitados a lo necesario en relación con los fines para los que son tratados" (minimización de datos). |
| **Art. 32.1** | El responsable y el encargado del tratamiento aplicarán "medidas técnicas y organizativas apropiadas para garantizar un nivel de seguridad adecuado al riesgo", incluyendo cifrado, seudonimización, y garantía de "confidencialidad, integridad, disponibilidad y resiliencia permanentes". |
| **Art. 32.2** | La evaluación del nivel de seguridad adecuado tendrá en cuenta "en particular los riesgos... derivados de la destrucción, pérdida o alteración accidental o ilícita de datos personales transmitidos, conservados o tratados de otra forma, o la comunicación o acceso no autorizados a dichos datos". |
| **Art. 33.1** | El responsable notificará la violación a la autoridad de control "sin dilación indebida y, de ser posible, a más tardar 72 horas después de que haya tenido constancia de ella, a menos que sea improbable que dicha violación... constituya un riesgo para los derechos y las libertades de las personas físicas". Si excede 72h, debe justificar el motivo de la dilación. |
| **Art. 34.1** | Si la violación entraña "un alto riesgo para los derechos y libertades de las personas físicas", el responsable la comunicará **al interesado** "sin dilación indebida". |
| **Art. 34.3** | La comunicación al interesado NO es necesaria si: (a) se aplicaron medidas que hacen los datos ininteligibles a terceros no autorizados (p. ej. cifrado); (b) se adoptaron medidas posteriores que garantizan que el alto riesgo ya no es probable; o (c) supondría un esfuerzo desproporcionado (cabe entonces comunicación pública alternativa). |

El texto de los cuatro artículos coincide con el resumen del borrador PRE-implementación
(`docs/.../05-cumplimiento-normativo.md`) — no había errores de cita, pero sí faltaba el detalle
de las excepciones del Art. 34.3, relevante para la reevaluación siguiente.

**Reevaluación de la obligación de notificación, a la luz de Fase 1 y Fase 2 (lo que el borrador
PRE-implementación no podía saber):**

El borrador respondía "Sí, aplica" de forma incondicional. Con datos reales encima, la respuesta
correcta es más precisa: **la obligación de los Arts. 33/34 es condicional a que se produzca una
violación** ("en caso de violación...", "cuando sea probable que la violación... entrañe..."), no
un requisito permanente independiente de si el ataque tiene éxito. Lo que Fase 1 y Fase 2 cambian
no es si el artículo aplicaría *en caso de fuga* — sigue aplicando exactamente igual, el marco
legal no cambia — sino **la probabilidad medida de que esa fuga llegue a ocurrir**, que es
precisamente el dato que alimenta la evaluación de riesgo del Art. 32 y, por extensión, la
necesidad práctica de invocar el Art. 33/34 en un caso concreto:

- **Sin ninguna defensa** (Fase 1 / combinación `none` del estudio de ablación): 8/9 (89%) de
  éxito real del ataque sobre los tres documentos comprometidos, con fuga textual correcta del
  saldo en 5/8 de esos casos. Un incidente así, de producirse en producción, encajaría sin duda en
  el supuesto del Art. 33 (violación con riesgo) y muy probablemente en el del Art. 34 (alto
  riesgo — IBAN + saldo de un tercero, dato financiero identificable).
- **Con la defensa completa activa** (`ABCD`, Fase 2.3/2.7): 0/9 (0%) de éxito real medido, en 90
  llamadas automatizadas más 33 turnos de verificación manual adicionales, sobre el mismo catálogo
  de payloads. Ninguna violación se produjo en el conjunto de pruebas — no hay hecho que notificar.
- **Matiz importante, no ocultable**: el 0% es una tasa medida sobre el catálogo de técnicas
  conocidas a la fecha, no una garantía matemática de riesgo cero. El propio motor de mutación
  (Fase 2.9.7) encontró una evasión real de la capa (B) —ofuscación de carácter, Unicode invisible
  y homoglifos— antes de corregirla; en ese estado intermedio, (A) seguía bloqueando por una vía
  distinta, pero el caso ilustra que "0% observado" y "riesgo estructuralmente eliminado" no son
  lo mismo. Un registro de brechas real (Art. 33.5, RGPD) exige documentar también los incidentes
  que no llegaron a notificarse por no alcanzar el umbral de riesgo, precisamente para poder
  demostrar ante la autoridad de control que la evaluación de riesgo fue diligente y no una omisión.

**Conclusión, más matizada que el borrador**: la obligación de notificación (Art. 33/34) sigue
existiendo como obligación legal condicional — no desaparece por tener defensas activas, un
sistema con defensas puede igualmente sufrir una brecha real por una técnica no catalogada. Lo que
Fase 2 aporta es evidencia empírica de que el **riesgo residual** de que ese supuesto se
materialice es sustancialmente menor que sin defensa (0% medido frente a 89%), lo cual es
exactamente el tipo de evidencia que debe alimentar la evaluación de riesgo del Art. 32.2 y, en
consecuencia, reducir —pero no eliminar— la probabilidad práctica de tener que ejercer el
procedimiento de los Arts. 33/34 en la operación real del sistema.

### 3.2 DORA (Reglamento UE 2022/2554)

**Texto verificado** (EUR-Lex CELEX:32022R2554):

| Artículo | Texto exacto (relevante) |
|---|---|
| **Art. 9.2** | Las entidades financieras "utilizarán y mantendrán actualizados sistemas, protocolos y herramientas de TIC" adecuados a la magnitud de las operaciones que sustentan su actividad, con el fin de abordar y gestionar los riesgos relacionados con las TIC de conformidad con el principio de proporcionalidad. |
| **Art. 9.4.c** | Se identificarán y aplicarán "mecanismos para detectar oportunamente actividades anómalas... de conformidad con el artículo 10", incluyendo problemas de rendimiento de las redes de TIC e incidentes de TIC. |
| **Art. 10.1** | Las entidades financieras contarán con "mecanismos para la rápida detección de actividades anómalas", incluidos "los problemas de rendimiento de las redes de TIC y los incidentes de TIC", y para "identificar todas las fuentes de riesgo de TIC importantes". |
| **Art. 10.2** | Los mecanismos de detección establecerán "criterios de alerta" para activar los procesos de detección y respuesta a incidentes de TIC, incluidos "mecanismos automáticos de alerta al personal pertinente". |

Confirma lo citado en el borrador PRE-implementación, sin discrepancias de redacción.

**Encaje de (D) y la guardia de salida, no contemplados en el borrador**: el borrador descartaba
los Arts. 6, 11 y 17 por no tener, en ese momento, ningún control concreto que los activara. Con
(D) —Tool Gatekeeper, RBAC determinista fuera del LLM— y la guardia de salida
(`_confidential_leak_guard`) ya implementados, se reevalúa:

- **Art. 6 (marco de gestión del riesgo de TIC)** — el Art. 6.2 exige que el marco incluya
  "estrategias, políticas, procedimientos, protocolos y herramientas de TIC" para proteger los
  activos de información. El Tool Gatekeeper es exactamente una herramienta de este tipo, pero es
  un control técnico puntual (una defensa de un vector concreto), no el marco de gestión del
  riesgo en sí — **sigue sin encajar como obligación propia del Art. 6**, que opera a nivel de
  gobernanza institucional, no de componente individual. Se mantiene fuera de alcance, ahora con
  justificación explícita en vez de una omisión implícita.
- **Art. 10 (detección)** — este es el artículo que sí cambia de forma sustantiva: antes de Fase 2
  no existía ningún mecanismo real de detección para este vector, solo la intención declarada en
  el borrador. Ahora existen dos mecanismos concretos y verificables: (1) el bloqueo determinista
  de (A)/(B) antes de invocar al LLM, registrado en el Session File con la regla exacta que
  coincidió y la latencia por capa; y (2) la denegación de (D) en el punto de ejecución de la
  tool, con el resultado (`status: denied`) también registrado. Ambos son "mecanismos para
  detectar oportunamente actividades anómalas" en el sentido literal del Art. 10.1 — el análisis
  ya no es solo teórico, hay Session Files reales (`lab/audit/sessions/`) que sirven de evidencia
  de que el mecanismo de detección funciona sobre 90+33 casos probados.
- **Art. 17 (gestión de incidentes de TIC)** — exige un "proceso de gestión de incidentes de TIC"
  con clasificación, escalado y comunicación. El proyecto no implementa un proceso de gestión de
  incidentes per se (eso es organizativo, no una pieza de código de este capítulo), pero el
  Session File + el campo `error` detallado que expone cada bloqueo son la materia prima que
  alimentaría ese proceso si existiera. **Se mantiene fuera de alcance directo** del vector, con
  la misma justificación que el borrador, pero ahora explícita: el proyecto aporta los datos de
  entrada de un proceso de gestión de incidentes, no el proceso en sí.

**Vínculo con el registro de auditoría real**: cada Session File (`lab/audit/sessions/`) generado
durante Fase 1/2 registra, por turno, el prompt completo, la respuesta, las tools invocadas con su
resultado real, y (desde Fase 2.7) el bloque `defensas_activas`/`latencia_defensa_ms` — esto es
en la práctica el mecanismo de detección exigido por el Art. 10, no una descripción de intención
como en el borrador PRE-implementación.

### 3.3 EU AI Act (Reglamento UE 2024/1689)

**Texto verificado** (EUR-Lex CELEX:32024R1689):

| Artículo | Texto exacto (relevante) |
|---|---|
| **Art. 9.1-9.2** | Los proveedores de sistemas de IA de alto riesgo establecerán, aplicarán, documentarán y mantendrán "un sistema de gestión de riesgos" a lo largo de todo el ciclo de vida del sistema, consistente en "un proceso iterativo continuo" que incluye identificación, estimación y evaluación de los riesgos conocidos y previsibles, y adopción de "medidas de gestión de riesgos adecuadas y specificamente destinadas" a ellos. |
| **Art. 9.5** | Las medidas de gestión de riesgos "tendrán debidamente en cuenta los efectos y la posible interacción" resultante de la aplicación combinada de los requisitos de la sección (robustez, ciberseguridad, supervisión humana, etc.), del estado de la técnica. |
| **Art. 15.1** | Los sistemas de IA de alto riesgo se diseñarán y desarrollarán "de modo que alcancen un nivel adecuado de precisión, solidez y ciberseguridad", y funcionen de manera uniforme en esos sentidos durante todo su ciclo de vida. |
| **Art. 15.4-15.5** | Los sistemas de alto riesgo "serán resistentes a los intentos de terceros no autorizados de alterar su uso, sus resultados de salida o su funcionamiento aprovechando las vulnerabilidades del sistema". Entre las soluciones técnicas exigidas figuran medidas para prevenir, detectar, combatir, resolver y controlar ataques de "envenenamiento de datos" o "envenenamiento de modelos", y **"la información de entrada diseñada para hacer que el modelo de IA cometa un error" ("ejemplos adversarios" o "evasión de modelos")** — categoría en la que encaja el documento adjunto manipulado de este vector, no una interpretación extensiva sino el supuesto textual del artículo. |

El texto confirma la cita del borrador y aporta un dato que el borrador no tenía: el **Art. 15.5
nombra explícitamente la categoría de "información de entrada diseñada para hacer que el modelo de
IA cometa un error"** (ejemplos adversarios / evasión de modelos) como uno de los ataques que la
obligación de robustez debe prevenir, detectar y controlar — el vector de este capítulo (documento
adjunto con instrucciones ocultas que alteran la salida del modelo) es una instancia directa de esa
categoría, no una interpretación extensiva del artículo.

**Clasificación de alto riesgo**: confirmada contra `docs/propuesta-formal-promptguard-fintech.md`
(Anexo III, categoría 5.b — acceso a servicios financieros esenciales, evaluación de solvencia).
No se encontró contradicción ni matiz adicional al verificar el Anexo III del Reglamento —la
categoría 5.b cubre explícitamente "sistemas de IA destinados a ser utilizados para evaluar la
solvencia... o establecer su solvencia crediticia", que es el caso de uso de microcréditos del
escenario VerdaBank.

**Semáforo por requisito, con evidencia real de Fase 2** (a diferencia del borrador, que no podía
tener datos):

| Capa | Naturaleza | Estado | Justificación |
|---|---|---|---|
| (A) Firmas estructurales | Determinista, basada en reglas | 🟢 Verde | 100% de bloqueo medido (9/9), 0 falsos positivos, comportamiento reproducible y auditable — cumple el estándar de "exactitud, solidez" del Art. 15.1 sin margen de indeterminación. |
| (B) Sanitización de contenido | Determinista, basada en reglas | 🟢 Verde | Mismo argumento que (A). El hallazgo del motor de mutación (evasión por ofuscación de carácter) se corrigió y quedó verificado — evidencia de que el "proceso iterativo continuo" del Art. 9.1 se está aplicando en la práctica, no solo declarado. |
| (C) Separación semántica | Probabilística (depende del LLM) | 🟡 Amarillo | 6-8/9 (67-89%) de éxito real del ataque incluso con (C) activa en solitario — no alcanza el nivel de "solidez" exigible como control único. No es 🔴 Rojo porque el propio diseño del proyecto nunca la trata como barrera de bloqueo, sino como defensa de profundidad dentro de una arquitectura de 4 capas donde (A)/(B)/(D) sí son deterministas — el Art. 9.5 exige tener en cuenta la "interacción" entre medidas, no evaluar cada una de forma aislada como si fuera la única. |
| (D) Tool Gatekeeper | Determinista, RBAC fuera del LLM | 🟢 Verde | 0/9 (0%) de éxito real medido, verificación de propiedad de recurso reproducible al 100% en su dominio. Los dos fallos reales encontrados en verificación manual (falso positivo por transcripción de IBAN, alucinación fuera del alcance de la tool protegida) se corrigieron con evidencia empírica — documentado sin sobrevender el alcance del arreglo (`02-defensa/README.md`, "Alcance — qué queda sin resolver"). |
| Guardia de salida (`_confidential_leak_guard`) | Determinista, basada en patrón | 🟡 Amarillo | Reduce a 0/7 la fuga de IBAN ajeno en la tanda de verificación dirigida, pero su cobertura es específica al patrón IBAN español (`ES\d{22}`) — una alucinación que no cite un número con ese formato exacto no la activa. Limitación reconocida y documentada explícitamente, no oculta. |

**Conclusión del semáforo**: el sistema en conjunto no depende de ningún componente 🟡 en
solitario — (C) y la guardia de salida están respaldadas por controles 🟢 deterministas en la misma
ruta de ejecución (`ABCD` mide 0/9 de éxito real, ver Fase 2.7). Esto es consistente con el
espíritu del Art. 9.5 (evaluar la interacción de medidas, no cada una aislada) y constituye el
tipo de evidencia documentada que el sistema de gestión de riesgos del Art. 9 exige mantener.

### 3.4 EBA Guidelines / PSD2

El borrador PRE-implementación no llegaba a analizar este punto — se investiga aquí por primera
vez, con dos preguntas separadas: (a) ¿sigue teniendo relevancia independiente la guía EBA sobre
riesgo de TIC?, y (b) ¿aplica PSD2 al canal documental concreto de este vector (microcréditos y
reclamaciones)?

**(a) EBA/GL/2019/04 (Guidelines on ICT and security risk management)**: verificado que la propia
EBA **redujo el alcance de esta guía** mediante `EBA/GL/2025/02` (11/02/2025), precisamente porque
DORA —de aplicación directa y armonizada desde el 17/01/2025— vuelve obsoleta en la práctica la
mayor parte de su contenido para entidades sujetas a DORA (como VerdaBank). No fue derogada por
completo —sigue teniendo relevancia residual para proveedores de servicios de pago no sujetos a
DORA—, pero para el análisis de este capítulo **no aporta una obligación independiente de la ya
cubierta en 3.2 (DORA)**: sería citar dos veces la misma exigencia bajo dos nombres distintos. Se
documenta la investigación explícitamente para que quede claro que no es una omisión, sino una
conclusión verificada.

**(b) PSD2 (Directiva UE 2015/2366) — aplicabilidad al canal concreto de este vector**: el Anexo I
de PSD2 enumera taxativamente los "servicios de pago" sujetos a la directiva (depósito/retirada de
efectivo, ejecución de operaciones de pago, emisión de instrumentos de pago, remesas de dinero,
servicios de iniciación de pagos y servicios de información sobre cuentas). Ni la **evaluación de
elegibilidad para un microcrédito** (el caso de uso real del payload PDF de este vector) ni la
**apertura de una reclamación** (el caso de uso del payload DOCX) son servicios de pago en ese
sentido — son, respectivamente, un proceso de concesión de crédito y un proceso de atención al
cliente, ambos fuera del ámbito material de PSD2.

El matiz que sí merece dejarse explícito: el objetivo último del payload —filtrar el saldo de la
cuenta de un tercero vía `consulta_saldo`— toca conceptualmente el "servicio de información sobre
cuentas" (Anexo I.8), pero ese servicio, tal como lo regula PSD2, está pensado para un **tercero
proveedor (AISP)** accediendo a las cuentas de un cliente en **otra** entidad mediante acceso XS2A
con consentimiento explícito y Autenticación Reforzada de Cliente (SCA, Art. 97 PSD2 / RTS
2018/389) — el escenario de Clara es el opuesto: la propia entidad (VerdaBank) sirviendo a su
propio cliente autenticado a través de su propio canal, sin ningún tercero de por medio. PSD2 no
impone un régimen de AISP/XS2A sobre un banco consultando sus propias cuentas para su propio
cliente. La SCA sí podría aplicar de forma genérica a la sesión de acceso al canal (autenticación
del `user_id`), pero eso queda fuera del vector concreto de este capítulo, que no ataca la
autenticación —el atacante no se hace pasar por otro usuario— sino la **autorización** dentro de
una sesión ya autenticada legítimamente: exactamente el problema que resuelve (D), un control de
RBAC, no de autenticación.

**Conclusión**: ni EBA/GL/2019/04 ni PSD2 aportan una obligación aplicable de forma independiente
a este vector concreto. La primera queda subsumida en DORA (3.2); la segunda no aplica por razón
de materia (crédito y atención al cliente, no servicios de pago) ni por razón de sujeto (primera
parte, no un AISP tercero). Documentado como "no aplica, con justificación explícita" — la
instrucción original del `ROADMAP.md` para esta subsección.

### 3.5 NIST AI RMF 1.0

A diferencia de GDPR/DORA/AI Act, el NIST AI RMF no es un marco vinculante ni tiene "artículos" que
verificar contra una fuente legal — es un marco voluntario de funciones y categorías. El mapeo
GOVERN/MAP/MEASURE/MANAGE ya esbozado en `01-mapeo-taxonomico.md` §3 (documento de referencia,
PRE-implementación) describía la **intención** de cada función; esta subsección lo actualiza con
las **métricas reales** que Fase 1 y Fase 2 produjeron, que es exactamente el tipo de evidencia
que MEASURE exige y que antes no existía.

| Función | Descripción PRE-implementación (intención) | Estado real, con evidencia de Fase 1/2 |
|---|---|---|
| **GOVERN** | Política interna que clasifica todo texto extraído de documentos de usuario como no confiable. | Implementada como código, no solo como política declarada: (B) trata el texto extraído como dato no confiable por diseño (nunca se ejecuta, solo se sanitiza y se delimita), y (C) refuerza la misma política a nivel de prompt. La política dejó de ser una declaración de intenciones — es una propiedad verificable del pipeline (`chat.py`, `document_sanitizer.py`). |
| **MAP** | Identificación del canal de subida de documentos como nueva superficie de inyección. | Confirmado empíricamente, no solo identificado en abstracto: Fase 1 mapeó la superficie en 3 formatos concretos (PDF/DOCX/XLSX) con 5 técnicas de ocultación catalogadas por (A), más 2 técnicas adicionales de ofuscación de carácter descubiertas por el motor de mutación (Fase 2.9.7) — el mapa de la superficie de ataque creció con datos reales, no se quedó en la hipótesis inicial. |
| **MEASURE** | Cobertura del Input Sanitizer sobre texto extraído; tasa de detección sobre PDFs adversariales. | Esta es la función que más cambia: de "cobertura a medir" (intención) a **cifras concretas y reproducibles** — 85-100% de éxito del ataque sin defensa (Fase 1.5) → 0% con `ABCD` (Fase 2.3/2.7), sobre 90 llamadas automatizadas + 33 turnos de verificación manual adicionales; 0 falsos positivos en las 6 combinaciones del estudio de ablación; latencia real de la defensa medida por etapa (4.6-10.9ms de media, Fase 2). Todo reproducible con los comandos documentados en `02-defensa/README.md` y `01-ataque/evidencia/`. |
| **MANAGE** | Aplicar el mismo pipeline del Input Sanitizer al texto extraído; separación semántica documento vs. prompt. | Implementado y con una capa adicional no prevista en el borrador: además de (B) y (C), se añadió (A) —firmas estructurales, complementaria— y (D) —Tool Gatekeeper, ortogonal a las tres anteriores—, más dos arreglos concretos tras encontrar fallos reales en verificación manual (falso positivo de (D), alucinación de (D)). MANAGE dejó de ser "aplicar un pipeline" a secas — es un ciclo de gestión de riesgo real: hallazgo → mitigación → verificación, repetido varias veces dentro de esta misma fase. |

**Conclusión**: el mapeo PRE-implementación no estaba equivocado en su estructura, pero describía
intenciones sin poder respaldarlas — es exactamente la brecha que NIST AI RMF identifica como
riesgo (un sistema de gestión de riesgos "de papel"). Con Fase 1/2 completas, las cuatro funciones
tienen evidencia empírica y reproducible detrás, no solo una descripción de lo que se pretendía
hacer.

### 3.6 ISO/IEC 27001

No se citan artículos porque ISO/IEC 27001 es un estándar de pago, no de acceso público — el
análisis se basa en los **nombres y objetivos de control del Anexo A** (edición 2022, ya
referenciados de forma genérica en la propuesta formal del proyecto), evaluando cuáles aplican de
verdad a este vector concreto, no una lista genérica de "buenas prácticas" desconectada del
capítulo.

| Control (Anexo A, ISO/IEC 27001:2022) | ¿Aplica a este vector? | Evidencia concreta |
|---|---|---|
| **A.8.28 — Codificación segura** | Sí, directamente. | Las 4 capas de defensa ((A)/(B)/(C)/(D)) son código de seguridad propio del proyecto, con tests de regresión (63/63 al cierre de Fase 2.9.8) y hallazgo de bugs preexistentes en `injection_signatures.yaml` (comilla sin escapar, regex con falsos positivos) que confirman por qué este control importa en la práctica, no solo en teoría. |
| **A.8.16 — Actividades de monitorización** | Sí, directamente. | El Session File (`lab/audit/sessions/`) registra cada turno con las tools invocadas, su resultado real, y desde Fase 2.7 el desglose `defensas_activas`/`latencia_defensa_ms` por capa — es un mecanismo de monitorización real, no solo declarado, y ya sirvió para diagnosticar los dos fallos reales de (D) en verificación manual. |
| **A.8.23 — Filtrado web** | No aplica directamente. | Este control regula el acceso saliente a sitios web, no el canal de entrada de documentos de este vector — se descarta explícitamente, no por omisión. |
| **A.5.23 — Seguridad de la información para el uso de servicios en la nube** | No aplica a este vector concreto. | El lab corre en contenedores Docker locales (`docker-compose.yml`), no sobre un servicio cloud gestionado por un tercero — el control es relevante para el proyecto en general si se despliega en producción sobre un proveedor cloud, pero no para el vector documental en sí, que es independiente de dónde se aloje el backend. Se documenta el descarte explícitamente, corrigiendo la inclusión genérica que tenía el borrador de la propuesta formal. |
| **A.8.9 — Gestión de la configuración** | Parcialmente. | Los 4 parámetros booleanos del selector de defensas (`defensa_estructural`, `defensa_sanitizer`, etc., Fase 2.7) son configuración de seguridad explícita y versionada en código — relevante como ejemplo de gestión de configuración de un control de seguridad, aunque el control en sentido amplio (gestión de configuración de toda la infraestructura) excede el alcance de este capítulo. |

**Conclusión**: de los controles evaluados, dos aplican de forma directa y con evidencia concreta
(A.8.28, A.8.16), uno de forma parcial (A.8.9), y dos se descartan explícitamente por no
corresponder al vector concreto de este capítulo (A.8.23, A.5.23) — corrigiendo la lista genérica
de candidatos del `ROADMAP.md` con una evaluación real en vez de asumir que todos aplican por
estar en una lista de "buenas prácticas de ciberseguridad".

### 3.7 Impacto económico (ilustrativo)

**Advertencia explícita, no solo formal**: VerdaBank es un banco ficticio (`docs/propuesta-formal-promptguard-fintech.md`)
y este TFM no tiene acceso a datos reales de facturación, volumen de clientes afectados, ni a un
procedimiento sancionador real. Las cifras que siguen son un **orden de magnitud ilustrativo**,
aplicando los rangos oficiales de multa a supuestos de facturación estimados para un neobank de
~900.000 clientes (dato ya establecido en la propuesta formal), no una estimación de riesgo real
ni un dictamen legal.

| Marco | Rango oficial de multa | Aplicado al escenario VerdaBank (ilustrativo) |
|---|---|---|
| **GDPR** (Art. 83.5) | Hasta 20M€ o 4% de la facturación anual global, la cifra mayor. | Sin datos reales de facturación de VerdaBank, se ilustra con un neobank comparable de tamaño medio (facturación anual estimada en el orden de decenas de millones de €) — 4% situaría el techo teórico en varios millones de €, muy por debajo del máximo de 20M€ que actuaría como suelo si la facturación fuera menor. |
| **DORA** | No define un régimen sancionador único armonizado — remite a los regímenes sancionadores nacionales que cada Estado miembro debe establecer (Art. 50 DORA), con supervisión del Banco de España para una entidad española. | No hay una cifra europea única que aplicar; el orden de magnitud dependería de la transposición española, no estimable de forma ilustrativa sin inventar una cifra nacional concreta — se deja explícitamente sin cuantificar en vez de aproximar con un número inventado. |
| **AI Act** (Art. 99) | Hasta 35M€ o 7% de la facturación anual global, la cifra mayor, para las infracciones más graves (prácticas prohibidas); hasta 15M€ o 3% para incumplimiento de obligaciones de sistemas de alto riesgo (el caso de Clara). | Con la misma facturación estimada que en GDPR, el 3% del régimen de alto riesgo produce un orden de magnitud similar o algo superior al de GDPR — consistente con que el AI Act fue diseñado con un régimen sancionador comparable al RGPD. |

**Conclusión**: el ejercicio confirma la intuición cualitativa del borrador PRE-implementación
(exposición económica potencialmente significativa para una entidad del tamaño de VerdaBank), pero
con la salvedad de que **DORA no aporta una cifra europea comparable** —a diferencia de lo que
podría asumirse por analogía con GDPR/AI Act—, y de que todo el ejercicio depende de datos
financieros ficticios: se presenta como ilustración del orden de magnitud regulatorio, no como una
estimación de riesgo financiero real.
