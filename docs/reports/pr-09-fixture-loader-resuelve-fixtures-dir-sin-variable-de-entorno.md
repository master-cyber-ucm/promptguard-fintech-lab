# PR 9 — `fixture_loader` debe resolver el directorio de fixtures sin depender de una variable de entorno

**Estado:** implementado
**Prioridad:** P0 — invalida en silencio partes de la suite de tests
**Origen:** no estaba en el análisis original de `20260901_190305_qwen2.5-3b`; se
descubrió al intentar validar PR 8 con la suite completa.
**Dependencias:** ninguna
**Desbloquea:** una validación honesta de PR 8 (ya corregida) y de cualquier PR
posterior que dependa de `load_prompts()` sobre el catálogo completo.

## Pregunta de diseño (persistida antes de investigar)

> Al ejecutar `docker compose exec backend python -m pytest tests/ -v` (el comando
> exacto de `make test`) sin fijar `FIXTURES_DIR`, ¿por qué `test_security_rubrics.py`
> pasa en 0,20 s recorriendo "111 fixtures" y `test_aplicabilidad_por_capacidades.py`
> falla exigiendo encontrar 11 de ellos?

**Por qué importa:** si una aserción sobre "todo el catálogo" puede pasar sin haber
mirado ningún fixture, cualquier corrección futura al catálogo (como la migración de
PR 8) puede pasar la suite sin haberse verificado realmente. Es un problema de
integridad del propio mecanismo de validación, no de una fixture concreta.

**Dueño de la decisión:** ninguno externo — defecto verificable en código.

**Criterio de aceptación:**
1. `load_prompts()` sin `FIXTURES_DIR` en el entorno debe encontrar los 111 fixtures
   reales, tanto en layout de host como de contenedor — nunca devolver una lista
   vacía en silencio cuando el directorio real existe.
2. Las tres formas de arrancar la suite mencionadas en la documentación del propio
   repositorio (`make test`, `pytest lab/` del `CLAUDE.md` raíz, y la invocación
   directa `cd lab/backend && pytest tests/`) deben funcionar sin que quien las
   ejecuta tenga que conocer manualmente un `PYTHONPATH`/env específico.
3. `FIXTURES_DIR` sigue siendo un override válido cuando se declara explícitamente
   (contrato ya usado por `smoke:`, `make suite`, etc. — no se rompe).
4. El mecanismo de resolución reutiliza el patrón ya establecido en `lab_paths.py`
   para este mismo problema (`src`, `config`), no inventa uno nuevo.

## Evidencia del caso

### 1. El "0 en silencio"

```
$ docker compose exec -T backend python3 -c "
from fixture_loader import load_prompts, FIXTURES_DIR
print('FIXTURES_DIR:', FIXTURES_DIR, 'exists:', FIXTURES_DIR.exists())
print('total:', len(load_prompts(kind=None)))
"
FIXTURES_DIR: /app/backend/tests/fixtures exists: False
total: 0
```

`scripts/fixture_loader.py`:

```python
HERE = Path(__file__).resolve().parent
FIXTURES_DIR = Path(
    os.environ.get("FIXTURES_DIR", str(HERE.parent / "backend" / "tests" / "fixtures"))
)
```

`docker-compose.yml` monta `./backend/tests` directamente en `/app/tests` — dentro
del contenedor no existe `/app/backend` en absoluto (lo documenta el propio
`lab_paths.py`, ver más abajo). El valor por defecto asume el layout del host y, como
`Path.rglob` sobre un directorio inexistente no lanza excepción, sencillamente no
encuentra nada.

### 2. El daño real: aserciones sobre "todo el catálogo" pasan sin catálogo

`test_security_rubrics.py::test_todo_fixture_de_ataque_tiene_rubrica_de_conducta`:

```python
def test_todo_fixture_de_ataque_tiene_rubrica_de_conducta():
    for fixture in load_prompts(kind=None):
        if fixture.get("kind") == "legitimate-prompts":
            continue
        assert rubric_for(fixture).strip(), f"{fixture['id']} sin rúbrica"
```

Con `load_prompts(kind=None) == []`, el bucle no itera nunca y el test pasa. Esto
afectó directamente a la validación de PR 8: los 23 tests de
`test_security_rubrics.py` + `test_hybrid_attack_evaluator.py` +
`test_deterministic_requirements.py` + `test_hybrid_evaluator.py` que se reportaron
en verde en `pr-08-validacion.md` corrieron sobre 0 fixtures reales — pasaron, pero
no comprobaron nada del catálogo migrado. Reejecutados con `FIXTURES_DIR` correcto,
siguen en verde (esta vez recorriendo 111 fixtures reales, confirmado por el tiempo
de ejecución: 0,20 s → 0,85 s) — el fix de PR 8 seguía siendo correcto, pero por
suerte, no por que la validación lo hubiera comprobado.

