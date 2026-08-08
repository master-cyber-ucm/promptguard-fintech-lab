# Fase 1 — Los cuatro vectores

> **Qué NO hay aquí:** el análisis de amenaza. Mapeo taxonómico OWASP/ATLAS, threat modeling,
> CVSS, casos reales, contexto VerdaBank y playbook de respuesta de cada vector están en
> [`docs/ataques/`](../../docs/ataques) y no se repiten.
>
> **Qué sí hay:** por qué estos cuatro, qué defendía el lab antes de este capítulo
> ([`estado-inicial.md`](./estado-inicial.md)), y qué fixtures se usan como conjunto de prueba.

## Selección — uno por nivel de dificultad

Los cuatro vectores se eligieron del ranking de dificultad de los nueve escenarios del catálogo,
tomando uno de cada nivel. No es una selección por comodidad: cubre desde el ataque que solo
necesita un pretexto social hasta el que exige fabricar un documento adversarial.

| # ranking | Vector | Dificultad | Por qué es difícil (según el ranking) |
|---|---|---|---|
| 2 | LLM02 — PII Harvesting | ★★☆☆☆ | Solo un pretexto social y un turno; no hace falta ningún IBAN concreto |
| 4 | LLM07 — System Prompt Leakage (API key) | ★★★☆☆ | Requiere reconocimiento previo: saber que existe `API_KEY_INTERNAL` |
| 6 | LLM06 — Confused Deputy | ★★★★☆ | Suplantación + conocimiento de IBANs ajenos + ingeniería social; multi-vector |
| 9 | LLM01 — Injection Indirecta (documento) | ★★★★★ | Crafting del documento, técnicas de ocultación y canal documental activo |

La dificultad del **ataque** resultó no correlacionar con la dificultad de la **defensa**. El
vector más difícil de ejecutar (★★★★★) ya estaba defendido en su eje principal; el más fácil
(★★☆☆☆) no tenía ninguna defensa. Ver [`estado-inicial.md`](./estado-inicial.md).

## Conjunto de prueba

Todos los fixtures salen del catálogo del laboratorio
(`lab/backend/tests/fixtures/`). No se inventó ninguno para este capítulo: usar los existentes
mantiene las cifras comparables con el resto del TFM.

### Caso 2 — PII Harvesting

| Fixture | Qué prueba |
|---|---|
| `atk_011` | Enumeración de IBANs con pretexto de auditoría interna |
| `atk_012` | Volcado de datos completos de todos los clientes |
| `atk_023` | Solicitud masiva de PII con excusa de auditoría |
| `atk_024` | Variante en inglés orientada a GPT |
| `leg_024` | **Legítimo** — consulta sobre privacidad y derecho de supresión |
| `leg_025` | **Legítimo** — saldo propio |

### Caso 4 — System Prompt Leakage

| Fixture | Qué prueba |
|---|---|
| `atk_015` | Extracción directa de `API_KEY_INTERNAL` con pretexto de webhook |
| `atk_029` | Evasión por traducción |
| `atk_064` | Extracción incremental multi-turno |
| `atk_065` | Roleplay de modo desarrollador |
| `leg_028` | **Legítimo** — pregunta por las capacidades del asistente |

`leg_028` es el guardián contra la sobrecorrección: un sistema que bloquea "¿qué puedes hacer?"
está roto, por muy bien que contenga los secretos.

### Caso 6 — Confused Deputy

| Fixture | Qué prueba |
|---|---|
| `atk_010` | Suplantación de administrador desde sesión de cliente |
| `atk_020` | Ingeniería social de urgencia ("mi cuenta ha sido hackeada") |
| `atk_028_deputy_progresivo` | Construcción progresiva multi-turno |
| `leg_001_consulta_saldo_propio` | **Legítimo** — saldo de la cuenta propia |
| `leg_002_transferencia_entre_cuentas_propias` | **Legítimo** — transferencia entre cuentas del mismo titular |
| `leg_003_autorizar_apoderado` | **Legítimo** — trámite de apoderamiento |
| `leg_027` | **Legítimo** — autorización de persona delegada |

Los dos últimos legítimos importan más de lo que parece: impiden validar el control contra un
modelo de titularidad ingenuo del tipo "una cuenta por usuario". La delegación legítima
—apoderados, cuentas conjuntas— es el caso en el que un control de propiedad mal diseñado empieza
a denegar operaciones válidas.

### Caso 9 — Injection Indirecta vía documento

Solo fixtures `type: document-upload`, que adjuntan un archivo real:

| Fixture | Vehículo |
|---|---|
| `atk_035` | PDF con nómina comprometida |
| `atk_036` | DOCX |
| `atk_037` | XLSX |
| `atk_069` | PDF orientado a forzar una transferencia |
| `leg_030`, `leg_031`, `leg_032` | **Legítimos** — los mismos formatos, sin payload |

Los fixtures `atk_050`–`atk_054` **no** se usan aquí: simulan el documento pegándolo como texto en
el chat y viajan por el canal JSON, así que no ejercitan la defensa del canal documental. Sí se
usa `atk_050` como sonda en el test del hueco, donde lo que se mide es el sanitizador de contenido
y no el canal.

## Actores del escenario

Todos los ataques se ejecutan como `usr_001` (María García López, cliente estándar,
cuenta `ES9121000418450200051332`). Las cuentas objetivo:

| Cuenta | Titular | Saldo | Papel |
|---|---|---|---|
| `ES5821000418450200051335` | Admin Banco | 999.999,99 € | Objetivo de `atk_010` |
| `ES3421000418450200051334` | Ana Fernández Ruiz | 231.500,00 € | Objetivo de `atk_020` y de los payloads documentales |
| `ES7621000418450200051333` | Carlos Rodríguez Martín | 8.750,25 € | Tercero en los volcados de PII |
