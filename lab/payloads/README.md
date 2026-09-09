# Documentos de prueba

Recursos sintéticos necesarios para las fixtures `document-upload`: nóminas,
extractos, reclamaciones y hojas de gastos, con versiones sanas y comprometidas.
El runner busca aquí por defecto tanto en el host como en el montaje `/app/payloads`
de Docker. `PAYLOADS_DIR` permite indicar un directorio alternativo.

Los binarios se entregan versionados; no hay que generarlos para ejecutar la suite.
Los scripts de generación y ofuscación acompañan a los archivos para poder estudiar
las técnicas. Se conservaron los bytes originales de los documentos de investigación.

Desde la raíz del repositorio, para comprobar los generadores en un entorno Python:

```bash
python3 -m pip install -r lab/payloads/requirements.txt
python3 -m pytest lab/payloads/test_payloads.py -q
```

Los tests generan sus documentos en directorios temporales. Para regenerar recursos
manualmente, trabajar desde esta carpeta y consultar la ayuda o el bloque principal
del generador correspondiente; puede sobrescribir los archivos de su directorio.
La evidencia original se conserva en el [anexo histórico](../../docs/evidencias/README.md).
