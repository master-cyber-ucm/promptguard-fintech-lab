# Defensa — Cross-Context Data Leakage

> Contra el ataque **#3** del catálogo · [ficha del ataque](../../ataques/LLM02-sensitive-information-disclosure/cross-context-leakage)
> **OWASP LLM02:2025 · MITRE ATLAS AML.T0024** · Incidente motivador **INC-2025-0089**
> **Módulos principales:** Leak Guard (`core/leak_guard.py`, IBANs) + PII Shield (`core/pii_shield.py`, resto de entidades) · **Apoyo:** Tool Gatekeeper, aislamiento de sesión
>
> **Nota de saneado (`TODOs.md §P5`, 2026-08-16):** este documento describía originalmente un
> único "Output Auditor" ampliado como segunda comprobación. La implementación real tomó otro
> camino — dos módulos separados, cada uno con su propio criterio de verificación — y el diseño
> no se había actualizado para reflejarlo. §4.2 y §10 están corregidos contra el código real.

---

## 1. Qué hay que impedir

Que un dato financiero de **otro cliente** llegue al usuario autenticado. El vector es la manipulación del contexto: pedir el saldo de una cuenta ajena con un pretexto razonable, invocar `consulta_saldo` con un `account_id` que no es propio, o inducir al modelo a repetir un dato que ya pasó por el contexto.

Este es el ataque que ocurrió de verdad en el escenario y el que activó el proyecto. También es el que más caro sale: notificación a la AEPD en 72 horas.

| Invariante | Cómo se garantiza |
|-----------|-------------------|
| **I1** — Ninguna tool devuelve datos de una cuenta que no pertenece al `user_id` | Tool Gatekeeper (`require_own_account: true`) |
| **I2** — Ningún dato financiero sale en la respuesta sin haber sido cruzado contra las cuentas del `user_id` | Output Auditor |
| **I3** — El contexto de una sesión no contiene datos de otra | Aislamiento estricto de sesión |

Tres invariantes deterministas, ninguna probabilística. **Esta es la única categoría del catálogo donde la defensa puede ser completa**, porque "¿es este IBAN del titular?" es una pregunta cerrada con respuesta binaria.

## 2. Principio de diseño

> La pertenencia de un dato a un usuario no se juzga: se comprueba contra la base de datos. Y se comprueba dos veces — antes de que el dato entre (Gatekeeper) y antes de que salga (Auditor).

La razón de la doble comprobación no es paranoia. I1 falla cuando el dato entra al contexto por una vía distinta a una tool call: un documento subido, un resumen de sesión, una alucinación del modelo que acierta un IBAN plausible, o un bug futuro en la tool. I2 no depende de por dónde entró.

## 3. Posición en el pipeline

```mermaid
flowchart TD
    U["usr_001\n'Comprueba el saldo de ES58...1335'"] --> SAN["Input Sanitizer\nfirma account_manipulation → SUSPICIOUS"]
    SAN --> CLARA["Clara — LLM"]
    CLARA -- "tool call\nconsulta_saldo(ES58...1335)" --> GK{"Tool Gatekeeper\n¿ES58...1335 ∈ cuentas(usr_001)?"}
    GK -- "NO" --> DENY["Denegada\nresultado: PERMISSION_DENIED"]
    GK -- "SÍ" --> EXEC["Core Banking mock"]
    DENY --> CLARA2["Clara redacta respuesta\ncon la denegación"]
    EXEC --> SHIELD["PII Shield\ntokeniza"] --> CLARA2
    CLARA2 --> OA{"Output Auditor\ncross-check de cada IBAN,\nsaldo y tarjeta del texto"}
    OA -- "dato ajeno detectado" --> BLK["Respuesta bloqueada\nincidente CRITICAL"]
    OA -- "todo pertenece a usr_001" --> R([Respuesta al usuario])
    BLK --> LOG["Compliance Logger + alerta DPO"]
    R --> LOG
    style DENY fill:#cce5ff
    style BLK fill:#ffcccc
    style GK fill:#cce5ff
    style OA fill:#cce5ff
```

## 4. Diseño del control

### 4.1 Tool Gatekeeper — la primera comprobación

