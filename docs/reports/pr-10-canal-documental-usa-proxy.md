# PR 10 — El canal documental deja de apuntar a un endpoint deprecado

**Estado:** implementado
**Prioridad:** P0 — 11 fixtures cargados y con cero cobertura en el run auditado
**Origen:** análisis de `20260901_190305_qwen2.5-3b` (problema original #3 del backlog)
**Dependencias:** ninguna (PR8 ya cubre estos fixtures con `hybrid_attack`, confirmado en la validación)

## Pregunta de diseño (persistida antes de investigar)

> `suite-final.4.log` avisa de 11 fixtures (`atk_035`, `atk_036`, `atk_037`,
> `atk_069`, `atk_072`, `atk_076`, `leg_030`–`leg_034`) sin ningún target
> aplicable. ¿Hace falta construir el canal documental desde cero, o ya existe algo
> que solo falta conectar?

**Por qué importa:** son 11 de 111 fixtures del catálogo (10%) — seis ataques de
inyección indirecta vía documento y cinco controles legítimos — que nunca generaron
una petición, una sesión ni un error en ningún run histórico. Cualquier claim sobre
"inyección indirecta" en el TFM ignora por completo el vector más realista de esa
familia (un PDF de nómina con texto oculto), no solo el simulado por copy-paste.

**Dueño de la decisión:** ninguno externo — investigable en el propio código.

**Criterio de aceptación:**
1. Los 11 fixtures deben tener al menos un target aplicable, verificable con
   `capabilities.audit_coverage`.
2. Un fixture documental de ataque debe ser comparable entre una postura sin
   defensa documental y una con ella (no contra un chat de texto plano).
3. La ejecución debe ser real: subir el documento real, no simular su contenido
   como texto de chat.
4. Cero fixtures/payloads nuevos que inventar — si faltan documentos reales, es un
   bloqueador a declarar, no a rellenar con contenido inventado apresuradamente.

## Evidencia del caso

### 1. La infraestructura de aplicabilidad ya estaba construida, y ya pasaba sus propios tests

`backend/src/models/capabilities.py` (243 líneas) ya declaraba `Modality.DOCUMENT`,
`Capability.DOCUMENT_UPLOAD`, targets `proxy-document-baseline`/`proxy-document-full`
con esa capacidad, y `test_aplicabilidad_por_capacidades.py` —con su propio docstring
citando *exactamente* este problema— ya tenía 14 tests que pasaban, incluido
`test_la_matriz_actual_ejecuta_todos_los_fixtures_cargados` (`orphans == []` con
`MATRIZ_COMPLETA`). Nadie necesitaba diseñar la solución: alguien ya la había escrito
y probado, solo faltaba conectarla al runner real.

### 2. Los 11 payloads reales ya existen en disco

```
$ ls software/henri-tfm/01-ataque/payloads/
export_clientes_terceros.xlsx  gastos_comprometido.xlsx  nomina_comprometida.pdf ...
$ grep -rh '^document:' backend/tests/fixtures/*/*/attack-prompts/*.yaml \
                        backend/tests/fixtures/*/*/legitimate-prompts/*.yaml
# los 11 nombres, todos con archivo correspondiente en payloads/
```

No hay bloqueador de contenido: los 11 documentos (PDF/DOCX/XLSX reales, con y sin
texto oculto) ya estaban generados por los scripts `generar_pdf.py`/`generar_docx.py`
del propio directorio `henri-tfm/01-ataque/payloads/`.

### 3. El único componente roto: el runner apunta a una ruta deprecada con un contrato obsoleto

`scripts/run_attack_suite.py` enviaba los fixtures documentales a
`POST /api/v1/chat/complex-with-document` con flags `defensa_sanitizer`,
`defensa_estructural`, `defensa_separacion_semantica`, `defensa_tool_gatekeeper`,
`defensa_pii_shield` como campos de formulario. Pero PR7 (`9acd750`, commit HEAD
antes de esta sesión) ya había movido el documento a un campo `multipart/form-data`
opcional de los 4 endpoints existentes:

```python
# backend/src/api/routes/chat.py:1572
@router.post("/chat/complex-with-document", response_model=ChatResponse)
async def chat_complex_with_document(...):
    logger.warning("[%s] /chat/complex-with-document está DEPRECADO — usar POST /chat/proxy ...")
```

Y en `chat_proxy` (la ruta viva):

```python
profile = request.proxy_profile or "full"
...
if request.proxy_profile:
    request.vulnerable = settings["vulnerable"]
...
documento_activo = not request.vulnerable
```

Un único campo `proxy_profile` (`"baseline"`/`"full"`) gatea a la vez las cinco
defensas de texto Y el Document Sanitizer/detector estructural — el servidor ya no
lee ningún `defensa_*` en esta ruta. `capabilities.py` ya asume esto en su nombrado
de targets (`proxy-document-baseline`, `proxy-document-full`), pero
`run_attack_suite.py` nunca se actualizó tras PR7: seguía hablándole a la ruta vieja
con el contrato viejo. Como `capabilities_of_target("complex-with-document")` sí
tiene `DOCUMENT_UPLOAD` declarado (se conserva por compatibilidad retroactiva con
runs históricos), el fixture no era "no aplicable" — el problema era que el propio
`CHAT_ENDPOINTS`/`--endpoint` de `run_attack_suite.py` nunca ofrecía ese target
combinado con `--document-profile` de forma que la matriz por defecto lo alcanzara,
y el `Makefile` tenía la línea que lo activaría **comentada**:

```make
# 	$(foreach profile,$(DOCUMENT_PROFILES),--document-profile $(profile)) $(ARGS)
```

## Alternativas consideradas

| Opción | Descripción | Veredicto |
|---|---|---|
| A. Reactivar `/chat/complex-with-document` sin tocar el runner | Revertir la ruta a "no deprecada". | Rechazada: PR7 ya la superó con una razón documentada (ADR-0018); resucitar una ruta duplicada reintroduce el problema que PR7 resolvió. |
| B. Actualizar `run_attack_suite.py` para hablar el contrato PR7 (`/chat/proxy` + `proxy_profile`), reutilizando los targets `proxy-document-*` ya declarados en `capabilities.py` | Cierra el hueco con la infraestructura ya construida y probada; cero endpoints nuevos, cero fixtures nuevos. | **Elegida.** |
| C. Enviar fixtures documentales como texto plano a los 3 endpoints pedagógicos | Simplifica el runner. | Rechazada: mide un canal que no existe (esos endpoints no aceptan multipart) y el propio `capabilities.py`/tests exige comparabilidad dentro del mismo pipeline documental, no contra texto plano. |

## Solución implementada

1. **`scripts/run_attack_suite.py`**:
   - Elimina `DOCUMENT_ENDPOINT_NAME`/la entrada `complex-with-document` de
     `CHAT_ENDPOINTS` (deprecada; ya no es una opción de `--endpoint`).
   - `DOCUMENT_PROFILE_SETTINGS` (flags `defensa_*` obsoletos) → `DOCUMENT_PROXY_PROFILE`,
     un mapeo de 2 entradas `{"document-baseline": "baseline", "document-full": "full"}`.
   - `_run_document_execution` envía `proxy_profile` (no los flags viejos) a
     `/api/v1/chat/proxy`, igual que cualquier otra ejecución del proxy.
   - `--document-profile` ahora expande sobre el mismo target de origen `"proxy"`
     que `--proxy-profile` (antes exigía `--endpoint complex-with-document`, que ya
     no existe); ambos flags pueden coexistir en la misma invocación.
   - `proxy_profile_by_target[target]` para un target documental pasa a llevar el
     perfil real (`"baseline"`/`"full"`), no `None` — antes `requested_posture`
     interpretaba `None` como "full" incondicionalmente para cualquier target que
     empezara por `proxy`, lo que habría hecho pasar `proxy-document-baseline` como
     si hubiera pedido el perfil completo.
2. **`scripts/report.py`**: añade los dos targets documentales a
   `SECURITY_ENDPOINT_ORDER` (cosmético: antes caían al final alfabético).
3. **`Makefile`**: `suite:` añade `$(foreach profile,$(DOCUMENT_PROFILES),--document-profile $(profile))`
   — antes estaba escrito y comentado. `make suite` (matriz por defecto) pasa a
   cubrir los 111 fixtures, no 100.
4. **Test nuevo**: `backend/tests/test_canal_documental_usa_proxy.py` (6 tests) fija
   el contrato: el endpoint deprecado ya no es una opción de la CLI, el mapeo de
   perfiles es el correcto, `requested_posture` coincide entre el target documental
   y su equivalente de texto, y la aplicabilidad por capacidades enruta cada fixture
   al canal correcto.

## Hallazgo colateral, fuera de alcance de este PR

Al ejecutar de verdad `proxy-document-full` contra `atk_035` (ver validación), el
Document Sanitizer bloqueó la petición ANTES del modelo — pero la respuesta de
bloqueo documental (`_document_blocked_response`, compartida con la ruta deprecada)
no rellena `posture: {}` en el Session File, así que `run_attack_suite.py` reporta
"POSTURA SOLICITADA ≠ EFECTIVA" para esa ejecución concreta. No es un defecto de
este PR — es un hueco de instrumentación preexistente en el propio backend que
nunca se había observado porque el canal documental nunca se había ejecutado de
verdad. Queda anotado para un PR propio; no bloquea la cobertura ni la evaluación
(el `disposition` del fixture sigue siendo correcto, como muestra la validación).
