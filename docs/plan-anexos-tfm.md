# Cierre de los anexos del TFM — plan y estado

Documento vivo. Recoge el plan por fases acordado el 13 de septiembre de 2026 y su estado de
ejecución. Las casillas sin marcar son el trabajo que queda.

- **Documento:** TFM Grupo 2 (Google Docs).
- **Reportes de partida:** 01 números y métricas, 02 contenido técnico, 03 revisión académica,
  04 narrativa y alcance. 109 recomendaciones en total.
- **Rama de trabajo del repo:** `docs/tfm-correcciones`, para un único PR al final.

---

## 1. Estado por fases

| Fase | Contenido | Estado |
|---|---|---|
| 0 | Marco de referencia MITRE ATLAS | **Cerrada** |
| 1 | Anexo A: catálogo y criterios | **Cerrada** |
| 2 | Anexo A.6: matriz ATLAS | **Cerrada**, con dos ajustes pendientes |
| 3 | Anexo B: denominadores y etiquetas | Bloqueada por decisión del equipo |
| 4 | Anexos C y D: reproducción y evidencia | Diagnosticada, sin aplicar |
| 5 | Anexo E y aportaciones individuales | Sin empezar |
| 6 | Cierre editorial | Sin empezar |

## 2. Decisiones abiertas del equipo

Las tres bloquean trabajo. Conviene resolverlas antes de seguir.

1. **Fase 3.** Estrategia con las cifras del Anexo B: recalcular desde los artefactos del Run
   Folder (lo que piden los reportes 01 y 03) o conservarlas y acotar lo que afirman (lo que pide
   el reporte 04). Son incompatibles y cuestan muy distinto. Afecta a las diez tablas de B.
2. **Fase 4.** Qué hacer con `docs/adr` (18 registros de decisión de arquitectura) y `docs/reports`
   (63 archivos), que existen en la rama `doc-tfm` pero no en `main`. O se traen a `main` y el
   Anexo D pasa a ser cierto, o se borran las entradas D.5 y D.6.
3. **Transversal.** Si PII Harvesting (ataque 6 del catálogo) recibe una tabla propia en el
   Anexo B. Tiene nueve fixtures y 246 ejecuciones en el Run Folder de referencia, pero la memoria
   no muestra sus resultados en ningún sitio. Depende de la decisión 1.

---

## 3. Paso a paso de lo que queda

### Bloque A · Cierre inmediato (10 minutos)

Consecuencia de que el apartado 5.5 ya tenga contenido. Su texto declara que sus variantes «no son
vectores independientes», sino el mismo ataque 2 entregado por otro mecanismo, de modo que dos
afirmaciones escritas antes han dejado de ser ciertas.

- [ ] **A.2**, última frase del párrafo posterior a la tabla. Sustituir la que empieza «La condición
      de la Extensión 1 se cumplió…» por: *«Ninguna de las cuatro se abordó en esta entrega: las
      quince técnicas que agrupan quedan como trabajo futuro en el apartado 8.»*
- [ ] **A.6**, fila de `AML.T0054`. La columna «Vector del proyecto» pasa de `10 Jailbreak
      (Extensión 1)` a `Variante de rol-play del ataque 2`.
- [ ] **A.6**, fila de `AML.T0015`. Borrarla entera. La variante Base64 no produjo evidencia en
      ninguna de las dos configuraciones, así que no procede atribuirle un módulo que la interrumpa.

### Bloque B · Fase 4, anexos C y D

**B.1. Anexo C — separar lo vigente de lo histórico**

Nueve comandos apuntan hoy a archivos que no están en el repositorio. Viven en
`evidencias-historicas.zip` y en la rama `doc-tfm`.

- [ ] Dividir el Anexo C en dos bloques declarados: *procedimientos vigentes* (ejecutables contra
      `main`) y *procedimientos históricos* (que operan sobre el contenido del ZIP).
- [ ] Mover al bloque histórico los cinco comandos de `henri-tfm/01-ataque/payloads/…` (C.4) y
      `henri-tfm/02-defensa/benchmark_structural_detector.py` (C.6).
- [ ] Mover al bloque histórico `attack_loop.py`, `ver_respuestas.py` y `run_redteam.py` (C.6), y
      añadir el agente vigente: `lab/redteam-agent/`, ejecutable con `python cli.py`.
- [ ] Completar C.2 con el procedimiento entero. Ejecutar la suite no genera el informe: hacen
      falta `make evaluate` y `make report` después, y `make check-suite` para reconciliar la
      cobertura. Sin esos pasos no se llega a ninguna cifra de la memoria.
- [ ] Sustituir `pytest tests/ -q` por `make test`, que es el target real del Makefile, y fechar o
      retirar el recuento 59/59.

**B.2. Anexo D — que cada ruta lleve a donde dice**

Cuatro de sus siete entradas remiten fuera de la entrega.

- [ ] **D.2.** `lab/audit/runs` está excluido por `.gitignore`, así que no viaja. Sustituirlo por
      `log-examples/runs/20260907_193559_qwen2.5-3b/`, que es la copia versionada de esa campaña.
- [ ] **D.4.** Retirar. Los directorios `03-normativa` no están versionados; solo hay dos archivos
      sueltos dentro del ZIP.
