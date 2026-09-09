# Defensa — Extracción de Modelo

> Diseño de control: puede incluir propuestas y estados históricos. El [alcance de la entrega](../../alcance-y-limitaciones.md) delimita lo implementado; la eficacia se comprueba con las evidencias de cada ejecución.

> Contra el ataque **#10** del catálogo · [ficha del ataque](../../ataques/LLM10-unbounded-consumption/extraccion-de-modelo)
> **OWASP LLM10:2025** · **MITRE ATLAS AML.T0024**
> **Módulo principal:** Query Pattern Monitor · **Apoyo:** Rate Limiter y Budget Guard (comparten superficie con `denial-of-wallet.md`)

## 1. Qué hay que impedir

Que un volumen de queries —deliberadamente bajo y sostenido para no disparar el Rate
Limiter de `denegacion-de-servicio.md`— permita a un atacante muestrear el
comportamiento del modelo hasta reconstruirlo o extraer datos que memorizó. El Rate
Limiter cuenta *cuántas* peticiones; este control mira *qué forma* tienen.

| Invariante | Cómo se garantiza |
|-----------|-------------------|
| **I1** — Un patrón de queries sistemático y de baja velocidad es observable | Query Pattern Monitor — señal distinta de "muchas peticiones", es "peticiones que cubren el espacio de entrada de forma no orgánica" |
| **I2** — La superficie de valor (modelo propietario) está identificada | Solo aplica si `LLM_PROVIDER` es un modelo de pago/propietario — ver nota de aplicabilidad en la ficha del ataque |

## 2. Principio de diseño

> El volumen bajo, sostenido, es indistinguible de un usuario legítimo mirando una
> petición a la vez — la defensa no puede ser "más rate limiting", tiene que ser
> "detectar la FORMA del muestreo".

A diferencia del resto del catálogo, este control no tiene un invariante binario
verificable con una comparación determinista (`amount <= limite`) — es detección de
anomalías sobre un patrón, con la incertidumbre que eso implica. Se declara así, no se
disfraza de control determinista.

## 3. Diseño del control (nivel de idea, no de implementación)

- **Cobertura del espacio de entrada por usuario/día** — un usuario legítimo hace
  preguntas sobre SU cuenta; un extractor de modelo hace preguntas sistemáticamente
  variadas sobre temas no relacionados entre sí. Señal: diversidad temática alta +
  volumen sostenido + ausencia de referencias a datos propios del usuario.
- **No exponer logprobs/logits crudos** — si el proveedor los expone (algunos APIs
  OpenAI-compatible lo permiten), no reenviarlos al cliente: son la señal más barata
  para un atacante de *model inversion*.
- **Ruido/watermarking en la salida** — perturbación controlada de la respuesta que no
  afecta la utilidad para un usuario legítimo pero degrada la fidelidad de un modelo
  clon entrenado sobre esas salidas. Técnica de investigación activa, no un control
  maduro — se declara como línea a evaluar, no como control listo.
- **Presupuesto de queries "novedosas"** — extensión del Budget Guard de
  `denial-of-wallet.md`: no solo tokens, también número de preguntas semánticamente
  distintas por usuario/día (más caro de calcular — requiere embeddings o clustering
  de las peticiones ya vistas).

## 4. Qué NO cubre

- **No aplica con el modelo por defecto del lab** (`qwen2.5:3b` vía Ollama local es
  público — no hay IP que robar). El control solo tiene sentido si el despliegue usa un
  proveedor de pago con un modelo propietario — declarado también en la ficha del
  ataque, no se repite el control donde no protege nada.
- **No detiene un atacante paciente con presupuesto de tiempo alto** — cobertura del
  espacio de entrada a un ritmo suficientemente bajo puede quedar bajo cualquier umbral
  de detección razonable. Mitigación parcial, no solución.

## 5. Estado

- [x] Invariantes definidos, con la incertidumbre del control declarada explícitamente
- [x] Aplicabilidad al lab evaluada — bajo valor con la configuración por defecto
- [ ] Implementación — nada de esto existe en `lab/backend/src/`
- [ ] Decisión: ¿vale la pena implementar esto si el lab por defecto no lo necesita, o
  se documenta como diseño de referencia sin construir? Pendiente de decidir.
