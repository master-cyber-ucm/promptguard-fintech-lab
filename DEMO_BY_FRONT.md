# Recorrido visual

Arrancar el laboratorio siguiendo [estos pasos](DEMO_BY_COMMANDS.md#1-arrancar)
y completar `make smoke`. Las URL siguientes presuponen el puerto 3000.
Este recorrido permite inspeccionar el banco, el
Playground y el SOC. Las capturas adjuntas documentan sesiones anteriores y sirven
como orientación; los resultados de una nueva ejecución pueden variar.

## 1. VerdaBank

Abrir `http://localhost:3000`. Seleccionar a María García (`usr_001`) y entrar.
El login es simulado: la contraseña no se verifica. Revisar las cuentas y los
movimientos sintéticos. Pulsar **Hablar con Clara** y enviar:

> Hola Clara, ¿puedes decirme el saldo actual de mi cuenta ES9121000418450200051332?


Comprobar que la respuesta es útil y coherente con los datos de ese usuario. La
aplicación bancaria utiliza el proxy; un texto amistoso no acredita por sí mismo
que se haya realizado una operación.

## 2. Playground

Abrir `http://localhost:3000/playground.html`. El Playground tiene su propio
selector de usuario: elegir **María García (usr_001)**, aunque ya se haya entrado
en el banco con ella.

1. En **Modo**, elegir `proxy (defensa Tool Gatekeeper)`. Esa etiqueta abre el
   pipeline de proxy, con más controles que el Gatekeeper.
2. En **Fixture Browser**, dentro de **LLM06 · Excessive Agency**, pulsar
   **consulta_saldo_propio** (`leg_001_consulta_saldo_propio`). El catálogo muestra
   nombres, no IDs. Revisar el texto cargado y pulsar **Enviar**.
3. Esperar la respuesta y comprobar la utilidad y las herramientas en el SOC.
4. Pulsar **admin_impersonation** (`atk_010`), revisar el texto y pulsar **Enviar**.
   Seleccionar una fixture abre una sesión nueva, aunque las burbujas anteriores
   permanezcan en pantalla.
5. Para explorar el modo vulnerable, elegir `complex-with-context` y volver a
   seleccionar cada fixture antes de enviarla. Cambiar solo el modo no reinicia
   la sesión. En una fixture de varios pasos, enviar cada paso cargado después
   de recibir la respuesta anterior.

![Playground](docs/img/playground.jpg)

Los modos `simple-prompt`, `complex-prompt` y `complex-with-context` del Playground
solicitan explícitamente `vulnerable=true`. Esto no equivale al perfil `baseline`
de la suite: registrar modo y usuario, y utilizar la
[comparación por comandos](DEMO_BY_COMMANDS.md#2-comparar-texto) para aislar posturas
del mismo proxy.

Para el canal documental:

1. Seleccionar `complex-with-document (adjuntar archivo)`.
2. En **LLM01 · Prompt Injection**, cargar **document_upload_pdf_sano** (`leg_030`).
3. En el selector de archivo, adjuntar `lab/payloads/nomina_sana.pdf`. Cargar una
   fixture **no adjunta automáticamente** su documento.
4. Mantener A, B, C y D activadas y la variante `tool_framing` desactivada. Pulsar
   **Enviar** y esperar la respuesta.
5. Cargar **indirect_doc_pdf_upload_real** (`atk_035`), adjuntar
   `lab/payloads/nomina_comprometida.pdf` y enviar con las mismas defensas. Hay que
   volver a adjuntar el archivo en cada envío: el selector se vacía tras responder.

El Playground todavía llama al adaptador `/chat/complex-with-document`, conservado
por compatibilidad. Sus casillas documentales no representan exactamente los perfiles
`document-baseline` y `document-full` de la suite. Para comparar esas posturas sobre
el contrato vigente `/chat/proxy`, seguir la
[guía por comandos](DEMO_BY_COMMANDS.md#3-comparar-documentos).
Los archivos disponibles se describen en [lab/payloads](lab/payloads/README.md).

## 3. SOC

Abrir `http://localhost:3000/soc.html`. Consultar **Eventos**, localizar el Turn
recién enviado, desplegarlo y abrir **Ver sesión completa**.

![Eventos del SOC](docs/img/soc-eventos.jpg)

Revisar el prompt, la respuesta, las herramientas y los eventos de cada componente:
qué examinó, qué decidió y qué regla aplicó. `ALLOW`, `SUSPICIOUS` y `BLOCK` son
decisiones de etapas, no el veredicto global del experimento. Una etapa ausente
puede indicar que no era aplicable o que una etapa anterior detuvo el flujo.

La base de **Conocimiento** y los **Playbooks** enlazan la taxonomía y las defensas
con el evento. Esa documentación explica el control; no demuestra que actuara en
un Turn concreto.

## 4. Corridas y campañas

Ejecutar las muestras de [DEMO_BY_COMMANDS.md](DEMO_BY_COMMANDS.md). En el SOC,
abrir **Corridas**, localizar el nombre que imprimió el runner y consultar su
columna **Origen**. Pulsar el nombre de la corrida para abrir **Eventos** con el
filtro de corrida ya aplicado. Desplegar el Turn del caso de interés.


Comparar un ataque con su control legítimo: comprobar seguridad y también utilidad.
Para una campaña autónoma, contrastar los hallazgos del agente con las llamadas a
herramientas y sus efectos. El juicio del atacante no sustituye la evidencia.

Los porcentajes y comparaciones causales se interpretan en el Run Report, siguiendo
[DEMO_FULL_SUITE.md](DEMO_FULL_SUITE.md). Las evidencias de la entrega se localizan en
[el anexo experimental](docs/evidencias/README.md).
