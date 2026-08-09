# Roadmap — Defensa de 4 vectores (casos 2, 4, 6 y 9)

> Checklist por fases. Ver `00-INSTRUCCIONES.md` para el encuadre y las reglas de trabajo.

## Fase 0 — Setup ✅

- [x] 0.1 Rama `feat/daniel-defensas-4-vectores` partida de `feat/suite-improvements`
- [x] 0.2 Worktree aislado (`../software-daniel`) para no interferir con el backend Docker
      compartido, que corre con `--reload` sobre el árbol principal
- [x] 0.3 Entorno Python aislado con las dependencias de `lab/backend/requirements.txt`
- [x] 0.4 Línea base de tests — **8 fallos preexistentes** detectados y arreglados
      (dobles de test sin `all_messages()` tras la memoria de sesión). 63 tests en verde
- [x] 0.5 Backend aislado en `:8010` contra Ollama local (`qwen2.5:3b`)

## Fase 1 — Medición del estado inicial ✅

- [x] 1.1 Sonda ejecutable sobre los módulos deterministas, sin LLM
- [x] 1.2 Caso 6 (Confused Deputy) — **ya cubierto** por el Tool Gatekeeper
- [x] 1.3 Caso 4 (API key) — **parcial**: 4 variantes de evasión atraviesan el módulo
- [x] 1.4 Caso 9 (documento) — **cubre override, no exfiltración de datos**
- [x] 1.5 Caso 2 (PII Harvesting) — **sin defensa**, esqueleto no-op
- [x] 1.6 Síntesis: el hueco no son 4 problemas, es 1 eje sin cubrir
      → `01-vectores/estado-inicial.md`

## Fase 2 — Implementación ✅

### 2.1 PII Shield — el control del eje "dato que sale"
- [x] Flanco de entrada: detección de enumeración masiva (control de patrón, sin garantía)
- [x] Flanco de salida: cruce contra el conjunto autorizado del `user_id` (determinista)
- [x] Entidades sin forma regular (nombre de titular, saldo) vía catálogo real de cuentas
- [x] Variantes de formato de importe (anglosajón / europeo / sin decimales)
- [x] Umbral de cosecha masiva: ≥2 terceros → descartar respuesta entera
- [x] **Bug encontrado y corregido**: `phone_es` casaba dentro del IBAN → resolución de
      solapamientos por longitud
- [x] 31 tests, incluidos 10 prompts legítimos que no pueden bloquearse

### 2.2 Output Auditor — de literal a normalizado
- [x] Normalización (minúsculas, sin acentos, sin invisibles, sin separadores)
- [x] Ajuste del literal del bucket S3 (el secreto es el nombre, no el esquema)
- [x] Detector de umbrales del bloque interno
- [x] **Falso positivo encontrado y corregido**: dos importes redondos de cliente disparaban el
      detector → se exige además vocabulario del bloque interno
- [x] **Bug de conteo**: `10000` contiene `1000` → una sola cifra contaba como dos umbrales
- [x] 24 tests

### 2.3 Confused Deputy — verificación y regresión
- [x] Regresión atada a `atk_010`, `atk_020`, `atk_028_deputy_progresivo`
- [x] Contrafactual con `enforce_gatekeeper=False` (el bloqueo lo produce el control, no el modelo)
- [x] 7 prompts legítimos verificados
- [x] 13 tests

### 2.4 Cruce documento × PII
- [x] Hueco fijado por escrito: el payload de exfiltración atraviesa `document_sanitizer`
- [x] `defensa_pii_shield` en `/chat/complex-with-document`, **desactivada por defecto**
      (precedente: `defensa_separacion_tool_framing`)
- [x] 8 tests

### 2.5 Cableado e integración
- [x] PII Shield conectado al orquestador (entrada vía stage, salida tras el leak guard)
- [x] `/chat/proxy` con la capa activa; baselines intactos
- [x] `E(pii_shield)=…` en la cadena `defensas_activas` para que toda corrida diga si estaba puesta
- [x] 11 tests de integración del pipeline
- [x] **Suite completa: 150 tests en verde**

## Fase 3 — Evidencia experimental ✅

- [x] 3.1 Runner propio (`02-defensa/evidencia/ejecutar_evidencia.py`) — la suite compartida no
      incluye `/chat/proxy` y añadirlo allí habría cambiado el conjunto por defecto del equipo