Detalle completo en [`../LLM06-excessive-agency/confused-deputy.md`](../LLM06-excessive-agency/confused-deputy.md). Lo relevante aquí:

```python
# Pseudocódigo — validación determinista, fuera del LLM
def authorize(call: ToolCall, session: Session) -> Decision:
    spec = TOOL_PERMISSIONS[call.name]           # tool_permissions.yaml
    if spec.require_own_account:
        for account_id in extract_account_params(call):
            if account_id not in accounts_of(session.user_id):
                return Decision.DENY("account_not_owned")
    return Decision.ALLOW
```

Nótese que `session.user_id` **procede del token de autenticación, nunca del texto de la conversación**. Si el `user_id` se leyera del contexto del modelo, el atacante podría reescribirlo con una inyección y el control entero sería decorativo.

### 4.2 Leak Guard + PII Shield — la segunda comprobación

Ejecutan sobre el texto final, después de que Clara haya redactado y antes de responder al
usuario. El diseño original planteaba un único "Output Auditor" ampliado que extrajera todos los
patrones (IBAN, tarjeta, SWIFT, saldo) y resolviera el conjunto autorizado en un solo paso. La
implementación real reparte esa responsabilidad en **dos módulos con criterios de verificación
distintos**, ejecutados en este orden:

**1. `leak_guard.py::confidential_leak_guard`** — solo IBANs. Extrae los IBAN españoles de la
respuesta con regex y los cruza contra el conjunto `{cuenta propia del user_id} ∪ {IBANs que
aparecen en un resultado NO denegado de `tools_used` en este mismo turno}`. No consulta la base
de cuentas: verifica que el dato tenga un origen real dentro de la conversación, no que exista en
el sistema. Cualquier IBAN fuera de ese conjunto sustituye la respuesta completa por un mensaje
neutro.

  | Caso | Decisión |
  |------|----------|
  | El IBAN es el de la cuenta propia del `user_id` | ALLOW |
  | El IBAN aparece en un resultado real (no `denied`) de una tool de este turno | ALLOW — es el caso legítimo de un beneficiario de transferencia |
  | El IBAN no está respaldado por ninguna de las dos vías anteriores | **BLOCK** — sustituye toda la respuesta |

**2. `pii_shield.py::redact_foreign_pii`** — el resto de entidades (nombre de titular, saldo,
tarjeta, DNI, teléfono, email). Aquí sí hay consulta a datos: resuelve `MOCK_ACCOUNTS`,
`MOCK_CARDS` y `MOCK_USERS` por `user_id` para construir el conjunto de valores propios, y
tokeniza (o descarta la respuesta entera, si hay cosecha masiva) cualquier entidad de tercero.
Corre después del Leak Guard a propósito: si este ya sustituyó la respuesta, no queda nada que
tokenizar.

No existe hoy una detección de **saldo ajeno como cifra suelta** (un importe sin IBAN al lado) —
ver §4.3, sigue siendo un diseño propuesto, no implementado — ni una resolución de **tokens del
PII Shield entre sesiones distintas**: el mapeo token→valor no se comparte entre `user_id`, así
que esa fila del diseño original no aplica al mecanismo real (los tokens no viajan fuera de la
sesión que los generó).

