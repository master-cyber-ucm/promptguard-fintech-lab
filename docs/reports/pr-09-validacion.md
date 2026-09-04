# PR 9 — Evidencia de validación

## Qué se hizo

1. `scripts/lab_paths.py`: `fixtures_candidates()` / `find_fixtures_dir()`, mismo
   patrón que `config_candidates()`/`find_config()`.
2. `scripts/fixture_loader.py`: `FIXTURES_DIR` se calcula con `find_fixtures_dir()`.
3. `backend/tests/conftest.py`: bootstrap de `sys.path` (localiza `scripts/` probando
   los dos candidatos de layout, añade `lab_root()` para los imports `scripts.xxx`, e
   invoca `lab_paths.ensure_src_importable()`) antes de `from src.soc import store`.
4. `Makefile`: `test:` fija `-e FIXTURES_DIR=$(FIXTURES)`, igual que `smoke:`.
5. Dos tests nuevos en `test_resolucion_de_rutas.py`:
   `test_las_fixtures_se_encuentran_en_el_layout_del_contenedor_sin_fixtures_dir`
   (reproduce el layout de contenedor sin `FIXTURES_DIR` y exige `> 0` fixtures) y
   `test_la_variable_de_entorno_sigue_mandando_sobre_las_fixtures` (un `FIXTURES_DIR`
   explícito sigue ganando).

## Las tres formas de arrancar la suite, antes y después

| Comando | Antes | Después |
|---|---|---|
| `docker compose exec backend python -m pytest tests/ -v` (`make test`) | `ModuleNotFoundError` en 8 módulos; el resto corría sobre **0 fixtures** en silencio | **856 passed**, 8 failed / 21 errores — ver nota |
| `pytest lab/` (comando documentado en el `CLAUDE.md` raíz del proyecto) | `ModuleNotFoundError: No module named 'src'` — ni siquiera arrancaba | **908 passed**, 0 failed, 0 errores |
| `cd lab/backend && pytest tests/` | `ModuleNotFoundError: No module named 'scripts'` en 8 módulos | **885 passed**, 0 failed, 0 errores |

Las dos formas de host quedan completamente limpias sin ninguna variable de entorno
ni `PYTHONPATH` manual — que es exactamente el criterio de aceptación 2 de PR9.

## Docker: los 8 failed / 21 errores restantes son preexistentes y de otro problema

Se comparó, test a test, el listado de `FAILED`/`ERROR` en modo Docker antes y
después del fix:

- Los **8 failed** son idénticos byte a byte a los que ya fallaban antes de tocar
  nada: `test_reproducibilidad_e_incertidumbre.py` (2) y
  `test_resolucion_de_rutas.py::test_cada_cli_arranca_en_el_layout_del_host` /
  `test_el_makefile_inyecta_la_procedencia_de_git_en_la_suite` (6) — todos leen
  `LAB = Path(__file__).resolve().parents[2]`, que en el contenedor resuelve a `/`
  (no hay `/app/backend`), y necesitan el `.git`/`Makefile` reales del repositorio,
  que `docker-compose.yml` no monta a propósito (el contenedor solo monta
  subcarpetas de `backend/`, nunca la raíz del repo). No tiene relación con
  `FIXTURES_DIR` ni con el import de `src`/`scripts`.
- Los **21 errores** (20 preexistentes + 1 nuevo) son todos setup de la fixture
  `container_layout`, que hace `shutil.copytree(LAB / "backend" / "src", …)` — mismo
  `LAB` roto. El nuevo (`test_las_fixtures_se_encuentran_en_el_layout_del_contenedor_sin_fixtures_dir`)
  hereda el mismo error de setup que sus 7 hermanos que ya usaban esa fixture — no es
  un defecto nuevo, es la misma causa aplicada a un test más. Corrido en host, donde
  `LAB` sí resuelve, **pasa** (ver tabla siguiente).

Esto confirma que `test_resolucion_de_rutas.py` está diseñado para ejecutarse en
host (su propia fixture necesita resolver la raíz real del repositorio para construir
el árbol simulado de contenedor) y no como parte de `docker compose exec`. Corregirlo
excede el alcance de PR 9 (regla del criterio de aceptación: reusar el patrón
existente, no reescribir tests no relacionados) y queda fuera.

## `test_resolucion_de_rutas.py` completo, en host

```
$ cd lab/backend && python3 -m pytest tests/test_resolucion_de_rutas.py -v
22 passed in 2.07s
```

Los 22 incluyen los 5 parametrizados de layout de host, los 5 de layout de
contenedor (simulado vía `container_layout`, que en host sí resuelve `LAB`
correctamente), y los 2 nuevos de esta PR.

## Suite completa, host, sin PYTHONPATH manual

```
$ cd lab/backend && python3 -m pytest tests/ -q
885 passed in 9.22s

$ cd software && python3 -m pytest lab/ -q
908 passed in 9.59s
```

## Corrección retroactiva de PR 8

`pr-08-validacion.md` se actualizó con una nota: los recuentos de suite completa que
reportaba se capturaron sin `FIXTURES_DIR`, así que parte de lo que decían haber
comprobado en realidad corrió sobre 0 fixtures. Repetido con el entorno correcto, la
conclusión de PR 8 no cambia (0 regresiones, migración correcta) — pero ahora está
comprobado de verdad, no en falso.
