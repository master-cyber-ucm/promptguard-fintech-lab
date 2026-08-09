# Product

## Register

product

## Users

Dos audiencias con la misma pantalla, y la segunda manda cuando hay conflicto.

**Los autores del TFM**, a diario, en su portátil: lanzan ataques desde el Playground o corridas de la suite y necesitan ver qué hizo el proxy con cada prompt. Sesiones largas, muchas trazas, filtrado rápido.

**El tribunal**, una vez, en un aula con luz de día y un proyector: nunca han visto esta herramienta, la miran diez minutos a cuatro metros de distancia, y tienen que entender sin ayuda qué está pasando. No pueden hacer zoom, no pueden preguntar dos veces, y no van a leer una leyenda.

La consecuencia de diseño es concreta: la base es legible a distancia, y la densidad se gana **plegando y filtrando**, nunca reduciendo el tamaño de letra.

## Product Purpose

Hacer visible lo que el proxy PromptGuard hizo con cada prompt: qué entró, qué componente lo examinó, qué decidió y por qué.

El SOC no tiene autoridad. El proxy detecta y detiene; el SOC mira. No clasifica, no bloquea, y no evalúa si el proxy acertó — esa evaluación vive en el Analyze Pass offline. Éxito es que alguien que abre la pantalla por primera vez, mientras otro ataca en directo, entienda en treinta segundos qué está ocurriendo y dónde falla la cobertura.

Diseño funcional completo en [`docs/soc/README.md`](docs/soc/README.md).

## Brand Personality

**Vigilante, operativo, en tensión.** Sala de control, no cuaderno de notas.

Con una precisión que gobierna todo lo demás: **la tensión viene de que está vivo, no de que grita.** Lo que comunica vigilancia es el stream creciendo solo, el estado cambiando, el pulso de que algo se observa *ahora mismo*. No un rojo pulsante que dictamina que algo está mal. Un `BLOCK` es un dato, no una sirena.

Esto no es una concesión estética: es lo que mantiene la coherencia con la decisión de producto de que el SOC observa sin juzgar. Un panel que alarma estaría emitiendo un juicio que el SOC no tiene autoridad para emitir.

El SOC es un **sistema propio, deliberadamente distinto** del banco (`bank.css`) y del Playground (`app.css`). En el escenario, VerdaBank y el SOC pertenecen a organizaciones distintas: el banco es el cliente, el SOC es la herramienta de seguridad que lo vigila. Que se parezcan confundiría la distinción que el TFM quiere subrayar. Reutiliza escala de espaciado y radios; no reutiliza paleta ni voz.

## Anti-references

- **SOC de película.** Verde fosforito sobre negro, monoespaciada en todo, mapas de ataque animados, contadores de amenazas subiendo. Es el reflejo automático del género: si alguien puede adivinar el aspecto solo con oír "dashboard SOC", no se diseñó, se recitó.
- **Plantilla de dashboard SaaS.** Cuatro tarjetas con un número grande y una flechita de porcentaje, gráfico de área con degradado, tabla genérica debajo.
- **Consola de logs cruda.** Volcado monoespaciado sin jerarquía, tipo `tail -f`. Traslada todo el trabajo de interpretación al lector — inaceptable ante un tribunal que mira diez minutos.
- **Muro de widgets indiferenciados.** Todo del mismo tamaño y sin jerarquía. Parece potente y no dice nada, porque el ojo no sabe dónde ir.

## Design Principles

1. **Observar no es juzgar.** La pantalla muestra lo que pasó y por qué; nunca dictamina si el proxy acertó. Sin matrices de acierto, sin tasas, sin porcentajes de éxito. Contar actividad sí; evaluarla no.
2. **La tensión viene de que está vivo, no de que grita.** El pulso lo da el movimiento del stream y el cambio de estado. El color de alarma se reserva, no se reparte.
3. **El vacío es información.** Un turno que ningún componente examinó es un hallazgo, no un error de captura, y tiene que leerse como tal. La ausencia de defensa es el dato más elocuente que enseña este panel.
4. **Legible a cuatro metros; denso bajo demanda.** La densidad se gana con filtros y con plegar/desplegar. Reducir el cuerpo de letra para que quepa más nunca es la respuesta.
5. **Ninguna señal viaja sola en color.** Toda acción (`ALLOW` / `SUSPICIOUS` / `BLOCK`) se codifica con al menos dos canales: color más forma, peso, posición o etiqueta literal.

## Accessibility & Inclusion

**WCAG 2.1 AA, verificado, no asumido.** Texto de cuerpo ≥4.5:1; texto grande ≥3:1. El contraste se comprueba, no se estima a ojo.

**Nunca solo color.** El panel codifica `ALLOW` / `SUSPICIOUS` / `BLOCK` constantemente. Si esa distinción viajara únicamente en rojo-ámbar-verde, alrededor del 8% de los hombres no la percibiría — y un tribunal de tres personas es una muestra donde eso es una apuesta real, no un caso teórico. Doble codificación siempre.

**`prefers-reduced-motion` respetado.** El stream se actualiza en vivo; toda entrada animada necesita su alternativa sin movimiento.

Es además material citable para la memoria: la accesibilidad como requisito del marco propuesto, no como adorno del prototipo.
