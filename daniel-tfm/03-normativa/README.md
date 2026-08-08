# Fase 3 — Marco normativo aplicado a estos 4 vectores

> El mapeo normativo **genérico** de cada vector ya está en
> [`docs/defensas/`](../../docs/defensas) y en `docs/ataques/*/05-cumplimiento-normativo.md`.
> Aquí solo va lo que cambia **porque ahora existe una implementación medida**: qué requisito
> pasa de intención declarada a control con evidencia, y qué sigue sin cubrirse.

La distinción importa para el tribunal: un mapeo que dice "el PII Shield satisface GDPR Art. 32"
es una afirmación de diseño. Una que dice "el PII Shield satisface GDPR Art. 32, aquí está el
control, aquí el test que lo fija y aquí la corrida que lo mide" es evidencia.

---

## GDPR

### Art. 5.1.c — Minimización · de principio a control ejecutable

Antes de este capítulo, la minimización era una intención: `banking_patterns.yaml` declaraba qué
entidades había que redactar y **ningún código leía ese fichero**. El PII Shield lo conecta:
IBAN, tarjeta, SWIFT, teléfono, email y DNI se detectan con esos patrones y se tokenizan cuando
no pertenecen al usuario autenticado.

Matiz honesto sobre el alcance: la implementación actúa sobre la **salida**. El diseño completo
([`docs/defensas/.../pii-harvesting.md`](../../docs/defensas/LLM02-sensitive-information-disclosure/pii-harvesting.md))
contempla además tokenizar *antes* de que el dato entre al contexto del modelo, con vault de
sesión. Eso no está implementado, y por tanto **el argumento de que "los datos personales en
claro no salen hacia el proveedor del LLM" (relevante para Art. 44 y ss., transferencias
internacionales) todavía no se sostiene** en este lab. Se declara como trabajo futuro en el
ROADMAP, no como logro.

### Art. 32 — Seguridad del tratamiento

Tres controles con evidencia:

| Control | Qué garantiza | Evidencia |
|---|---|---|
| Tool Gatekeeper | Ningún usuario opera sobre recursos de terceros | `test_confused_deputy_fixtures.py` (13 tests) + contrafactual |
| PII Shield (salida) | Ningún dato personal de terceros sale en la respuesta | `test_pii_shield.py` (27 tests) |
| Output Auditor | Ningún secreto de configuración sale en la respuesta | `test_output_auditor_secretos.py` (24 tests) |

El Art. 32 pide medidas "apropiadas al riesgo" y cita expresamente la **seudonimización**. La
tokenización con preservación de los últimos 4 dígitos es seudonimización; se documenta también
su concesión: preservar 4 dígitos reduce entropía a cambio de que el cliente reconozca su cuenta.

### Art. 33 — Notificación de brecha en 72 h

El cambio real no es que haya menos brechas, es que **ahora hay detección fechada**. Un turno
bloqueado deja Session File con la marca (`BLOCKED_BY_PII_SHIELD`) y, en el proxy, firma HMAC
(`sign_turn`). Sin eso, una fuga de PII era un evento silencioso: nadie podía decir cuándo se
supo, y el reloj de 72 h no puede empezar a contar sobre algo que no se registró.

Verificado en `test_el_turno_bloqueado_deja_session_file`.

### Art. 25 — Protección desde el diseño

Aplica parcialmente y conviene decirlo así. El PII Shield es un control **añadido** a un sistema
existente, no una propiedad del diseño original: el lab se construyó deliberadamente vulnerable.
Lo que sí es "desde el diseño" es que el Tool Gatekeeper resuelva la identidad desde el canal de
autenticación (`ctx.deps.user_id`) y no desde un parámetro que el modelo pueda rellenar — esa
decisión sí es estructural y no un filtro posterior.

---

## DORA

### Art. 9 — Protección · Art. 10 — Detección

| Requisito | Estado tras este capítulo |
|---|---|
| Controles sobre el canal ICT | Tool Gatekeeper + PII Shield + Output Auditor, todos deterministas |
| Detección en tiempo real | Cada decisión de bloqueo emite log `WARNING` con la entidad detectada y queda en el Session File |

Lo que **no** se ha construido: correlación de eventos entre turnos y sesiones (detección de
sondeo sistemático). Un atacante que prueba diez formulaciones distintas genera hoy diez eventos
aislados, no un incidente. Pertenece al `Attack Pattern Detector` de la Extensión 1.

### Art. 12 — Aprendizaje post-incidente

El Session File registra la respuesta **original** del modelo junto a la marca de sustitución
(`[GUARDIA DE SALIDA ACTIVADA — respuesta original sustituida…]`, `[PII SHIELD — N entidades
tokenizadas…]`). Es decir: el cliente recibe la versión saneada y el auditor conserva la
original. Sin eso, el post-mortem no podría reconstruir qué llegó a generar el modelo.

---

## EU AI Act (Reglamento 2024/1689)

Clara es sistema de alto riesgo (Anexo III, 5.b — acceso a servicios financieros).

| Artículo | Requisito | Estado |
|---|---|---|
| **Art. 13** — Transparencia y trazabilidad | Registro de la actividad | ✅ Session File por turno, incluidos los bloqueados; firma HMAC en el proxy |
| **Art. 14** — Supervisión humana | Intervención humana en decisiones críticas | ⚠️ **No cubierto por este capítulo.** El Gatekeeper valida propiedad pero no exige confirmación fuera de banda; los límites de importe y la aprobación humana son el ataque #1, fuera de alcance |
| **Art. 15** — Robustez y ciberseguridad | Medidas frente a manipulación | ✅ Tres controles deterministas + endurecimiento frente a evasión por normalización |

El Art. 14 merece la marca de "no cubierto" y no una interpretación generosa: `tool_permissions.yaml`
declara `requires_approval: true` para `transferencia_nacional` y **ninguna línea de código lo
lee**. Declararlo satisfecho sería el mismo error que este capítulo encontró al medir el estado
inicial — confundir configuración escrita con control implementado.

---

## Lo que la implementación cambia respecto al análisis normativo previo

Tres correcciones concretas sobre lo que los documentos de diseño daban por hecho:

1. **`banking_patterns.yaml` no estaba conectado a nada.** Los documentos de defensa lo citan
   como el mecanismo del PII Shield y del Output Auditor. Era un fichero muerto hasta este
   capítulo. Cualquier afirmación normativa que se apoyara en él era, hasta ahora, una intención.

2. **La detección de secretos por cadena literal no aguanta un análisis de robustez (AI Act Art.
   15).** Un control que se evade escribiendo el mismo secreto con guiones no es una "medida
   técnica frente a la manipulación". Tras la normalización, sí.

3. **El canal documental no tenía control de salida de datos personales.** Un documento podía
   pedir —sin instruir nada— que el asistente incluyera datos de terceros, y salían. Para GDPR
   Art. 32 esto es relevante porque el vector de entrada (documento adjunto) es precisamente el
   que el cliente controla por completo.

---

## Fuera de alcance, declarado

| Requisito | Por qué no |
|---|---|
| EU AI Act Art. 14 (supervisión humana efectiva) | Confirmación fuera de banda y límites de importe pertenecen al ataque #1 (Excessive Agency) |
| GDPR Art. 44 y ss. (transferencias internacionales) | Requiere tokenización *antes* del modelo, no implementada |
| DORA Art. 17 (notificación al regulador) | Requiere retención de 5 años y política de reporte, fuera del lab |
| PSD2 / EBA | La autenticación reforzada es del canal de pago, no del conversacional |
