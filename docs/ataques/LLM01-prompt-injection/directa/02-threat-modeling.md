# Threat Modeling & Scoring — Prompt Injection Directa

> Ataque #2 del catálogo · Escenario: usr_001 → cuenta de usr_admin

---

## 1. Actor de amenaza

**Perfil principal:** cliente fraudulento / script kiddie.

- No requiere infraestructura, malware ni credenciales robadas.
- Conoce patrones de inyección por exposición pública (ejemplos en prensa, foros, repositorios de payloads).
- Motivación: curiosidad, fraude, o reventa de información financiera.

El catálogo del TFM define al actor como *"cliente bancario autenticado o cibercriminal externo"*. La inyección directa es el único ataque del catálogo que este actor puede ejecutar **sin escalado de privilegios ni herramientas adicionales**.

## 2. Pre-requisitos

| Requisito | Estado en el escenario |
|-----------|------------------------|
| Sesión autenticada en Clara | **Sí** — cualquier cliente con cuenta activa |
| Conocimiento del IBAN objetivo | Bajo — se infiere o se obtiene por ingeniería social previa |
| Herramientas especializadas | Ninguna |
| Acceso a la red interna | No |

## 3. Vector de acceso y complejidad

- **Vector:** canal conversacional público de Clara (web / app móvil).
- **Complejidad:** **barrera de entrada cero**. El payload `atk_001` es una frase en lenguaje natural copiable.
- **Superficie:** el endpoint `POST /api/v1/chat` (`lab/backend/src/api/routes/chat.py:45`), que pasa el mensaje sin filtro al LLM (`chat.py:65`).

## 4. Explotabilidad — **ALTA**

Justificación:

1. La ruta de entrada coincide con el uso legítimo del producto (enviar un mensaje a Clara).
2. No existe validación entre el input y el LLM en el modo vulnerable.
3. El system prompt incluye límites declarativos ("NO LAS VIOLES NUNCA", `clara_system.txt:14`) que son justamente el objetivo a derribar — un límite declarativo sin control técnico es trivial de sobrescribir.
4. El éxito o fracaso es observable inmediatamente por el atacante en la respuesta.

## 5. Impacto

| Dimensión | Descripción |
|-----------|-------------|
| **Financiero** | Si la inyección deriva en tool call (`consulta_saldo`, `transferencia_nacional`), acceso a saldos y posible fraude. Cuenta objetivo: 999.999,99 €. |
| **Regulatorio** | Lectura de saldo de un tercero = brecha de dato personal. Obligación GDPR Art. 33/34. |
| **Reputacional** | Publicación del incidente erosiona la confianza en un neobank cuya propuesta de valor es digital. |

## 6. Score CVSS 3.1 (orientativo)

```
CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:L/A:N
```

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| **Attack Vector (AV)** | Network (N) | Clara es accesible vía web/app desde Internet |
| **Attack Complexity (AC)** | Low (L) | Barrera de entrada cero: payload de lenguaje natural |
| **Privileges Required (PR)** | Low (L) | Cliente autenticado, sin rol privilegiado |
| **User Interaction (UI)** | None (N) | No requiere interacción de terceros |
| **Scope (S)** | Changed (C) | El impacto cruza de Clara al activo de otro usuario (usr_admin) |
| **Confidentiality (C)** | High (H) | Revela saldo/movimientos de cuenta ajena |
| **Integrity (I)** | Low (L) | El payload base es de lectura; la integridad se ve afectada si deriva en transferencia |
| **Availability (A)** | None (N) | No interrumpe el servicio |

**Puntuación base orientativa: ~8,5 (High).**

> Marcado como **orientativo**: CVSS no fue diseñado para ataques contra LLMs. El valor de Scope y Integrity depende del payload concreto que tenga éxito; este vector asume el caso de filtrado de saldo de la cuenta admin.