Un solo archivo tenía una guarda que atrapó el problema:
`test_aplicabilidad_por_capacidades.py::test_la_matriz_sin_canal_documental_deja_huerfanos_los_once_fixtures`
empieza con `assert len(fixtures) == len(DOC_FIXTURES)` antes de comprobar nada más
— y por eso es el único test (junto a `test_los_documentos_benignos_tambien_se_ejecutan`,
que exige una lista no vacía) que **falla** en vez de pasar en falso.

### 3. Ninguna de las formas documentadas de arrancar la suite funciona sola

```
# La que documenta el Makefile del propio lab (make test):
$ docker compose exec backend python -m pytest tests/ -v
→ ModuleNotFoundError: No module named 'fixture_loader' (varios módulos)

# La que documenta el CLAUDE.md de la raíz del proyecto (`pytest lab/`):
$ cd software && python3 -m pytest lab/ -q
→ ModuleNotFoundError: No module named 'src' (conftest.py)

# Invocación directa más intuitiva:
$ cd lab/backend && python3 -m pytest tests/ -q
→ ModuleNotFoundError: No module named 'scripts' (varios módulos)
```

La única combinación que funciona limpia es
`cd lab/backend && PYTHONPATH=.. python3 -m pytest tests/ -q` (883 passed, 0 failed,
0 errors) — no documentada en ningún sitio, y solo se encontró por experimentación
durante esta validación.

### 4. El patrón para resolverlo ya existe en el repo, para otro caso

`scripts/lab_paths.py` ya resuelve exactamente este problema para `src` y para
`config/*.yaml`, con un comentario que describe el defecto de `fixture_loader.py`
casi palabra por palabra:

> "Suponer una sola de las dos formas rompe la otra […] Se resuelve buscando el
> ancestro que contiene `src/`, sin adivinar."

`security_rubrics.py` ya usa `lab_paths.find_config(...)` para el catálogo de
rúbricas. `fixture_loader.py` es el único módulo de carga de datos del pipeline que
no pasó por este mecanismo.

## Alternativas consideradas

| Opción | Descripción | Veredicto |
|---|---|---|
| A. Exigir `FIXTURES_DIR` siempre (documentar el requisito) | Añadir el env var a `make test` y a la documentación. | Rechazada como única medida: no arregla `pytest lab/` ni la invocación directa: cualquiera que no lea la nota sigue teniendo un "0 en silencio", que es justo el fallo que hay que eliminar, no legislar. |
| B. Reutilizar `lab_paths` en `fixture_loader.py` + bootstrap de `sys.path` en `conftest.py` | Aplica el mecanismo ya probado del repo a los dos puntos que fallan: dónde vive `tests/fixtures` y cómo se hacen importables `src`/`scripts` antes de que `conftest.py` los necesite. | **Elegida.** |
| C. Reescribir todos los tests para no depender de imports relativos a layout | Cambiaría decenas de archivos y el propio patrón que el repo ya adoptó conscientemente (ver docstring de `lab_paths.py` y de `test_resolucion_de_rutas.py`). | Rechazada: no es un defecto de los tests, es una pieza de infraestructura (`fixture_loader`, `conftest`) que no adoptó un patrón ya existente. |

## Solución implementada

1. **`scripts/lab_paths.py`**: nuevas `fixtures_candidates()` / `find_fixtures_dir()`,
   mismo patrón que `config_candidates()`/`find_config()` (variable de entorno manda;
   si no, host y luego contenedor, en ese orden).
2. **`scripts/fixture_loader.py`**: `FIXTURES_DIR` se calcula con
   `find_fixtures_dir()` en vez del cálculo ad-hoc; si ninguna ruta candidata existe
   (entorno realmente atípico), conserva el valor por defecto anterior para no romper
   un `Path` válido en `import time` — pero ese caso ya no ocurre en host ni en
   contenedor.
3. **`backend/tests/conftest.py`**: bootstrap mínimo al principio del archivo que
   localiza `scripts/` probando los mismos dos candidatos que usa `lab_paths`
   internamente (sin poder importar `lab_paths` todavía, porque vive en `scripts/`),
   lo añade a `sys.path`, e invoca `lab_paths.ensure_src_importable()` antes del
   `from src.soc import store` que hoy encabeza el archivo. Con esto, `pytest`
   arranca igual desde `lab/backend/tests`, desde `/app/tests` (contenedor) o desde
   `lab/` (`pytest lab/`), sin `PYTHONPATH` externo.
4. **`Makefile`**: `test:` pasa a fijar `-e FIXTURES_DIR=$(FIXTURES)`, igual que ya
   hace `smoke:` — defensa en profundidad; con el fix de (1)-(3) deja de ser
   necesario, pero es gratis y consistente con el resto del Makefile.
