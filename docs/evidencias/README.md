# Evidencias experimentales entregadas

El [anexo comprimido](evidencias-historicas.zip) contiene **455 archivos**
recuperados del commit `33917d5a4470516591be49409b83a5f7c40c7e39`. Conserva resultados, Session Files,
capturas, documentos de análisis y scripts de los experimentos originales. El
[manifiesto](manifest.json) enumera cada archivo, su tamaño y SHA-256, además del
hash del ZIP. Los contenidos archivados no se han modificado.

## Cómo leer el anexo

| Ruta dentro del ZIP | Contenido |
|---|---|
| `henri-tfm/01-ataque/evidencia/` | Inyección documental, resultados agregados, ablaciones, trazas y capturas |
| `henri-tfm/02-defensa/` | Análisis de las defensas documentales |
| `daniel-tfm/02-defensa/evidencia/` | Evidencia de fugas y controles, con respuestas y resultados |
| `daniel-tfm/01-vectores/` | Investigación inicial y reproducción de ataques |
| `odile-tfm/evidencias/` | Sesiones de inyección directa y controles legítimos |
| `odile-tfm/STATS_ANALYSIS.csv` | Análisis estadístico original de esa investigación |
| `Red Team_/` | Experimentos previos de red-team y sus resultados |
| `lab/redteam-agent/` | Hallazgos y ejercicios de campañas históricas |

Se mantienen los nombres originales dentro del archivo para preservar las citas y
la atribución de las contribuciones. Son experimentos de etapas anteriores: sus
comandos, endpoints, interpretaciones y conclusiones deben leerse con la fecha y
el código de su medición, no como instrucciones de uso de la versión entregada.
Una cifra incluida en un documento original no supone una nueva validación por la
limpieza de entrega. Algunas referencias originales apuntaban a archivos locales
no versionados; el manifiesto delimita exactamente qué evidencia se entrega.

Para inspeccionarlo desde la raíz del repositorio, sin sobrescribir el laboratorio:

```bash
python3 -m zipfile -l docs/evidencias/evidencias-historicas.zip
python3 -m zipfile -e docs/evidencias/evidencias-historicas.zip /tmp/promptguard-evidencias
```

Para verificar ZIP, hashes y recursos necesarios para la entrega:

```bash
python3 lab/scripts/check_delivery.py
```

## Reproducir con la versión actual

Los documentos operativos están en [lab/payloads](../../lab/payloads/README.md).
El protocolo vigente es [DEMO_FULL_SUITE.md](../../DEMO_FULL_SUITE.md). El Run Report define la interpretación de los resultados de cada ejecución.

Las ejecuciones nuevas se guardan en `lab/audit/`, que está fuera de Git. Para citar
una corrida nueva en la memoria se debe adjuntar su Run Folder completo, con
procedencia, configuración, plan, resultados y Session Files. El anexo histórico
no se presenta como una campaña final realizada sobre el commit de entrega.
