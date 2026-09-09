# PR 11 — `make suite` exige árbol limpio por defecto

**Estado:** revertido (2026-09-02) — ver "Corrección posterior" al final
**Prioridad:** P1 — no bloquea análisis, sí bloquea que un run sea citable
**Origen:** análisis de `20260901_190305_qwen2.5-3b` (problema original #2 del backlog)
**Dependencias:** ninguna

## Pregunta de diseño (persistida antes de investigar)

> El run auditado corrió con árbol de trabajo sucio y el propio `run.md` lo
> advierte ("este run no puede agregarse con otros"), pero la corrida se ejecutó
> igual. ¿Falta construir un gate, o ya existe uno que nadie activó?

**Por qué importa:** un run que no puede agregarse ni citarse como comparación
causal, si de todas formas se ejecuta y se analiza, corre el riesgo real de
colarse en el capítulo experimental del TFM por inercia — es más fácil olvidar
pasar un flag opcional que recordar comprobarlo después.

**Dueño de la decisión:** ninguno externo — verificable en el propio Makefile.

**Criterio de aceptación:**
1. `make suite` sin argumentos adicionales debe abortar antes de enviar tráfico
   si el árbol está sucio.
2. Debe seguir siendo posible ejecutar una corrida exploratoria sobre un árbol
   sucio, explícitamente, sin editar el Makefile.
3. No se reescribe el gate en sí (ya existe, ya está probado) — solo se cambia
   si `make suite` lo pasa por defecto.

## Evidencia del caso

`scripts/run_attack_suite.py` ya implementa el gate completo desde PR5/ADR-0017:

```python
parser.add_argument(
    "--require-clean-tree", action="store_true",
    help=(
        "Gate previo de reproducibilidad (PR5 / ADR-0017): aborta antes de enviar "
        "tráfico si el árbol de trabajo está sucio. Sin este flag, un árbol sucio "
        "solo emite el aviso histórico y la corrida continúa — úsalo para runs "
        "exploratorios, pero nunca para una campaña baseline/full/ablaciones que "
        "vaya a publicarse como comparación causal."
    ),
)
...
if args.require_clean_tree:
    print("  ✗ --require-clean-tree: abortando antes de enviar tráfico ...")
    sys.exit(1)
```

Pero `Makefile:suite:` nunca lo pasa, y `run.sh` (el script que produjo
`suite-final.4.log`, fuera del repo, en la raíz de `software/`) tampoco:

```sh
log=audit/logs/suite-final.3.log; : > "$log"; make suite REPEAT=5 >>"$log" 2>&1; ...
```

El propio texto de ayuda ya dice "úsalo… pero nunca para una campaña
baseline/full/ablaciones que vaya a publicarse" — que es exactamente lo que
produjo `suite-final.4.log`. La política está escrita; no está aplicada.

## Alternativas consideradas

| Opción | Descripción | Veredicto |
|---|---|---|
| A. Documentar que hay que acordarse de pasar `--require-clean-tree` | No cambia nada — es la situación actual, y ya falló una vez. | Rechazada. |
| B. `make suite` pasa `--require-clean-tree` por defecto, con un override explícito | El caso común (campaña que se va a citar) queda protegido sin acción extra; el caso exploratorio sigue disponible con una variable nombrada. | **Elegida.** |
| C. Forzar el gate sin override (eliminar la opción de correr sucio) | Rompe el flujo de desarrollo normal: iterar sobre un fixture nuevo exige commitear cada prueba. | Rechazada: el propio texto de ayuda ya distingue explícitamente "runs exploratorios" de "campañas publicables" — ambos casos son legítimos. |

## Solución implementada

`Makefile`: nueva variable `REQUIRE_CLEAN_TREE ?= true` y
`CLEAN_TREE_FLAG = $(if $(filter true,$(REQUIRE_CLEAN_TREE)),--require-clean-tree,)`,
añadida a la recta de `suite:`. Comportamiento:

- `make suite` (sin nada más) → exige árbol limpio, aborta si está sucio.
- `make suite REQUIRE_CLEAN_TREE=false` → conserva el comportamiento anterior
  (aviso, sin abortar) para iteración exploratoria.

Se corrige además `make help`, que describía `make suite` como "Matriz principal
(sin documentos)" — desactualizado desde PR10, que activó el canal documental por
defecto.

## Corrección posterior (2026-09-02) — el gate se retira

Al usarlo en la práctica (`audit/logs/suite-final.5.log`, run
`20260902_200130_qwen2.5-3b`), el gate abortó un `make suite` real por 3 ficheros
sucios ajenos al código evaluado (un cambio cosmético en el propio `Makefile` y
dos ficheros sueltos fuera de `lab/`), sin enviar ninguna petición. El dueño del
proyecto decidió explícitamente que esta dependencia — que el comando que lanza
ataques dependa del estado de `git` del host — no tiene sentido para un
laboratorio de un único investigador iterando localmente: el coste (una suite de
horas abortada en el segundo 0 por un fichero de notas sin commitear) supera el
beneficio (poder citar un run como "reproducible" formalmente), que este TFM no
llegó a necesitar en la práctica.

Se retira:
- `Makefile`: `REQUIRE_CLEAN_TREE`/`CLEAN_TREE_FLAG` y su paso a `suite:`.
- `scripts/run_attack_suite.py`: el flag `--require-clean-tree` y el `sys.exit(1)`
  asociado.

Se conserva sin cambios (no es el gate, es información pasiva que no bloquea
nada): `provenance.py` sigue registrando `git.commit`/`git.dirty` en
`provenance.json` de cada run, y `run_attack_suite.py` sigue imprimiendo el aviso
"árbol de trabajo sucio: el commit no identifica el código que corre" si
corresponde — solo deja de poder abortar la ejecución.

Validado con la suite completa de tests tras el cambio: 903 passed, 0 failed (los
tests de `provenance.build()`/`git.dirty` en `test_reproducibilidad_e_incertidumbre.py`
y `test_resolucion_de_rutas.py` prueban la detección pasiva, no el flag retirado,
así que no requirieron cambios).

## Segunda corrección posterior (2026-09-06) — el gate se reintrodujo y se retira otra vez

El gate volvió (`6099c52`, "exigir árbol limpio antes de ejecutar", como respuesta a
una recomendación de auditoría) con el mismo mecanismo: `parser.error(...)` en
`run_attack_suite.py` si `git.dirty` y no se pasa `--allow-dirty`. Abortó de nuevo un
`make suite` real (`GIT_DIRTY_FILES=8` en ese momento) por el mismo motivo de fondo que
en la corrección anterior — no por un defecto de implementación, sino porque el dueño
del proyecto rechaza explícitamente que el comando de ataque dependa del estado de
`git` del host, ejecute como ejecute. Instrucción explícita: eliminar todo el control,
no solo relajarlo.

Se retira definitivamente:
- `scripts/run_attack_suite.py`: el flag `--allow-dirty` y el `parser.error(...)`
  asociado a `git.dirty`, además del aviso pasivo que se imprimía en consola
  ("árbol de trabajo sucio: el commit no identifica..." antes de abrir tráfico).
- `backend/tests/test_runner_prevuelo.py::test_el_runner_exige_excepcion_explicita_para_arbol_sucio`
  — verificaba la existencia del flag retirado.

Se conserva (no es un control, es un dato que no bloquea ni imprime advertencias):
`provenance.py` sigue registrando `git.commit`/`git.dirty` en `provenance.json`, y
`report.py` lo sigue mostrando como una fila más de la tabla "Procedencia del run".
Dado el historial de esta misma discusión (añadido → retirado → reintroducido →
retirado), cualquier futura recomendación de volver a bloquear la ejecución por estado
de git debería tratarse como ya rechazada por el dueño del proyecto, no como un hallazgo
nuevo a corregir.
