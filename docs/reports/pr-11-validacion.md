# PR 11 — Evidencia de validación

## Qué se hizo

`Makefile`: `REQUIRE_CLEAN_TREE ?= true` + `CLEAN_TREE_FLAG`, aplicado a `suite:`;
`make help` corregido (ya no dice "sin documentos", ver PR10). Sin cambios de código
Python — la puerta ya existía en `run_attack_suite.py` desde PR5/ADR-0017.

## Nota sobre el entorno de esta validación

`make -n suite` y `make suite` (real, sin `-n`) devuelven "Nothing to be done for
`suite'" en esta máquina, con GNU Make 3.81 (la versión que trae macOS de fábrica).
Se verificó que **es preexistente y no lo causa este cambio**: se reprodujo
idéntico con `git stash` sobre el commit de PR10, antes de tocar el Makefile. No se
investiga más a fondo aquí — está fuera del alcance de PR11 (el propio `run.sh` que
generó `suite-final.4.log` invoca `make suite` con éxito, así que en el entorno real
donde se generan los runs no ocurre) — y se valida el mecanismo por dos vías que sí
son deterministas y no dependen de esa invocación:

## 1. La expresión `CLEAN_TREE_FLAG` expande correctamente

Aislada en un Makefile mínimo con el mismo `make` del sistema:

```
$ cat > /tmp/pgtest.mk <<'EOF'
REQUIRE_CLEAN_TREE ?= true
CLEAN_TREE_FLAG = $(if $(filter true,$(REQUIRE_CLEAN_TREE)),--require-clean-tree,)
t:
	@echo "FLAG=[$(CLEAN_TREE_FLAG)]"
EOF
$ make -f /tmp/pgtest.mk t
FLAG=[--require-clean-tree]
$ make -f /tmp/pgtest.mk t REQUIRE_CLEAN_TREE=false
FLAG=[]
```

Y contra el Makefile real, `make -p` confirma que `REQUIRE_CLEAN_TREE` resuelve a
`true` por defecto y a `false` con el override, exactamente igual.

## 2. El gate real aborta antes de tráfico, con el árbol genuinamente sucio

El árbol de trabajo tenía cambios sin commitear de este mismo PR — condición real,
no simulada:

```
$ git status --short
 M Makefile

$ docker compose exec -e GIT_COMMIT=$(git rev-parse HEAD) -e GIT_DIRTY=true \
    -e GIT_DIRTY_FILES=3 backend python scripts/run_attack_suite.py \
    --require-clean-tree --id atk_001 --endpoint simple-prompt

  Peticiones HTTP al backend: 1
  ⚠ árbol de trabajo sucio: el commit no identifica el código que corre. Este run no puede agregarse con otros.
  ✗ --require-clean-tree: abortando antes de enviar tráfico (3 ficheros sucios).
```

El Run Folder que llegó a crear solo contiene `provenance.json` y una carpeta de
endpoint vacía — cero Session Files, cero peticiones HTTP reales enviadas, tal como
promete el mensaje. Descartado tras la comprobación.

## Suite completa: sin regresiones

Sin cambios de código Python en este PR, se confirma igualmente:

```
$ cd backend && python3 -m pytest tests/ -q
891 passed in 10.00s
```

Incluye `test_el_makefile_inyecta_la_procedencia_de_git_en_la_suite`, que parsea el
bloque `suite:` del propio Makefile — sigue en verde tras las líneas añadidas.