- [x] 3.2 Veredicto con el `DeterministicEvaluator` del proyecto, no con criterio propio
- [x] 3.3 **Bug encontrado**: la API devuelve `args` como cadena y el evaluador espera dict
      → adaptador `_normalizar_tools()`; añadido volcado incremental tras perder una corrida entera
- [x] 3.4 Corrida completa: 50 ejecuciones (4 casos × {vulnerable, defendida})
- [x] 3.5 **Artefactos de medición detectados** (3 modos): el evento se dispara con la invocación
      de la tool aunque el Gatekeeper la deniegue, aunque no retorne, y con la mención del nombre
      de un secreto en un rechazo → métrica de **fuga real** en post-proceso
      (`analizar_resultados.py`), sin tocar el evaluador compartido
- [x] 3.6 **Auditoría del propio detector** con tráfico legítimo → dos defectos de `phone_es`
      corregidos; limitación de cuenta única declarada
- [x] 3.7 Resultados en `02-defensa/evidencia/resultados_<timestamp>/` (`resultados.md`,
      `fuga-real.md`, `resultados.json`)

## Fase 4 — Redacción 🔄

- [x] 4.1 `01-vectores/estado-inicial.md` — la medición y el análisis del hueco
- [x] 4.2 `02-defensa/README.md` — implementación y decisiones
- [x] 4.3 `02-defensa/evidencia/README.md` — cómo leer las métricas
- [x] 4.4 `03-normativa/README.md` — lo normativo específico de estos vectores
- [x] 4.5 `CAPITULO.md` — prosa para el documento final
- [x] 4.6 `bitacora/BITACORA.md` — diario cronológico
- [x] 4.7 Revisión final de coherencia y de que ninguna afirmación queda sin evidencia

## Fase 5 — Investigación del 0% (casos 2 y 4) ✅

Disparada al revisar la evidencia: un 0% de éxito en la columna «vulnerable» es sospechoso.

- [x] 5.1 Diagnóstico de las dos causas (verificación en código + pruebas manuales)
  - Caso 4: `audit_response()` corría incondicionalmente → no había línea base indefensa
  - Caso 2: `atk_011/012` piden enumerar una BD inalcanzable → ataque inganable, no defendido
- [x] 5.2 Entorno vulnerable real: flag `vulnerable` en `ChatRequest` (default False) que
      desactiva Output Auditor, guardia de fuga, Gatekeeper, PII Shield e Input Sanitizer
- [x] 5.3 Payloads que SÍ explotan, hallados a mano:
  - Caso 4: prefix injection 4/4, lista de secretos 4/4, webhook 3/4 (`atk_073`–`atk_075`)
  - Caso 2 vía documento: transcripción de export de terceros 3–5/5 (`atk_076`)
- [x] 5.4 Hallazgo lateral: las capas no son independientes — el PII Shield de salida exime los
      IBAN que una tool devolvió, y sin Gatekeeper eso es un agujero
- [x] 5.5 Observación: los payloads canónicos de extracción los bloquea el alignment del modelo
      sin defensas; en `qwen3.5:9b` incluso los efectivos fallan → la viabilidad depende del modelo
- [x] 5.6 Runner reproducible (`reproducir.py`) + documento (`investigacion-0pct/README.md`,
      `payloads-que-explotan.md`)
- [x] 5.7 6 tests del flag `vulnerable` (`test_flag_vulnerable.py`) — 156 tests en verde

## Trabajo futuro declarado (no entra en este capítulo)

- **Tokenización antes del modelo.** El PII Shield actual actúa sobre la respuesta. El diseño de
  `docs/defensas/.../pii-harvesting.md` describe además tokenización reversible *antes* de que el
  dato entre al contexto, con vault de sesión. Requiere tocar el retorno de las tools y el
  historial de sesión; queda fuera.
- **Presidio.** El NER genérico (nombres arbitrarios, direcciones) sigue sin cubrirse: el módulo
  cruza contra el catálogo de titulares del lab, que es exacto pero cerrado.
- **Fuga semántica sin emisión del dato.** "Esa cuenta tiene fondos de sobra para cubrir los
  3.000 €" no es detectable por comparación de valores. Límite reconocido, no resuelto.
- **Attack Pattern Detector.** La correlación de intentos por sesión (sondeo, extracción
  incremental) pertenece a la Extensión 1 del catálogo.
