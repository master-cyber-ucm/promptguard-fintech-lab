"""Resuelve dónde vive el paquete `src` según el layout en el que se ejecute.

Los scripts del Analyze Pass importan el contrato de evaluación del backend
(`src.models.evaluation`, `src.core.…`), y ese paquete está en un sitio distinto según
cómo se ejecute:

    host        lab/scripts/…      →  el paquete está en  lab/backend/src
    contenedor  /app/scripts/…     →  el paquete está en  /app/src

`docker-compose.yml` monta `./backend/src` directamente en `/app/src`, así que dentro
del contenedor no existe ningún `/app/backend`. Suponer una sola de las dos formas
rompe la otra, y como `python scripts/x.py` pone en `sys.path` el directorio del script
—no el cwd— tampoco basta con confiar en que `/app` esté en la ruta.

Se resuelve buscando el ancestro que contiene `src/`, sin adivinar.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: Candidatos en orden: primero el layout del host, después el del contenedor.
_CANDIDATES = (HERE.parent / "backend", HERE.parent)


def backend_root() -> Path | None:
    """Directorio que contiene el paquete `src`, o `None` si no aparece."""
    for candidate in _CANDIDATES:
        if (candidate / "src").is_dir():
            return candidate
    return None


def ensure_src_importable() -> Path | None:
    """Deja `src` importable y devuelve la raíz usada.

    Idempotente: llamarla desde varios módulos no duplica entradas en `sys.path`.
    """
    root = backend_root()
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def lab_root() -> Path:
    """Raíz desde la que se resuelven `audit/`, `config/` y `tests/`.

    En el host es `lab/`; en el contenedor, `/app`. Es la referencia contra la que se
    imprimen las rutas de un Run Folder: una ruta relativa a otra cosa no se puede
    volver a pasar por `--run`.
    """
    return HERE.parent


def config_candidates(filename: str) -> tuple[Path, ...]:
    """Rutas donde puede vivir un fichero de `config/`, en orden de preferencia.

    `docker-compose.yml` monta `./backend/config` en `/app/config`, así que la ruta
    cambia con el layout igual que la del paquete `src`. Cablear `/app/config` funciona
    en el contenedor y en ningún otro sitio.
    """
    raiz = lab_root()
    return (raiz / "config" / filename, raiz / "backend" / "config" / filename)


def find_config(filename: str, *, env_var: str | None = None) -> Path | None:
    """Localiza un fichero de configuración. La variable de entorno manda."""
    import os  # noqa: PLC0415

    if env_var:
        declarado = os.environ.get(env_var, "").strip()
        if declarado and Path(declarado).is_file():
            return Path(declarado)
    for candidate in config_candidates(filename):
        if candidate.is_file():
            return candidate
    return None


def display_path(path: Path) -> str:
    """Ruta de un artefacto tal como puede volver a pasarse por `--run`.

    Se imprime relativa a la raíz del lab —el cwd desde el que se invocan los
    scripts—, no relativa al padre de esa raíz. En el contenedor, `HERE.parent.parent`
    es `/`, así que un Run Folder salía como `app/audit/runs/X` y, reinyectado en
    `make evaluate RUN=…`, se resolvía contra `/app` dando `/app/app/audit/…`: el
    comando fallaba con "no es un directorio válido".
    """
    try:
        return str(path.relative_to(lab_root()))
    except ValueError:
        return str(path)
