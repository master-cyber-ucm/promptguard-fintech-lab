# Roadmap — Ataque #7: Prompt Injection Indirecta vía Documento

> Checklist de trabajo. Marcar `[x]` según se completa. Cada tarea que produzca evidencia debe
> anotarse también en `bitacora/BITACORA.md` con fecha y forma de reproducirla (ver regla 2 de
> `00-INSTRUCCIONES.md`).

## Fase 0 — Setup

- [x] Explorar el repo y entender el objetivo del TFM (PromptGuard FinTech).
- [x] Leer los 7 capítulos de referencia en `docs/ataques/LLM01-prompt-injection/indirecta-documento/`.
- [x] Crear el entorno de trabajo personal (`henri-tfm/` en la raíz del repo).
- [x] Verificar que el lab arranca en local: `cd lab && make run` (Ollama + backend + frontend).
- [x] Correr `make smoke` y confirmar health check del backend y del proveedor LLM.

## Fase 1 — Ataque

### 1.1 Diseño del payload

- [ ] Decidir formatos de documento a atacar: **PDF obligatorio** (hay base en
      `lab/gen_adversarial_pdf.py`); valorar si se amplía a DOCX/XLSX o se deja como trabajo
      futuro.
- [ ] Diseñar el payload bancario específico (adaptar el ejemplo de RRHH de
      `gen_adversarial_pdf.py` a un objetivo bancario: filtrar saldo/IBAN de un tercero, o forzar
      `transferencia_nacional` / `bloquear_tarjeta`), coherente con lo ya definido en los fixtures
      `atk_021`/`atk_022`.
- [ ] Generar el documento **sano** (nómina/extracto legítimo, sin payload) como control negativo.
- [ ] Generar el documento **comprometido** con al menos dos técnicas de ocultación (texto blanco
      sobre blanco, fuente 1pt, texto fuera de viewport, o metadatos).
- [ ] Especificar por escrito (en `01-ataque/README.md`) qué hace cada técnica y por qué se espera
      que funcione — esto es la "especificación" que exige la regla de trabajo.

### 1.2 Canal de subida de documentos (falta implementarlo)

- [ ] Decidir el approach: ¿nuevo endpoint (`/chat/complex-with-document` siguiendo la progresión
      ya existente en `chat.py`) o campo opcional de archivo en `ChatRequest`?
- [ ] Implementar la extracción de texto del PDF (p. ej. `pypdf`/`pdfplumber`) y su concatenación
      al contexto del LLM, **sin sanitizar** (modo vulnerable — así se demuestra el ataque).
- [ ] (Opcional, según tiempo) soporte DOCX/XLSX si se decide ampliar el alcance.
- [ ] Escribir un test/fixture que cubra el nuevo endpoint (aunque sea mínimo) antes de darlo por
      cerrado.

### 1.3 Ejecución y evidencia

- [ ] Levantar el lab en modo vulnerable (`make run`).
- [ ] Ejecutar el flujo con el documento **sano** → confirmar que el payload NO se ejecuta
      (control negativo).
- [ ] Ejecutar el flujo con el documento **comprometido** → confirmar que SÍ se ejecuta (tool call
      no autorizado o fuga de datos de un tercero).
- [ ] Capturar evidencia: Session File (`lab/audit/sessions/`), Run Report si se integra en la
      suite (`lab/audit/runs/`), captura de pantalla del playground.
- [ ] Documentar el comando/procedimiento exacto para reproducir ambos casos.

### 1.4 Capítulo de ataque

- [ ] Redactar el borrador de resultados (basado en los capítulos de referencia, con evidencia
      real reemplazando las notas "PRE-implementación").
- [ ] Redactar el aporte a la sección **4.2** del índice del TFM (vector evaluado) y a **6.1**
      (parcial — resultados de ataque, antes de la defensa).
- [ ] Revisar que se citan MITRE ATLAS (`AML.T0051.001`) y OWASP (`LLM01:2025`) correctamente.

## Fase 2 — Defensa

### 2.1 Brainstorm de medidas candidatas

- [ ] Lluvia de ideas — como mínimo evaluar: sanitización del texto extraído (mismo pipeline que
      el Input Sanitizer del escenario base), detección de patrones ocultos estilo antivirus
      (heurísticas tipo "texto del mismo color que el fondo", "fuente <2pt", firmas conocidas),
      separación semántica explícita dato/instrucción en el prompt, límites/normalización de
      metadatos del PDF, conversión forzada a texto plano (elimina capas/color/tamaño antes de
      llegar al LLM).
- [ ] Documentar cada candidato en `02-defensa/README.md`: qué hace, por qué podría funcionar,
      coste de implementación, falsos positivos esperados.

### 2.2 Selección e implementación

- [ ] Elegir la(s) medida(s) a implementar, con justificación escrita.
- [ ] Implementar en el backend (extensión del Input Sanitizer u otro módulo nuevo).
- [ ] Escribir test(s) de regresión para la defensa.

### 2.3 Validación

- [ ] Repetir el ataque con el documento **comprometido** y la defensa activa → evidencia de
      bloqueo.
- [ ] Repetir con el documento **sano** y la defensa activa → confirmar que NO hay falso positivo.
- [ ] Capturar evidencia (mismo formato que en 1.3).

### 2.4 Capítulo de defensa

- [ ] Redactar el aporte a **4.1** (arquitectura general — cómo encaja este módulo) y a **6.1/6.2**
      (resultados después de la defensa, análisis y discusión).
- [ ] Actualizar el checklist de estado en `docs/ataques/.../README.md` (si se decide tocar el
      material de referencia en esta etapa — a confirmar con el resto del equipo).

## Fase 3 — Marco normativo

- [ ] Verificar contra fuentes oficiales (EUR-Lex) el borrador ya existente en
      `05-cumplimiento-normativo.md` (GDPR Art. 5.1.c/32/33/34, DORA Art. 9/10, AI Act Art. 9/15).
- [ ] Investigar si aplica EBA guidelines / PSD2 a este vector concreto.
- [ ] Ampliar NIST AI RMF (ya esbozado en `01-mapeo-taxonomico.md`) e investigar ISO 27001 si
      aplica.
- [ ] Estimar impacto/multas potenciales para el escenario VerdaBank (orden de magnitud,
      justificado).
- [ ] Redactar el aporte a la sección **7** del índice del TFM (Marco normativo y cumplimiento).

## Fase 4 — Consolidación

- [ ] Ensamblar el capítulo individual completo siguiendo el índice oficial del TFM.
- [ ] Revisar trazabilidad/reproducibilidad de principio a fin (cada afirmación con su evidencia
      y su comando de reproducción).
- [ ] Checklist final de entregable — nada pendiente sin marcar o justificado como trabajo futuro.