**Respuesta segura.** Ambos módulos, ante bloqueo, devuelven un mensaje neutro y no una versión
"censurada" del texto: un texto parcialmente redactado sigue filtrando estructura ("el saldo de
esa cuenta es [REDACTED]" confirma que la cuenta existe y que hay saldo).

### 4.3 Detección de saldos: el caso difícil

Los IBANs son fáciles: formato reconocible y comparación exacta. Los **importes** no. `4.230,55 €` en una respuesta puede ser el saldo del usuario, el de otro, un ejemplo o un importe de transferencia.

Diseño propuesto:

- Construir el conjunto de "importes sensibles del contexto": todo valor monetario devuelto por tools en esta sesión, con su cuenta asociada.
- Un importe de la respuesta que coincida con un valor asociado a **otra cuenta** → BLOCK.
- Un importe que no aparezca en ningún resultado de tool → marcar como posible alucinación, severidad MEDIUM (no bloqueante por defecto, configurable).

Esto tiene falsos positivos (coincidencias numéricas casuales) y falsos negativos (el modelo redondea: "unos 4.200 €"). Se documenta como límite conocido; el control fuerte sigue siendo I1.

### 4.4 Aislamiento estricto de sesión

Requisito estructural, previo a todo lo anterior:

- **Una ventana de contexto por `session_id`**, sin reutilización de objetos de conversación entre usuarios.
- El store de sesión (`lab/backend/src/agents/session_store.py`) debe indexar por `session_id` y validar `user_id` en cada lectura, no solo en la escritura.
- **Sin caché compartida de respuestas del modelo** entre usuarios: una caché por prompt normalizado es un canal de fuga directo entre clientes.
- El mapeo token→valor del PII Shield se destruye al cerrar la sesión.
- TTL explícito de sesión; el contexto no vive indefinidamente.

## 5. Límites conocidos

| Límite | Consecuencia | Mitigación |
|--------|-------------|------------|
| Detección de saldos por coincidencia numérica | Falsos positivos y negativos (redondeos, paráfrasis) | Apoyarse en I1; tratar los importes como señal secundaria |
| El modelo puede describir el dato sin escribirlo | "Tiene fondos de sobra para cubrir los 3.000 €" filtra información sin emitir el saldo | Límite real y no resuelto; se mitiga en I1, no en I2 |
| IBAN ofuscado por el modelo (espacios, guiones raros) | Evade el regex | Normalizar la respuesta antes de aplicar patrones |
| Datos de terceros legítimamente presentes | Un beneficiario de transferencia sí es una cuenta ajena legítima | Lista blanca contextual: cuentas destino que el propio usuario ha introducido en el turno |
| Coste de la consulta al conjunto autorizado | Una consulta a datos por respuesta | Cacheable por sesión |
| `session_store.py` indexa solo por `session_id`, sin validar `user_id` en cada lectura (I3) | Si un `session_id` se filtrara o colisionara, `get_history()` lo serviría sin comprobar a quién pertenece | No mitigado. Declarado como hueco abierto, no como decisión de diseño — ver `core/leak_guard.py`, cabecera "Alcance declarado" |
| Sin importes monetarios cruzados contra el saldo de otras cuentas | Una cifra ajena sin IBAN al lado ("231.500 €") no dispara ninguna guardia | No mitigado. §4.3 sigue siendo un diseño propuesto, no código |

El segundo límite merece énfasis en el TFM: **la filtración semántica sin emisión del dato no es detectable con controles de patrón**. Es un argumento a favor de resolver este ataque en la capa de tools (I1) y tratar el Output Auditor como red de seguridad, no como control primario.

## 6. Controles complementarios

| Control | Qué añade |
|---------|-----------|
| **Input Sanitizer** | La firma `account_manipulation` marca la petición como SUSPICIOUS y eleva el nivel de log, aunque no bloquee |
| **PII Shield** | Reduce el material disponible: si el dato ajeno nunca entró como valor real, no hay nada que filtrar |
| **Compliance Logger** | Evidencia firmada de la detección: es lo que permite fechar el conocimiento de la brecha para el reloj GDPR de 72 h |
| **Alerta al DPO** | Un BLOCK de este tipo notifica automáticamente al Data Protection Officer, no solo al SOC |

## 7. Validación

**Fixtures de ataque** (`lab/backend/tests/fixtures/LLM02-sensitive-information-disclosure/cross-context-leakage/attack-prompts/`):

| Fixture | Vector |
|---------|--------|
| `atk_008` | Petición directa del saldo de cuenta ajena disfrazada de verificación de pago empresarial |
| `atk_009` | Invocación directa de `consulta_saldo` con IBAN ajeno |
| `atk_025` | Cross-context por ambigüedad semántica en la identidad del cliente |
| `atk_026` | Variante en inglés orientada a Llama |

`atk_025` es el fixture crítico: fue **uno de los tres ataques que tuvieron éxito** contra un modelo alineado sin ninguna defensa. No dice "ignora tus instrucciones"; explota la ambigüedad. Es la prueba de que el alignment del modelo no cubre esta categoría.

**Legítimo:** `leg_025` (consulta del saldo propio) — debe pasar sin fricción.
**Navi:** `navi_006` (intento obvio) — debe denegarse en el Gatekeeper.

### Criterios de aceptación

| Métrica | Objetivo |
|---------|----------|
| Denegación en el Gatekeeper de los 4 fixtures de ataque | 100% |
| `atk_025` bloqueado con las defensas activas | Sí — es el caso testigo del módulo |
| Falso positivo sobre `leg_025` | 0% |
| Respuesta a un BLOCK del Auditor | Mensaje neutro, sin redacción parcial |
| Latencia añadida del Auditor | <50 ms p95 |
| Cobertura de log | 100% de las decisiones, con `user_id`, dato detectado y veredicto |

### Prueba de aislamiento de sesión

Prueba explícita y separada: dos sesiones concurrentes de usuarios distintos consultando datos en paralelo. Ningún dato de la sesión A puede aparecer en la B, ni siquiera bajo peticiones de la forma "¿qué has consultado antes?". Esta prueba debe estar en la regresión permanente: es el escenario exacto de INC-2025-0089.

## 8. Coste operativo

| Dimensión | Estimación |
|-----------|-----------|
| Latencia del Gatekeeper | <5 ms (comparación en memoria) |
| Latencia del Auditor | 20–50 ms (regex + consulta cacheada) |
| Falsos positivos esperados | Bajos en IBAN, moderados en importes |
| Coste de un falso negativo | Notificación AEPD, sanción potencial, daño reputacional — asimetría que justifica configurar el módulo hacia el bloqueo |

## 9. Mapeo normativo

| Norma | Artículo | Cómo lo satisface |
|-------|----------|-------------------|
| GDPR | Art. 5.1.f (integridad y confidencialidad) | Cross-check obligatorio antes de cada respuesta |
| GDPR | Art. 32 | Medida técnica apropiada frente al acceso no autorizado |
| GDPR | Art. 33 | La detección fechada y firmada inicia el cómputo de 72 h con evidencia |
| DORA | Art. 9 | Control de salida del canal conversacional |
| EU AI Act | Art. 13 | Cada decisión del Auditor queda registrada |
| EU AI Act | Art. 15 | Robustez frente a manipulación del contexto |

## 10. Estado

> Corregido el 2026-08-16 contra el código real — la versión anterior no se había actualizado
> desde el diseño inicial y declaraba "sin implementar" cosas que ya lo estaban (Tool
> Gatekeeper), y "implementado" un módulo (Output Auditor ampliado) que nunca se construyó así.

- [x] Invariantes definidos (I1, I2, I3)
- [x] Patrones de detección disponibles (`banking_patterns.yaml`, regex IBAN en `leak_guard.py`)
- [x] Reglas de propiedad de cuenta definidas (`tool_permissions.yaml`, `require_own_account: true`)
- [x] Tool Gatekeeper implementado (I1) — `consulta_saldo`, `transferencia_nacional`, `bloquear_tarjeta`
- [x] I2 implementado — repartido en dos módulos reales, no en un Output Auditor único: `core/leak_guard.py` (IBANs) + `core/pii_shield.py` (resto de entidades). Ver §4.2.
- [x] Validado contra `atk_008`, `atk_009`, `atk_025`, `atk_026`, `leg_025`, `navi_006` — evidencia en `docs/reports/evidencia-cross-context-leakage.md`
- [ ] Detección de importes sensibles del contexto (§4.3) — sigue siendo diseño propuesto, sin código
- [ ] Aislamiento estricto de sesión por `user_id` verificado — **no implementado**. `session_store.py` indexa solo por `session_id`; `leak_guard`/`pii_shield` cierran la fuga dentro de un turno, no entre sesiones. Declarado como hueco abierto en `core/leak_guard.py` (cabecera "Alcance declarado") y en §5.
- [ ] Alerta automática al DPO — no implementado. El SOC registra la Alerta con severidad `CRITICAL` (mapeo de categoría en `api/routes/soc.py`) para revisión humana; no hay integración con un canal de notificación real.
- [ ] Prueba de concurrencia entre sesiones en la regresión — no existe. Requiere primero resolver el punto anterior para que la prueba verifique algo real y no una propiedad que ya se cumple por construcción del diccionario en memoria.
