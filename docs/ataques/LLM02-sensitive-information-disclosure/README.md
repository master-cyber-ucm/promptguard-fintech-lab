# LLM02:2025 — Sensitive Information Disclosure

> **OWASP LLM Top 10 (2025) — LLM02:2025 · MITRE ATLAS AML.T0024**
> Categoría del catálogo. Agrupa **2 ataques** del escenario base de VerdaBank.

## Definición

El modelo revela **datos confidenciales que no deberían llegar al usuario**: información de otros clientes, PII acumulada en el contexto de sesión, saldos, IBANs o secretos de configuración. OWASP incluye aquí tanto el filtrado de datos de terceros como la exposición progresiva de datos sensibles.

En el escenario bancario esta categoría es la de **mayor impacto regulatorio**: cualquier filtrado de dato personal activa obligaciones GDPR.

## Por qué es relevante en VerdaBank

- Es la categoría del **incidente motivador del TFM** (INC-2025-0089): Clara filtró el saldo de otro cliente.
- Clara procesa de forma continua **IBANs, saldos, movimientos y datos de tarjeta** dentro del contexto de conversación.
- **GDPR Art. 33**: notificación obligatoria a la AEPD en 72 horas ante una brecha de dato personal.

## Ataques en esta categoría

| # | Ataque | Subcarpeta | Distinción |
|---|--------|-----------|------------|
| 3 | Cross-Context Data Leakage | [`cross-context-leakage/`](./cross-context-leakage) | Filtra datos de **otro usuario** vía manipulación del contexto |
| 6 | PII Harvesting vía Contexto | [`pii-harvesting/`](./pii-harvesting) | Extracción **progresiva** de PII acumulada en la sesión |

Ambos filtran datos, pero #3 salta la **frontera entre usuarios** (acceder a lo ajeno) mientras #6 acumula **lo propio y lo de otros** turno a turno de forma encubierta. Ángel de ataque distinto → defensa complementaria.

## Filosofía de defensa

Dos módulos cubren los dos flancos:

- **PII Shield** (prevención): redacta IBANs, tarjetas y saldos **antes de que lleguen al LLM**, usando tokens reversibles. El modelo nunca procesa el dato real.
- **Output Auditor** (verificación): escanea la respuesta buscando datos financieros que **no pertenezcan al usuario autenticado** y aplica **strict session isolation**.

El principio es defensa en profundidad: nunca confiar en que el LLM "decida bien"; verificar el output contra las cuentas legítimas del `user_id` de la sesión.

## Mapeo normativo

- **GDPR** Art. 5.1.c (minimización) → PII Shield; Art. 33 (notificación de brecha) → motivación directa del incidente.
- **EU AI Act** Art. 9 (gestión de riesgos) e Art. 15 (robustez).
- **DORA** Art. 9 → Output Auditor.
