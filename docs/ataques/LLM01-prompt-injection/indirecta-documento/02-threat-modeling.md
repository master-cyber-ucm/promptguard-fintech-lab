# 02 — Threat Modeling

> **Ataque #7** — Prompt Injection Indirecta — Documento
> Análisis PRE-implementación. Las contramedidas (Input Sanitizer sobre texto extraído) se mencionan como defensa futura, no implementada.

---

## 1. Actor de amenaza

**Perfil:** cliente bancario fraudulento con **mínimo conocimiento de ofimática**.

- Sin conocimientos de ML ni de prompt engineering avanzado.
- Capaz de editar un PDF con cualquier visor/editor (Inkscape, LibreOffice, reportlab).
- **No** requiere credenciales ajenas ni acceso interno al backend.
- Motivación: fraude financiero directo, suplantación de solvencia, o disrupción reputacional del banco.

## 2. Pre-requisitos

| Requisito | Estado en el lab |
|-----------|------------------|
| Canal de subida de documentos habilitado en Clara | **Pendiente de implementar** (Ext. 2) |
| Pipeline que extrae texto del PDF y lo inyecta en el contexto del LLM | **Pendiente de implementar** |
| Sesión de cliente autenticada | Disponible (`usr_001` en `MOCK_USERS`) |
| LLM en modo vulnerable, sin defensa sobre texto extraído | Disponible en `chat.py` |

> El ataque no es ejecutable hoy; se documenta como análisis previo al desarrollo del canal documental.

## 3. Vector y complejidad

- **Vector de acceso:** Network — el cliente sube el documento vía web/app.
- **Complejidad del ataque:** Baja — generar texto blanco sobre blanco es una operación trivial en cualquier editor PDF.
- **Interacción del usuario objetivo:** Ninguna — el propio atacante ejecuta la subida.
- **Privilegios requeridos:** Bajos — cuenta de cliente autenticada.

## 4. Explotabilidad

| Factor | Valoración |
|--------|-----------|
| Conocimientos técnicos del atacante | Muy bajos |
| Herramientas necesarias | Estándar (editor PDF / `reportlab`) |
| Trazabilidad visual para un revisor humano | Nula — el payload no es visible en el chat |
| Probabilidad de detección por inspección del documento | Baja — depende de revisión forense del PDF |
| Dependencia de fallos adicionales | Ninguna; el LLM por defecto sigue instrucciones del contexto |

## 5. Impacto

| Dimensión | Impacto | Justificación |
|-----------|---------|---------------|
| **Financiero** | Alto | Puede desencadenar `transferencia_nacional` (`tools.py:71`) sin autorización del titular. |
| **Regulatorio** | Alto | Fuga de PII de terceros activa GDPR Art. 33/34 (notificación a AEPD). |
| **Reputacional** | Alto | Fraude ejecutado desde el propio asistente del banco erosiona confianza. |
| **Operacional** | Medio | Requiere investigación forense de cada PDF sospechoso subido. |
| **Disponibilidad** | Bajo | El ataque no busca denegación de servicio. |

## 6. CVSS 3.1 — vector orientativo

```
CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:L
```

| Métrica | Valor | Justificación |
|---------|-------|---------------|
| Attack Vector | Network | Subida vía web/app. |
| Attack Complexity | Low | Texto oculto en PDF es trivial de producir. |
| Privileges Required | Low | Cliente autenticado. |
| User Interaction | None | El atacante ejecuta la subida. |
| Scope | Changed | El impacto rebasa el componente vulnerable (LLM) y alcanza herramientas bancarias y datos de terceros. |
| Confidentiality | High | Fuga posible de saldo/PII de cuentas ajenas. |
| Integrity | High | Transferencias / bloqueos ejecutables sin consentimiento. |
| Availability | Low | No es objetivo del ataque. |

**Puntuación base: 9.1 — Crítica.**

## 7. Supuestos y limitaciones del análisis

- El score asume que el canal de subida de documentos está habilitado (no es el caso actual del lab).
- No se contempla nochains detools adicionales; el impacto se deriva de las 5 tools actuales de Clara.
- La puntuación es orientativa: el TFM no incluye auditoría formal CVSS del entorno productivo.