- [ ] **D.5 y D.6.** Según la decisión 2: traer `docs/adr` y `docs/reports` a `main`, o borrarlas.
- [ ] **D.7.** Retirar. Los directorios `bitacora` no están ni en el repositorio ni en el ZIP.
- [ ] Añadir las tres fuentes que sí viajan y hoy no se citan: `log-examples/` con sus tres logs de
      fase, `docs/evidencias/evidencias-historicas.zip` con sus 455 archivos, y
      `docs/evidencias/manifest.json` con los SHA-256.
- [ ] Pasada final cuando Norma suba su evidencia al repositorio.

### Bloque C · Fase 5, Anexo E y aportaciones

- [ ] **E.1.** Retirar la atribución causal. El texto explica la estabilización del modelo por su
      mayor tamaño, pero no se repitió la línea base con el modelo final, así que la mejora no es
      atribuible. Conservar versión anterior, versión nueva y condiciones; quitar la inferencia.
- [ ] **E.3.** Revisar «configuración por defecto inválida del modelo juez». La campaña de
      referencia declara `qwen3.5:9b` como juez y conserva su configuración, de modo que llamarlo
      inválido contradice la procedencia del run. Conservar la incidencia solo si se adjunta el log.
- [ ] **E.5.** Revisar su frase final («lo que sí generaliza es la eficacia de las mitigaciones»),
      que reintroduce el absoluto que el resto del apartado retira.
- [ ] Convertir el apartado 8.6 en una tabla de contribuciones dentro del anexo, con una fila por
      integrante. Hoy lleva el título «Aportaciones individuales (en sugerencia de Norma)» y
      contiene un solo bloque: es una nota de redacción visible en el documento final.

### Bloque D · Fase 3, Anexo B (bloqueada)

Diez tablas a sanear, por orden de gravedad. No empezar hasta resolver la decisión 1, y aplicar la
misma estrategia a las diez.

- [ ] B.5. Sustituir el semáforo verde/amarillo de cumplimiento por columnas de evidencia técnica y
      alcance de la conclusión.
- [ ] B.8.a a B.8.c. Reformular las tablas normativas como aportación técnica y límite.
- [ ] B.2.a. Retirar la columna «Tasa final» con 100 % derivada de secuencias fallo-éxito.
- [ ] B.3.a y B.3.b. Separar en dos columnas la evidencia de acceso y la etiqueta del evaluador.
- [ ] B.1.a, B.4.a y B.4.b. Rotular como resultados históricos con su fecha y su denominador.
- [ ] B.6.a. Identificar campaña, objetivo y postura de cada variante.
- [ ] B.7.a. Separar las latencias por recorrido.
- [ ] B.7.b. Completar desde una corrida limpia o retirar la fila y declararlo limitación.
- [ ] B.9 (nueva), si se decide dar tabla propia a PII Harvesting.

### Bloque E · Fase 6, cierre editorial

- [ ] Sustituir la tabla de contenidos. La actual sigue siendo el guion del borrador, con
      estimaciones de páginas, viñetas por persona, «5.6. Daniel — Ataque restante» y un
      «10.1 Fotografías» que ya no existe.
- [ ] Corregir la numeración duplicada del capítulo 3: hay dos apartados «3.5», Criterio de éxito y
      Trazabilidad.
- [ ] Retirar «Ataque N» de los cinco títulos del capítulo 5. Es una numeración interna de reparto
      que no coincide con la del catálogo y que contradice al propio §5.3.1.
- [ ] Poner nombre de integrante al apartado 5.6, que es el único sin él.
- [ ] Poner pie a las cuatro imágenes embebidas, que hoy no tienen ninguno, indicando campaña,
      fixture, postura y enlace al Session File.
- [ ] Comprobar que el cuerpo no supera las 20 caras y que la bibliografía cabe en media.

### Bloque F · Verificación final

- [ ] Buscar `[pendiente]`, `[AÑADIR`, `[Nombre` y corchetes sueltos. Deben dar cero.
- [ ] Comprobar que toda remisión interna resuelve a un apartado existente.
- [ ] Comprobar que ninguna afirmación del cuerpo es más fuerte que la del anexo que la respalda.
- [ ] Abrir el PR único desde `docs/tfm-correcciones`.

---

## 4. Registro de lo ya cerrado

**Fase 0.** Identificadores MITRE ATLAS verificados contra el catálogo oficial 2026.08. Corregidos
cuatro errores en el documento (`AML.T0055` usado para fuga de prompt, que es Unsecured Credentials;
`AML.T0024` para Cross-Context; `TA0043` como táctica, que es un identificador de ATT&CK; y una
entrada de bibliografía que mezclaba tres técnicas) y cinco en `docs/anexo-catalogo-ataques-llm.md`,
tres de ellos códigos inexistentes. Bibliografía saneada y versión del catálogo declarada.

**Fase 1.** Anexo A pasa de cinco frases descriptivas a seis subapartados con contenido. Las
condiciones de activación de las cuatro extensiones se recuperaron de
`docs/propuesta-formal-promptguard-fintech.md`. Actualizadas las tres remisiones del cuerpo, ahora
apuntando al subapartado exacto.

**Fase 2.** Anexo A.6, matriz ATLAS recortada a las cuatro tácticas implicadas, con la columna que
identifica qué módulo de PromptGuard interrumpe cada técnica.

**Transversal.** Resuelto el desajuste entre los siete ataques declarados y los seis con estudio
individual, y retirado el término «campaña integrada», que provenía de los reportes de revisión y no
del vocabulario de la memoria.
