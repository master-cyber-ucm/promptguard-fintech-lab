"""Los scripts deben arrancar en los dos layouts en los que se ejecutan.

El host los ve como `lab/scripts/…` con el paquete en `lab/backend/src`. El contenedor
los ve como `/app/scripts/…` con el paquete en `/app/src`, porque `docker-compose.yml`
monta `./backend/src` directamente y ahí no existe ningún `/app/backend`.

Suponer una de las dos formas rompía la otra: `make suite` falló entero con
`ModuleNotFoundError: No module named 'src'`. Estos tests recorren el árbol real de
`scripts/` para que un import nuevo no vuelva a asumir un layout.
"""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[2]
SCRIPTS = LAB / "scripts"

#: Los ejecutables del pipeline: si uno no arranca, la corrida entera se cae.
CLI_SCRIPTS = (
    "run_attack_suite.py",
    "check_suite_run.py",
    "evaluate.py",
    "report.py",
    "judge_calibration.py",
)


@pytest.fixture(scope="module")
def container_layout(tmp_path_factory) -> Path:
    """Copia el árbol tal y como lo monta el contenedor: `src` junto a `scripts`.

    Se copia en vez de enlazar a propósito: `Path.resolve()` sigue los symlinks y
    devolvería el layout del host, con lo que la prueba no probaría nada.
    """
    raiz = tmp_path_factory.mktemp("app")
    shutil.copytree(SCRIPTS, raiz / "scripts")
    shutil.copytree(LAB / "backend" / "src", raiz / "src")
    shutil.copytree(LAB / "backend" / "config", raiz / "config")
    shutil.copytree(LAB / "backend" / "tests" / "fixtures", raiz / "tests" / "fixtures")
    (raiz / "audit" / "runs").mkdir(parents=True)
    assert not (raiz / "backend").exists(), "el contenedor no tiene /app/backend"
    return raiz


def _ejecutar(raiz: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=raiz, capture_output=True, text=True, timeout=120,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "FIXTURES_DIR": str(raiz / "tests" / "fixtures")},
    )


@pytest.mark.parametrize("script", CLI_SCRIPTS)
def test_cada_cli_arranca_en_el_layout_del_contenedor(container_layout, script):
    resultado = _ejecutar(container_layout, f"scripts/{script}", "--help")
    assert resultado.returncode == 0, resultado.stderr
    assert "ModuleNotFoundError" not in resultado.stderr


@pytest.mark.parametrize("script", CLI_SCRIPTS)
def test_cada_cli_arranca_en_el_layout_del_host(script):
    resultado = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--help"],
        cwd=LAB, capture_output=True, text=True, timeout=120,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_la_config_se_encuentra_en_el_layout_del_contenedor(container_layout):
    """`security-rubrics.yaml` se monta en `/app/config`, no en `/app/backend/config`."""
    resultado = _ejecutar(container_layout, "-c", (
        "import sys; sys.path.insert(0, 'scripts');"
        "from security_rubrics import load_catalog;"
        "print(len(load_catalog()['families']))"
    ))
    assert resultado.returncode == 0, resultado.stderr
    assert int(resultado.stdout.strip()) > 0


def test_las_fixtures_se_encuentran_en_el_layout_del_contenedor_sin_fixtures_dir(container_layout):
    """PR9: antes de esto, `FIXTURES_DIR` sin fijar resolvía a una ruta inexistente
    en el contenedor y `load_prompts()` devolvía `[]` en vez de fallar — varias
    aserciones sobre "todo el catálogo" pasaban sin haber mirado ningún fixture."""
    resultado = subprocess.run(
        [sys.executable, "-c", (
            "import sys; sys.path.insert(0, 'scripts');"
            "from fixture_loader import load_prompts;"
            "print(len(load_prompts(kind=None)))"
        )],
        cwd=container_layout, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin"},  # sin FIXTURES_DIR a propósito
    )
    assert resultado.returncode == 0, resultado.stderr
    assert int(resultado.stdout.strip()) > 0


def test_la_variable_de_entorno_sigue_mandando_sobre_las_fixtures(tmp_path):
    """`find_fixtures_dir` no puede ignorar un `FIXTURES_DIR` explícito (`smoke:`,
    `make suite`, `evaluate.py --run` ya dependen de este contrato)."""
    sys.path.insert(0, str(SCRIPTS))
    import lab_paths  # noqa: PLC0415

    otro = tmp_path / "otras_fixtures"
    otro.mkdir()
    import os  # noqa: PLC0415

    previo = os.environ.get("FIXTURES_DIR")
    os.environ["FIXTURES_DIR"] = str(otro)
    try:
        assert lab_paths.find_fixtures_dir() == otro
    finally:
        if previo is None:
            os.environ.pop("FIXTURES_DIR", None)
        else:
            os.environ["FIXTURES_DIR"] = previo


