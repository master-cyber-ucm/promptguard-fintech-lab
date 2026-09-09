# Recorrido visual

Con el laboratorio arrancado, este recorrido permite inspeccionar el banco, el
Playground y el SOC. Las capturas adjuntas documentan sesiones anteriores y sirven
como orientación; los resultados de una nueva ejecución pueden variar.

## 1. VerdaBank

Abrir `http://localhost:3000`. Seleccionar a María García (`usr_001`) y entrar.
El login es simulado: la contraseña no se verifica. Revisar las cuentas y los
movimientos sintéticos; abrir el chat y solicitar el saldo propio.

![Acceso al banco](docs/reports/demo-by-front/01-login.png)

Comprobar que la respuesta es útil y coherente con los datos de ese usuario. La
aplicación bancaria utiliza el proxy; un texto amistoso no acredita por sí mismo
que se haya realizado una operación.

## 2. Playground

Abrir `http://localhost:3000/playground.html`. Mantener el mismo usuario para
comparar escenarios. Cargar una fixture desde el catálogo y revisar sus pasos antes
de enviarlos. Para comenzar, utilizar `leg_001` (control legítimo) y `atk_010`
(*confused deputy*).

![Playground](docs/img/playground.jpg)

Seleccionar el modo y registrar la configuración elegida. Al comparar con `proxy`,
inspeccionar qué controles actuaron; no suponer que el modo vulnerable y la postura
baseline representan el mismo experimento. La suite automatizada registra las
posturas con mayor precisión y permite comparaciones reproducibles.

Para el canal documental, cargar una nómina de [lab/payloads](lab/payloads/README.md)
y comparar su versión sana con la comprometida. La interfaz puede conservar la
etiqueta de modo documental; el contrato vigente incorpora el archivo a los
endpoints existentes. La [guía por comandos](DEMO_BY_COMMANDS.md#3-comparar-documentos)
explica cómo ejecutar una comparación documental con posturas registradas.

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
origen (`Suite` o `Agente de red-team`). Usar los filtros para llegar a los Turns
del caso de interés.

![Detalle de una corrida histórica](docs/reports/demo-by-front/08-soc-suite-attack-detail.png)

Comparar un ataque con su control legítimo: comprobar seguridad y también utilidad.
Para una campaña autónoma, contrastar los hallazgos del agente con las llamadas a
herramientas y sus efectos. El juicio del atacante no sustituye la evidencia.

Los porcentajes y comparaciones causales se interpretan en el Run Report, siguiendo
[DEMO_FULL_SUITE.md](DEMO_FULL_SUITE.md). Las evidencias de la entrega se localizan en
[el anexo experimental](docs/evidencias/README.md).
