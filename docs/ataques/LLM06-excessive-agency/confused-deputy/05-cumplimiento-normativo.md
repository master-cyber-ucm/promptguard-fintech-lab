# 5. Cumplimiento Normativo — Confused Deputy Attack

> Artículos citados estrictamente del conjunto permitido para el TFM.

## GDPR (Reglamento 2016/679)

| Artículo | Requisito | Cómo lo vulnera el ataque |
|---------|----------|---------------------------|
| **Art. 5.1.c** — Minimización de datos | Los datos personales solo pueden tratarse para fines determinados y limitados a lo necesario. | Clara expone saldo y movimientos de cuentas ajenas a un usuario sin legitimación, ampliando el tratamiento más allá del fin perseguido. |
| **Art. 32** — Seguridad del tratamiento | Medidas técnicas y organizativas apropiadas (pseudonimización, control de acceso). | Ausencia de control de autorización `user_id` ↔ `account_id` en las tools bancarias; cualquier sesión accede a cualquier cuenta. |
| **Art. 33** — Notificación a la autoridad | Notificar a la AEPD en 72 h tras conocer una brecha de dato personal. | La consulta/transferencia sobre cuenta ajena constituye brecha de confidencialidad/integridad notificable. |
| **Art. 34** — Comunicación al interesado | Informar al afectado cuando el riesgo sea alto. | El titular de la cuenta ajena debe ser comunicado por el alto riesgo financiero. |

## DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Cómo lo vulnera el ataque |
|---------|----------|---------------------------|
| **Art. 6** — Marco de gestión del riesgo ICT | Definir, aprobar, implementar y revisar un marco de gestión del riesgo digital. | Este vector debe estar inventariado y gestionado en el marco del banco. |
| **Art. 9** — Identificación y protección | Catalogar activos ICT y aplicar controles de acceso. | Las tools bancarias son activos ICT sin control de acceso efectivo por identidad. |
| **Art. 11** — Pruebas de seguridad | Realizar pruebas de resiliencia del marco ICT. | Los vectores `atk_010`/`atk_020` deben figurar como casos de prueba adversarial. |
| **Art. 17** — Notificación de incidentes | Reportar incidentes ICT graves a la autoridad competente. | Una transferencia fraudulenta desde cuenta ajena es incidente ICT grave reportable. |

## EU AI Act (Reglamento 2024/1689)

Clara es sistema de IA de **alto riesgo** (acceso a servicios financieros). Artículos directamente implicados:

| Artículo | Requisito | Cómo lo vulnera el ataque |
|---------|----------|---------------------------|
| **Art. 9** — Gestión de riesgos | Identificar y mitigar riesgos previsibles del sistema de IA. | El confused deputy es riesgo previsible que exige mitigación (control de autorización en tools). |
| **Art. 14** — Supervisión humana | Posibilidad de intervención humana en operaciones de alto riesgo. | `atk_020` ejecuta transferencia sin confirmación humana posible; ausencia de *human-in-the-loop*. |
| **Art. 15** — Robustez y ciberresiliencia | Resistencia a errores, fallos y ataques. | El pretexto verbal basta para inducir la tool sobre cuenta ajena; falta de robustez. |

## Síntesis de obligaciones de notificación

- **GDPR Art. 33/34:** notificación AEPD ≤72 h y comunicación al titular afectado.
- **DORA Art. 17:** reporte de incidente ICT grave según umbrales del regulador.
- **EU AI Act Art. 9/14/15:** registro del incidente en el sistema de gestión de riesgos del proveedor/desplegador y revisión de las medidas de supervisión humana.
