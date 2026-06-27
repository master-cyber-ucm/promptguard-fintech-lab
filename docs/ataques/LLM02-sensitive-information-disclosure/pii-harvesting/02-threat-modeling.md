# Threat Modeling — PII Harvesting vía Contexto

## Actor de amenaza

| Atributo | Valor |
|----------|-------|
| Perfil | Cliente bancario fraudulento / curioso, **paciente** |
| Motivación | Fraude financiero posterior, doxxing, venta de datos en mercados clandestinos |
| Habilidad | Baja-media: no requiere exploits, sí ingeniería conversacional sostenida |
| Recursos | Una sesión autenticada + tiempo (10-30 turnos) |

A diferencia del actor impulsivo del Cross-Context #3, este actor **invierte turnos** para construir confianza y referencia acumulada.

## Pre-requisitos

- [x] Sesión autenticada válida en Clara (`user_id` de cualquier `role`).
- [x] Las tools bancarias exponen `owner` y `balance` en su respuesta (`lab/backend/src/agents/tools.py:61-68`).
- [x] `MOCK_ACCOUNTS` accesible al contexto del agente sin redacción (`lab/backend/src/models/banking.py:72-101`).
- [ ] Ausencia de PII Shield en el escenario pre-PromptGuard (estado vulnerable por defecto).

## Superficie expuesta (datos mock)

4 cuentas en `lab/backend/src/models/banking.py:72-101`:

| Titular | IBAN | Saldo (EUR) |
|---------|------|-------------|
| María García López | ES91…1332 | 15.420,50 |
| Carlos Rodríguez Martín | ES76…1333 | 8.750,25 |
| Ana Fernández Ruiz | ES34…1334 | 231.500,00 |
| Admin Banco | ES58…1335 | 999.999,99 |

`_get_account` en `lab/backend/src/agents/tools.py:27-29` **no verifica propiedad**: cualquier sesión autenticada puede leer cualquier cuenta, y el LLM consolida la PII en su contexto.

## Explotabilidad

- **Probabilidad de éxito (modo vulnerable):** Alta.
- **Esfuerzo del atacante:** Media (requiere paciencia multi-turno y pretexto creíble).
- **Detectabilidad sin defensa:** Baja. Las peticiones individuales parecen consultas legítimas.
- **Rating combinado:** **Media-Alta**.

## Impacto

| Dimensión | Detalle |
|-----------|---------|
| Confidencialidad | Alta — IBAN + saldo + nombre de múltiples titulares |
| Integridad | Nula en este ataque (no altera datos) |
| Disponibilidad | Nula |
| Escala | Crece con el número de turnos: 4 cuentas en lab, ~900.000 clientes en VerdaBank en producción |

## Consecuencias normativas

- **GDPR Art. 5.1.c** — violación del principio de minimización: el contexto retiene más PII de la estrictamente necesaria.
- **GDPR Art. 33** — si la cosecha escala a muchos titulares, obligación de notificar a la AEPD en **72 h**.
- **GDPR Art. 34** — riesgo alto para los derechos de los afectados puede activar comunicación al interesado.

## Score CVSS 3.1 orientativo

```
CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:N/A:N
```

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Vector de Acceso | Red (AV:N) | Clara es accesible vía web/app |
| Complejidad | Baja (AC:L) | Ingeniería conversacional, no exploit técnico |
| Privilegios | Bajos (PR:L) | Cualquier cliente autenticado |
| Interacción usuario | Ninguna (UI:N) | Atacante = operador |
| **Scope** | **Cambiado (S:C)** | La PII extraída pertenece a otros titulares → el impacto salta del componente comprometido |
| Confidencialidad | Alta (C:H) | Datos financieros sensibles |
| Integridad / Disponibilidad | Nula | No altera ni interrumpe |

**Base Score: 8.6 (Alto) · Severidad: HIGH.**

> La métrica *S:C* refleja que la cosecha afecta a titulares distintos del que opera la sesión, criterio coherente con la calificación del incidente motivador INC-2025-0089 (`docs/propuesta-formal-promptguard-fintech.md:44-46`).

## Estado del análisis

- [x] Actor y motivación definidos
- [x] Pre-requisitos trazados al código mock
- [x] Explotabilidad e impacto cuantificados
- [x] CVSS 3.1 orientativo calculado
- [ ] Validación empírica con datos de ejecución del lab
