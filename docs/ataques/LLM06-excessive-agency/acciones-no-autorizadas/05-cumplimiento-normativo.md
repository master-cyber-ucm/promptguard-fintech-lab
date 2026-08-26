# 05 — Cumplimiento Normativo

> Mapeo **estricto** a los artículos permitidos. Sin invocar normativa fuera de la lista autorizada.

## GDPR (Reglamento 2016/679)

| Artículo | Requisito | Incumplimiento que provoca el ataque |
|----------|-----------|--------------------------------------|
| **Art. 5.1.c** — Minimización | Tratar solo los datos adecuados, pertinentes y limitados. | La tool recibe IBANs ajenos y opera sobre ellos sin necesidad. |
| **Art. 32** — Seguridad del tratamiento | Medidas técnicas y organizativas apropiadas al riesgo. | Ausencia de validación determinista en `transferencia_nacional` (`tools.py:71`) y `bloquear_tarjeta` (`tools.py:118`). |
| **Art. 33** — Notificación a la autoridad | Comunicar la brecha a la AEPD en **72 h**. | Pérdida financiera derivada de agency excesiva activa el deber de notificación. |
| **Art. 34** — Comunicación al interesado | Notificar al titular si hay riesgo alto. | El titular debe ser informado de la transferencia/bloqueo no autorizado. |

## DORA (Reglamento UE 2022/2554)

| Artículo | Requisito | Vínculo con el ataque |
|----------|-----------|-----------------------|
| **Art. 6** — Sistema de gestión del riesgo ICT. | El canal conversativo con tools irreversibles debe inventariarse como activo de alto riesgo. |
| **Art. 9** — Identificación y protección. | Falta de control de acceso sobre las tools → brecha de protección ICT. |
| **Art. 11** — Pruebas y respuesta. | El ataque demuestra ausencia de pruebas de seguridad sobre la lógica de autorización. |
| **Art. 17** — Incidente grave. | Pérdida financiera directa e irreversible = incidente grave ICT con obligación de reporte. |

## EU AI Act (Reglamento 2024/1689)

Clara es sistema de IA de **alto riesgo** (acceso a servicios financieros).

| Artículo | Requisito | Vínculo con el ataque |
|----------|-----------|-----------------------|
| **Art. 9** — Gestión de riesgos. | El Excessive Agency es un riesgo no mitigado en el ciclo de vida del sistema. |
| **Art. 14** — **Supervisión humana** *(CLAVE)*. | Operaciones críticas requieren **confirmación humana**. El ataque **omite por diseño** toda supervisión: la tool ejecuta sin aprobación. Es el incumplimiento nuclear. |
| **Art. 15** — Precisión, robustez y ciberseguridad. | La ausencia de validación determinista vulnera la robustez frente a manipulación conversacional. |

> **Art. 14 es el eje del análisis:** la esencia de Excessive Agency es *delegar en la máquina una decisión crítica que la normativa exige que tome un humano*. La defensa futura (Tool Gatekeeper + confirmación sobre umbral) materializa directamente el cumplimiento del Art. 14.

## Estado

- [x] GDPR Art. 5.1.c, 32, 33, 34 mapeados
- [x] DORA Art. 6, 9, 11, 17 mapeados
- [x] EU AI Act Art. 9, 14, 15 mapeados
- [x] Art. 14 destacado como núcleo del incumplimiento
- [ ] Revisión jurídica formal por Compliance (trabajo futuro)