def test_el_corpus_del_juez_se_encuentra_en_el_layout_del_contenedor(container_layout):
    resultado = _ejecutar(container_layout, "-c", (
        "import sys; sys.path.insert(0, 'scripts');"
        "from judge_calibration import load_gold_set;"
        "print(len(load_gold_set()['cases']))"
    ))
    assert resultado.returncode == 0, resultado.stderr
    assert int(resultado.stdout.strip()) > 0


def test_el_run_folder_impreso_se_puede_volver_a_pasar_por_run(container_layout):
    """`app/audit/runs/X` se resolvía contra `/app` dando `/app/app/audit/…`.

    La ruta se imprime relativa a la raíz del lab, que es el cwd desde el que se
    invocan los scripts, así que reinyectarla en `--run` funciona.
    """
    resultado = _ejecutar(container_layout, "-c", (
        "import sys; sys.path.insert(0, 'scripts');"
        "from lab_paths import display_path, lab_root;"
        "print(display_path(lab_root() / 'audit/runs/20260831_000000_qwen'))"
    ))
    assert resultado.stdout.strip() == "audit/runs/20260831_000000_qwen"


def test_una_ruta_fuera_del_lab_se_imprime_entera(container_layout):
    resultado = _ejecutar(container_layout, "-c", (
        "import sys; sys.path.insert(0, 'scripts');"
        "from pathlib import Path; from lab_paths import display_path;"
        "print(display_path(Path('/otro/sitio/run')))"
    ))
    assert resultado.stdout.strip() == "/otro/sitio/run"


def test_ningun_script_cablea_una_ruta_absoluta_del_contenedor():
    """`/app/...` en código —no en un comentario— vuelve a atar el script a un layout."""
    culpables: list[str] = []
    for path in sorted(SCRIPTS.rglob("*.py")):
        arbol = ast.parse(path.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if nodo.value.startswith("/app/"):
                    culpables.append(f"{path.relative_to(SCRIPTS)}:{nodo.lineno} {nodo.value}")
    # `AUDIT_RUNS_DIR_CONTAINER` es la excepción legítima: es la ruta que el backend
    # verá DENTRO del contenedor, no la que usa el script para leer sus propios ficheros.
    culpables = [c for c in culpables if "audit/runs" not in c]
    assert culpables == []


# ── Procedencia: el contenedor no monta el repositorio ──────────────────────

def test_los_digests_de_artefactos_se_calculan_en_el_layout_del_contenedor(container_layout):
    """Apuntaban a `LAB/backend`, que en el contenedor no existe: todo salía `null`."""
    resultado = _ejecutar(container_layout, "-c", (
        "import sys, json; sys.path.insert(0, 'scripts');"
        "import provenance;"
        "print(json.dumps({k: bool(v) for k, v in provenance.artifact_digests().items()}))"
    ))
    assert resultado.returncode == 0, resultado.stderr
    digests = json.loads(resultado.stdout)
    for clave in ("system_prompt", "tool_permissions", "security_rubrics",
                  "fixtures", "evaluation_schema", "evaluators"):
        assert digests[clave], f"{clave} sin digest en el layout del contenedor"


def test_sin_git_el_estado_del_arbol_queda_desconocido_no_limpio(container_layout):
    """`dirty: False` sin haberlo comprobado afirma un árbol limpio que nadie miró."""
    resultado = _ejecutar(container_layout, "-c", (
        "import sys, json; sys.path.insert(0, 'scripts');"
        "import provenance; print(json.dumps(provenance.git_provenance()))"
    ))
    git = json.loads(resultado.stdout)
    assert git["dirty"] is None
    assert git["available"] is False


def test_el_commit_inyectado_por_el_host_se_respeta(container_layout):
    resultado = subprocess.run(
        [sys.executable, "-c", (
            "import sys, json; sys.path.insert(0, 'scripts');"
            "import provenance; print(json.dumps(provenance.git_provenance()))"
        )],
        cwd=container_layout, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin", "GIT_COMMIT": "abc123",
             "GIT_BRANCH": "main", "GIT_DIRTY": "true", "GIT_DIRTY_FILES": "7"},
    )
    git = json.loads(resultado.stdout)
    assert git["commit"] == "abc123"
    assert git["dirty"] is True
    assert git["dirty_files"] == 7
    assert git["available"] is True


def test_un_run_sin_procedencia_de_git_no_es_agregable():
    """No saber si el árbol estaba limpio no equivale a que lo estuviera."""
    sys.path.insert(0, str(SCRIPTS))
    import provenance  # noqa: PLC0415

    sin_git = {"artifacts": {"a": "1"}, "git": {"commit": None, "dirty": None,
                                                "available": False}}
    razones = provenance.aggregation_blockers(sin_git, dict(sin_git))
    assert any("no registró procedencia de git" in razon for razon in razones)


def test_el_makefile_inyecta_la_procedencia_de_git_en_la_suite():
    makefile = (LAB / "Makefile").read_text(encoding="utf-8")
    assert "GIT_COMMIT" in makefile and "GIT_DIRTY" in makefile
    bloque_suite = makefile.split("\nsuite:", 1)[1].split("\n\n", 1)[0]
    assert "$(GIT_ENV)" in bloque_suite
