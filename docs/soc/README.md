# LLM-SOC — Observabilidad y control del proxy PromptGuard

> Diseño cerrado en sesión de grilling (2026-08-09) e implementado en la misma.
> Vocabulario en [`CONTEXT.md`](../../CONTEXT.md) §"Observabilidad del proxy (SOC)".
> Persistencia en [`ADR 0007`](../adr/0007-dos-almacenes-para-la-traza-de-un-turno.md).
> Contexto de producto en [`PRODUCT.md`](../../PRODUCT.md).
> Alcance vigente y límites: [documentación de entrega](../alcance-y-limitaciones.md).

## Qué es

Un sistema de auditoría del proxy. Registra qué prompt entró, qué componente lo examinó,
qué decidió y por qué; conecta cada evento con los 71 documentos de ataque y defensa del
proyecto; y deja revisar un incidente con su playbook delante.

**El proxy detecta y detiene. El SOC solo mira.**

## Qué NO es

Estas exclusiones son decisiones, no omisiones:

- **No tiene autoridad.** Nunca bloquea. Si el SOC se cae, el chat sigue: el volcado va
  envuelto en `try/except` que traga y sigue, y hay un test que lo verifica
  (`test_un_fallo_al_volcar_no_propaga_la_excepcion`).
- **No clasifica.** La clasificación es del proxy; el SOC captura la que ya se hizo.
- **No juzga.** Sin matriz de confusión, sin tasas de acierto, sin falsos positivos
  calculados. Esa evaluación sigue en el Analyze Pass offline (`make evaluate` y `make report` → Run
  Report). El SOC enseña actividad; el Run Report emite Verdicts.
- **La única excepción es humana.** Marcar una Alerta como revisada o descartada es un
  juicio, pero lo emite una persona y queda trazado. El sistema no cierra nada solo.

## Arquitectura

```
        ┌─ captura ────────────────────────────────────┐
Turno ──┤ SocCollector (uno por turno)                 │
        │   ├─ StageContext → input_sanitizer, pii_shield
        │   ├─ Deps         → tool_gatekeeper (dentro de agent.run)
        │   ├─ endpoint     → document_sanitizer
        │   └─ orquestador  → output_auditor, leak_guard
        │ flush() ──▶ SQLite  (lab/audit/soc.db)       │
        └───────────────────────────────────────────────┘
                              │
        ┌─ lectura ───────────┴────────────────────────┐
        │ /api/v1/soc/*  +  índice de docs/ en memoria │
        └───────────────────────────────────────────────┘
                              │
                    soc.html (7 destinos, hash routing)
```

## Modelo de datos

Tres tablas en `lab/audit/soc.db` (SQLite de la stdlib — sin dependencias nuevas).

**`soc_turn`** — uno por turno: `ts`, `session_id`, `user_id`, `endpoint`, `origen`,
`run_id`, `postura`, `vulnerable`, `prompt`, `respuesta`, `modelo`, `latencia_total_ms`,
`fixture_id`, `fixture_kind`, `fixture_expected_result`, `categoria`, `subcategoria`,
`bloqueado`, `audit_file`.

**`soc_event`** — N por turno, el Analysis Event: `componente`, `objetivo`, `accion`,
`confianza`, `razon`, `regla`, `attack_type`, `detalle`, `latencia_ms`, `orden`.

**`soc_alert`** — una por evento `BLOCK`/`SUSPICIOUS`: `severidad`, `severidad_origen`,
`estado`, `nota`.

`fixture_expected_result` se guarda como **contexto que se muestra**, nunca como base de
un cálculo de acierto.

### La regla fundacional

**El evento se emite siempre, también cuando la acción es `ALLOW`.** Un componente que
deja pasar es información: sin ese evento no se distingue "lo miró y lo permitió" de "no
lo miró nadie".

El código hacía lo contrario. En `chat.py` el bucle de stages era:

```python
decision = stage.evaluate(stage_ctx)
if decision.action != "BLOCK":
    continue          # ← la decisión se tiraba a la basura
```

Corregirlo fue parte del trabajo, no un efecto colateral.

### Simetría del Tool Gatekeeper

Con `enforce_gatekeeper=False` el Gatekeeper **no emite nada**, y es deliberado: en esa
configuración no está verificando propiedad, así que registrar un `ALLOW` haría parecer
defendido un endpoint que no lo está. Su ranura sale vacía — el vacío es el dato.

## Cobertura desigual, y por qué se ve

| Endpoint | Componentes que evalúan |
|---|---|
| `simple-prompt` · `complex-prompt` · `complex-with-context` | **solo** `output_auditor` |
| `proxy` | los 6 |
| `complex-with-document` | doc_sanitizer + estructural + gatekeeper + auditor + leak_guard |
| cualquiera con `vulnerable=true` | **ninguno** |

Verificado contra tráfico real:

```
#5 proxy                vuln=True  eventos=0  []
#3 simple-prompt        vuln=False eventos=1  [output_auditor ALLOW]
#1 proxy                vuln=False eventos=6  [input_sanitizer ALLOW, pii_shield ALLOW,
                                               tool_gatekeeper BLOCK, output_auditor ALLOW,
                                               leak_guard ALLOW, pii_shield ALLOW]
```

