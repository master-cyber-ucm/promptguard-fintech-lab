Análisis de la ejecución 20260901_190305_qwen2.5-3b

He cruzado suite-final.4.log con run.md, run.json y el código de evaluación (scripts/evaluations/*.py) del propio repo. Mi lectura, como si estuviera evaluando esto en una defensa de TFM:

Lo que está bien hecho (y hay que decirlo, porque es poco frecuente)

- El propio informe se niega a mentir por omisión. La sección "Claims suprimidos por cobertura insuficiente" y la tabla de Reconcilia ✅ muestran que el pipeline calcula un denominador sellado antes de ejecutar y no deja desaparecer del recuento lo que falló o quedó sin evidencia. Eso es exactamente la disciplina que se le exige a un informe experimental serio, y la mayoría de proyectos de este nivel no lo tienen.
- Separación de seguridad y utilidad como ejes independientes. La tabla "Seguridad × utilidad" evita el error clásico de contar "respuesta segura pero inútil" como éxito de la defensa. Bien pensado.
- Bootstrap pareado por fixture (no por repetición) para el delta causal. Es la forma correcta de no inflar artificialmente el intervalo de confianza tratando repeticiones del mismo caso como observaciones independientes.
- El propio run se auto-descalifica para agregación: detecta árbol de trabajo sucio y lo dice explícitamente ("este run no puede agregarse c ver el puntocrítico #2 abajo.

Problema crítico #1 — El evaluador determinista no lee el texto
de la respuesta

Esto es lo más grav el 50-65% de lasejecuciones acaban en EVIDENCE_INSUFFICIENT (tabla "Cobertura",
filas Inconclusas).

Fui a la causa raízterministic.py. El87% de las ejecuciones (2005/2303) usan method="deterministic",
cuyo criterio de "ben telemetría dellamadas a tools (forbidden_events/required_events sobre
tool_outcomes). Cuai un eventoprohibido ni una ausencia de evento requerido — es decir, cuando
el modelo "compromevez de llamando auna tool — el código cae aquí:

if is_attack:
    return self._no
                                                                _no_effect marca moeffect_outcome=NO_HARMFUL_EFFECT_OBSERVED, y nunca invoca al    juez. Lo confirmé e
                                                                ┌──────────────────────┬─────┐
│              Método              │ Inconclusas │  %  │        ├──────────────────────┼─────┤
│ deterministic (2005 ejecuciones) │ 1167        │ 58% │        ├──────────────────────┼─────┤
│ hybrid (198 ejecuciones)         │ 0           │ 0%  │        ├──────────────────────┼─────┤
│ hybrid_attack (100 ejecuciones)  │ 5           │ 5%  │        └──────────────────────┴─────┘
                                                                Y de las 1172 ejecu el run, solo 5llegaron al juez semántico (qwen3.5:9b) — el resto se resolvió  "por defecto" sin qe la respuesta. Esto ocurre transversalmente en las 11 familias de ataque            (EXCESSIVE_AGENCY, ESTING,SYSTEM_PROMPT_LEAKAGE, JAILBREAK, etc.), no en un caso aislado. 
Por qué esto es grave para la tesis: cualquier ataque que triunfsin pasar por una tla el system prompt en prosa, coopera con un jailbreak narrativo, o filtra un dato  de contexto por escinvisible para el87% del arnés. No es que el modelo se comporte bien en esos     casos: es que nadieón proxy-full vsproxy-baseline que es el resultado central del capítulo         experimental queda l 44–57%, por debajo del umbral 99% que el propio informe exige — y por eso la       sección "Comparacióon ❌ no comparable. El hallazgo más vendible del trabajo (que el proxy reduce el    efecto dañino en -2ificativo) estácalculado sobre datos que el propio sistema dice que no alcanzanpara sostener el cl
                                                                Recomendación concre familias sin toolobligatoria (PII_HARVESTING conversacional, JAILBREAK,          SYSTEM_PROMPT_LEAKA method:deterministic a method: hybrid o hybrid_attack con fallback.whenrequired_event_misspara que elfallback semántico se dispare igual que ya hace en los 100      fixtures hybrid_attncluso baja a 5%).Es un cambio de configuración de fixtures, no de arquitectura.  
Problema #2 — Reproducibilidad: árbol sucio + commit que no     identifica el códig
                                                                El log lo marca él DIRTY_FILES=1,commit 9acd750. Para una tesis que exige reproducibilidad (tu   propio CLAUDE.md detamente), un run con working tree sucio no es defendible como evidencia final — es,  en el mejor caso, u. Antes deconsiderar estos números como los del capítulo experimental, hayque repetir el run itarlo.
                                                                Problema #3 — Fixtu
                                                                El arranque del log5, atk_036, atk_037, atk_069, atk_072, atk_076, leg_030-034) con cobertura cero:     ningún target los ebre sus familiasqueda automáticamente sin sustento. Hay que decidir             explícitamente si eecir por qué) ocompletar la matriz fixture×target.                             
Problema #4 — El gate global no lo pasa ninguna postura, incluidla defensa completa
                                                                La tabla "Seguridadas 5 filas,proxy-full incluido. Combinado con la tabla de "Utilidad        legítima": el éxito resueltascorrectamente) va del 24% al 57% según endpoint, con            SAFE_BUT_UNHELPFUL 9 casos). Estosugiere que qwen2.5:3b tiene un problema de capacidad basal,    independiente de setimas confrecuencia. Eso contamina la interpretación de "el ataque no tuvefecto" — en un mod" puede significar"no entendió la tarea", no "se resistió al ataque". Para las    conclusiones de la ir con un modelo dereferencia más capaz para separar "seguro por diseño" de "seguropor incompetencia",sión explícitamentecomo limitación.                                                
Problema #5 — Agujeros reales en la defensa proxy-full (esto sí es un hallazgo de s
                                                                Con los datos que s
- OBFUSCATION: 0/25 bloqueados (0.0%) en proxy-full, la única     familia con contener las cincodefensas activas. Coincide entre el log (OBFUSCATION 0.0% /     100.0%) y run.md.
- LLM07 (system prompt leakage): 0/25 contenidos en proxy-full,   igual que en las eak_guard youtput_auditor no están capturando esta categoría en absoluto.- DEFENSE_FALSE_POSll (5/69 sobretráfico legítimo) — el único endpoint con falsos positivos de   defensa medibles.
- Punto positivo real: el bloqueo PRE_MODEL_BLOCK de proxy-full   tiene p50 de 0.9mn de entrada esefectiva y barata cuando actúa.                               
Estos tres puntos (OBFUSCATION y LLM07 en cero, FP del 7%) son  defendibles como ha de la ambigüedaddel punto #1 — son bloqueos/no-bloqueos observados directamente,no inferidos de aus
                                                                ---
                                                                Resumen para tu defal y el aparato decontabilidad (cobertura, reconciliación, supresión de claims)   están a un nivel má trabajos de estetipo — eso hay que subrayarlo. Pero el resultado headline       (proxy-full reduce te no es citablecomo está porque el propio sistema certifica que le falta       cobertura, y la cau bug de diseñoconcreto y arreglable en deterministic.py (ausencia de fallback semántico), no un lque. Yo priorizaría: (1) arreglar la migración de método en fixtures de texto pur(2) re-correr sobrees sí recalcular lacomparación causal — y probablemente el -29pp se sostenga o mejore, pero ahora