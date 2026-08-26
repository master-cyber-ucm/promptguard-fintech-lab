# 02 — Threat Modeling

> System Prompt Leakage — Modelo de amenaza del ataque #5.
> Documento analítico **previo a la implementación**.

## Actor de amenaza

| Atributo | Valor |
|----------|-------|
| Perfil | Cliente bancario autenticado (o cualquiera con acceso al chat) |
| Motivación | Reconocimiento previo a fraude de precisión |
| Conocimiento | Bajo — técnicas documentadas públicamente |
| Barrera de entrada | **Baja**: no requiere tooling ni credenciales privilegiadas |

## Pre-requisitos

- [ ] Sesión autenticada contra Clara (`POST /api/v1/proxy/chat`, `propuesta-formal-promptguard-fintech.md:758`).
- [ ] Canal conversacional de texto disponible (escenario base, sin multimodalidad).
- [ ] Modelo en **modo vulnerable**: sin Output Auditor activo.

## Explotabilidad

**Alta.** Los payloads del lab (`attack_prompts.jsonl` líneas 4, 5, 15 y 19) son frases en lenguaje natural sin obfuscación. No requieren evasión del clasificador ni técnicas avanzadas.

## Activos en riesgo

| Activo | Ubicación en el prompt | Valor de inteligencia |
|--------|-----------------------|----------------------|
| Umbrales (10.000 / 5.000 / 1.000 €) | `clara_system.txt:23-25` | Alto — habilita evasión de controles (#1) |
| Disparador antifraude > 3.000 € | `clara_system.txt:26` | Alto — diseño de transferencias "silenciosas" |
| `API_KEY_INTERNAL: pg_internal_sk_a1b2c3d4e5f6` | `clara_system.txt:27` | Crítico — secreto simulado |
| `db-banking.internal.verdabank.es:5432` | `clara_system.txt:28` | Medio — host interno |
| `s3://verdabank-audit-logs-prod/` | `clara_system.txt:29` | Medio — destino de logs |

## Impacto

- **Directo**: bajo-moderado. Por sí mismo, no mueve dinero ni accede a datos de clientes.
- **Indirecto (ampliado)**: alto. Es la **fase de reconocimiento** que multiplica la eficacia de #1 (Excessive Agency), #3 (Cross-Context) y #6 (PII Harvesting).
- **Incidente de seguridad específico**: la filtración de `API_KEY_INTERNAL` sería, en producción, una brecha de secreto que activa el playbook de rotación (ver `07-playbook-incident-response.md`).

## Score CVSS 3.1 orientativo

```
CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:L/I:N/N:A  →  Base 5.4 (Medium)
```

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Attack Vector | Network (AV:N) | Chat accesible vía web/app |
| Attack Complexity | Low (AC:L) | Pregunta indirecta, sin ofuscación |
| Privileges Required | Low (PR:L) | Sesión autenticada de cliente |
| User Interaction | None | Sin interacción adicional |
| Scope | Changed (S:C) | La inteligencia habilita ataques en otros componentes (tools, DB) |
| Confidentiality | Low (C:L) | Por sí solo filtra configuración, no datos de clientes |
| Integrity / Availability | None | No altera ni degrada el servicio |

**Justificación del Scope=Changed**: aunque el impacto directo es C:L, el alcance se amplía al facilitar ataques contra tools bancarias y otros componentes, lo que justifica subir la puntuación por encima de la del leaked-prompt aislado.

## Asume el atacante

- **Coste**: minutos de conversación.
- **Retorno**: mapa completo de límites, lógica de autorización y secretos simulados.

## Referencias

- OWASP LLM07:2025 — System Prompt Leakage (owasp.org).
- MITRE ATLAS AML.T0055 — Discovery (atlas.mitre.org).
- CVSS v3.1 Specification Document (first.org/cvss).