Cada turno guarda su `postura`, así que el vacío se explica solo: *"modo vulnerable — 0
componentes activos"*, nunca un fallo de captura ambiguo.

El Input Sanitizer registra todas sus decisiones, incluidas `ALLOW`. Aplica firmas
de inyección tras normalizar Unicode, decodificar Base64 y considerar una ventana
acotada de la sesión. Es una capa de reducción de riesgo basada en patrones, no una
garantía frente a cualquier paráfrasis o técnica nueva.

## Base de conocimiento

**El puente es estructural.** Fixtures y documentación comparten árbol de taxonomía:

```
lab/backend/tests/fixtures/LLM07-system-prompt-leakage/filtrado-por-repeticion/…
docs/ataques/              LLM07-system-prompt-leakage/filtrado-por-repeticion/07-playbook…
docs/defensas/             LLM07-system-prompt-leakage/filtrado-por-repeticion.md
```

Un turno de `atk_042` encuentra sus documentos por construcción. Para tráfico libre sin
fixture, el puente es el `attack_type` del componente que bloqueó.

Índice en memoria al arrancar: **71 documentos**. Nada se copia a la base; la fuente sigue
siendo el repositorio. Requiere el montaje `../docs:/app/docs:ro` en `docker-compose.yml`.

**Hueco declarado:** `_extensiones` (jailbreak, chained, ingeniería social, ofuscación) son
**21 fixtures sin ninguna documentación**. El SOC lo muestra explícitamente. Es un hallazgo
sobre el proyecto, no un fallo del panel.

**Renderizado Markdown propio** (`js/soc/md.js`, ~120 líneas) en lugar de vendorizar
`marked`: los documentos usan un subconjunto acotado y regular, y escribirlo da control
total del escapado. Los bloques Mermaid se muestran como fuente etiquetada — renderizarlos
exigiría ~2 MB de librería. Limitación declarada, no sorpresa.

## Interfaz

Una sola página, `soc.html`, con enrutado por hash. **No es capricho:** si cada destino
fuera un documento, navegar reiniciaría el polling y se perdería el hilo del vivo justo al
explicar algo.

| Destino | Contenido |
|---|---|
| **Postura** | Mapa de cobertura · actividad por componente · últimas corridas |
| **Eventos** | Stream en vivo, cadena de seis componentes, filtros, pausa, traza desplegable |
| **Alertas** | Triaje ligero: revisar, descartar, reabrir |
| **Sesión** | Conversación + traza por turno + escalada + panel de relacionados |
| **Conocimiento** | Los 71 documentos navegables por taxonomía |
| **Playbooks** | Los 7 procedimientos, abiertos desde el evento que los motiva |
| **Corridas** | Comparación de dos corridas componente a componente |

**La cadena de seis posiciones** es el motivo distintivo: una ranura por componente,
siempre el mismo orden. Relleno = evaluó, hueco punteado = no evaluó. Sin desplegar nada
se ve cobertura y desenlace a la vez, y un turno vulnerable son seis huecos en fila.

Refresco por **polling incremental** cada 2 s contra `/turns?since=<cursor>`. El stream
**nunca se repinta entero**: solo se añaden filas arriba. Repintar cada 2 s haría parpadear
la pantalla y movería el foco del teclado. Techo de 250 filas en el DOM.

**Pausa con la barra espaciadora**, porque en una defensa nadie puede explicar una traza
mientras la lista se mueve sola.

### Accesibilidad

- Tema claro por física: un proyector en sala con luz lava los negros.
- **Ninguna señal viaja sola en color**: cada acción lleva color + forma (círculo / rombo /
  cuadrado) + etiqueta literal.
- El eje ALLOW/BLOCK evita el par rojo-verde — `ALLOW` es teal.
- Contraste AA verificado en la escala de tinta; `prefers-reduced-motion` respetado.

## PII y retención

Prompt y respuesta se guardan **en claro**: los datos del lab son sintéticos y la fidelidad
forense importa (investigar un PII harvesting con el payload censurado es imposible).

Pero el marco que propone el TFM va dirigido a empresas reales, y ahí esta tabla **es** un
tratamiento de datos personales. La memoria (§10) debe recoger los controles que un
despliegue real necesitaría: minimización, retención, control de acceso y registro de
consultas. Se documentan, no se construyen — disciplina de alcance.

Sin purga automática; borrado por corrida. `soc.db` queda fuera de git.

## Trabajo declarado fuera de alcance

- **Tokenización de PII antes de persistir** (doble campo con revelar auditado).
- **Cruce con ground truth**: `fixture_expected_result` está guardado, así que la matriz de
  confusión es una consulta de distancia. No se hace: mezclaría observación con evaluación.
- **Cruce con el Verdict del Analyze Pass**, que dejaría ver los casos donde el proxy dejó
  pasar el prompt pero el ataque fracasó por alignment del modelo.
- **Firmas Sigma e IoCs conversacionales** (trabajo futuro): el SOC aporta el sustrato.
- **Asignación de alertas a personas y fases cronometradas** del playbook.
