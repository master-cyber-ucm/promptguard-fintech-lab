# 05 — Cumplimiento Normativo

> Cross-Context Data Leakage (#3). Artículos aplicables **exactos** + plantilla de notificación AEPD.

## 1. GDPR (Reglamento UE 2016/679)

| Artículo | Requisito | Cómo se vulnera en este ataque |
|----------|-----------|-------------------------------|
| **Art. 5.1.c** — Minimización de datos | Tratar solo los datos adecuados, pertinentes y limitados a lo necesario. | El sistema expone a un cliente datos de **otros** titulares que no necesita para atenderle. |
| **Art. 32** — Seguridad del tratamiento | Medidas técnicas y organizativas apropiadas (control de acceso por identidad). | `consulta_saldo` no valida propiedad (`tools.py:44`): ausencia de control de acceso a nivel de tool. |
| **Art. 33** — Notificación a la autoridad | Comunicar la brecha a la AEPD en **≤72 h** desde la toma de conocimiento. | La fuga de saldo/IBAN de un tercero es brecha personal; **arranca el reloj legal de 72 h**. |
| **Art. 34** — Comunicación al interesado | Informar al afectado cuando exista alto riesgo para sus derechos. | El titular cuyo saldo se filtra debe ser notificado (dato financiero = alto riesgo). |

## 2. DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Aplicación |
|----------|-----------|-----------|
| **Art. 10** — Detección de incidentes | Capacidad de identificar anomalías e incidentes relacionados con las TIC. | La fuga debe detectarse y registrarse (hoy inexistente; futuro Output Auditor). |
| **Art. 17** — Notificación de incidentes graves | Reportar incidentes TIC graves a la autoridad competente. | Una brecha de datos de clientes por el canal conversacional puede ser incidente grave. |

## 3. EU AI Act (Reglamento UE 2024/1689)

| Artículo | Requisito | Aplicación |
|----------|-----------|-----------|
| **Art. 9** — Gestión de riesgos | Identificar, evaluar y mitigar riesgos conocidos y razonablemente previsibles. | Cross-context leakage es un riesgo previsible; debe figurar en el registro de riesgos de Clara. |
| **Art. 15** — Robustez y ciberseguridad | Medidas técnicas frente a ataques (manipulación, explotación de vulnerabilidades). | La falta de validación de propiedad en la tool es vulnerabilidad explotable (Art. 15 incumplido en el estado actual). |

## 4. Plantilla de notificación a la AEPD (GDPR Art. 33)

> Campos a rellenar por el DPO dentro de las 72 h siguientes a la toma de conocimiento.

```
NOTIFICACIÓN DE BRECHA DE DATOS PERSONALES — AEPD (GDPR Art. 33)

[A] Responsable del tratamiento:
    VerdaBank S.A. — CIF: ____  ·  DPO: ______________
[B] Referencia interna del incidente: INC-2025-0089
[C] Fecha y hora de la detección: ____ (fecha/hora, CET)
[D] Fecha y hora de la toma de conocimiento: ____ (inicia cómputo 72 h)
[E] Número estimado de afectados: ____ clientes
[F] Naturaleza de la brecha: Confidencialidad (acceso no autorizado vía chatbot)
[G] Naturaleza de los datos: DATOS FINANCIEROS — saldo e IBAN de cuenta(s) ajena(s)
[H] Categorías de afectados: clientes del banco (y, en su caso, administrador)
[I] Probables consecuencias: exposición patrimonial, fraude, suplantación
[J] Riesgo para los derechos y libertades de los interesados: ____ (ALTO/MEDIO)
[K] Medidas adoptadas o propuestas:
      - [ ] Contención del vector (deshabilitar/aislar tool o sesión)
      - [ ] Parche de validación de propiedad (account_id vs user_id)
      - [ ] Rotación de contexto / cierre de sesiones afectadas
      - [ ] Comunicación al interesado (GDPR Art. 34)
[L] Origen y causas: ausencia de control de acceso en tool consulta_saldo
[M] Destinatario de la notificación: Agencia Española de Protección de Datos (AEPD)
[N] Fecha límite de notificación: toma de conocimiento + 72 h (____)
```

## 5. Comunicación al interesado (Art. 34) — elementos mínimos

- Naturaleza de la brecha y datos concretos filtrados.
- Medidas adoptadas y recomendaciones (vigilancia de movimientos, cambio de credenciales).
- Punto de contacto del DPO para ejercer derechos (acceso, rectificación, oposición).
