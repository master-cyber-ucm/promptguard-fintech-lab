"""Procedencia del run: qué artefactos exactos produjeron estos números.

P14: el manifiesto registraba `defense_version: dev`, sin Git SHA, sin estado dirty,
sin parámetros efectivos del modelo, sin seeds y sin versión del juez. Nueve casos de
una familia pequeña no se pueden reconstruir con eso — ni siquiera se sabe qué
implementación los produjo.

El manifiesto referencia artefactos por contenido: cambiar un prompt, una policy o un
schema cambia su digest, y eso impide agregar en silencio dos runs que midieron cosas
distintas.
"""

from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from lab_paths import backend_root, lab_root  # noqa: E402

LAB = lab_root()
REPO = LAB.parent

PROVENANCE_SCHEMA_VERSION = 3


def _sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _sha256_tree(root: Path, patterns: tuple[str, ...]) -> str | None:
    """Digest estable de un conjunto de ficheros, ordenado por ruta relativa."""
    if not root.is_dir():
        return None
    digest = hashlib.sha256()
    encontrados = sorted(
        {path for patron in patterns for path in root.rglob(patron) if path.is_file()}
    )
    if not encontrados:
        return None
    for path in encontrados:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _git(*args: str) -> str | None:
    try:
        salida = subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return salida.stdout.strip() if salida.returncode == 0 else None


def git_provenance() -> dict:
    """Commit y estado del árbol, o la constancia de que no se pudieron leer.

    Dentro del contenedor no hay repositorio montado: `docker-compose.yml` monta
    `./backend/src`, `./scripts` y `./audit`, no el `.git`. Devolver ahí
    `dirty: False` afirmaría un árbol limpio que nadie comprobó — un silencio leído
    como conformidad, que es justo lo que P14 trata de eliminar.

    Por eso el host puede inyectar los datos por entorno (`GIT_COMMIT`, `GIT_DIRTY`) y,
    si no llegan y `git` tampoco responde, `dirty` queda en `None`: desconocido.
    """
    commit = os.environ.get("GIT_COMMIT", "").strip() or _git("rev-parse", "HEAD")
    branch = os.environ.get("GIT_BRANCH", "").strip() or _git("rev-parse", "--abbrev-ref", "HEAD")

    declarado = os.environ.get("GIT_DIRTY", "").strip().lower()
    if declarado in {"true", "1", "yes"}:
        dirty, sucios = True, int(os.environ.get("GIT_DIRTY_FILES", "0") or 0)
    elif declarado in {"false", "0", "no"}:
        dirty, sucios = False, 0
    else:
        estado = _git("status", "--porcelain")
        if estado is None:
            # `git` no está disponible: no se sabe, y no se finge que sí.
            dirty, sucios = None, None
        else:
            dirty = bool(estado)
            sucios = len([linea for linea in estado.splitlines() if linea.strip()])

    diff = _git("diff", "HEAD")
    return {
        "commit": commit,
        "branch": branch,
        # `dirty` no es un detalle: si el árbol tiene cambios sin commitear, el commit
        # por sí solo no identifica el código que corrió. `None` significa desconocido.
        "dirty": dirty,
        "dirty_files": sucios,
        "available": bool(commit) and dirty is not None,
        "diff_sha256": hashlib.sha256((diff or "").encode("utf-8")).hexdigest()[:16] if diff else None,
    }


def artifact_digests() -> dict:
    """Digests de todo lo que define el experimento y puede cambiar entre runs.

    La raíz se resuelve: en el host los artefactos cuelgan de `lab/backend`, en el
    contenedor de `/app`. Cablear una sola forma dejaba todos los digests en `null`
    justo donde se ejecuta la suite de verdad.
    """
    backend = backend_root() or (LAB / "backend")
    return {
        "system_prompt": _sha256_file(backend / "config" / "prompts" / "clara_system.txt"),
        "simple_prompt": _sha256_file(backend / "config" / "prompts" / "clara_simple.txt"),
        "tool_permissions": _sha256_file(backend / "config" / "rules" / "tool_permissions.yaml"),
        "security_rubrics": _sha256_file(backend / "config" / "security-rubrics.yaml"),
        "judge_gold_set": _sha256_file(backend / "config" / "judge-gold-set.yaml"),
        "evaluation_schema": _sha256_file(
            backend / "config" / "schemas" / "evaluation-result-v2.json"
        ),
        "injection_rules": _sha256_tree(backend / "config" / "rules", ("*.yaml", "*.yml")),
        "fixtures": _sha256_tree(backend / "tests" / "fixtures", ("*.yaml",)),
        "evaluators": _sha256_tree(LAB / "scripts" / "evaluations", ("*.py",)),
        "requirements": _sha256_file(backend / "requirements.txt"),
    }


def runtime_provenance() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "container": Path("/.dockerenv").exists(),
        "cpu_count": os.cpu_count(),
    }


def model_provenance(model_info: dict) -> dict:
    """Parámetros efectivos del target, no solo su nombre lógico."""
    return {
        "provider": model_info.get("provider"),
        "model": model_info.get("model"),
        "digest": model_info.get("digest"),
        "max_output_tokens": os.environ.get("CLARA_MAX_OUTPUT_TOKENS", "1024"),
        "base_url": os.environ.get("OLLAMA_BASE_URL") or os.environ.get("LLM_BASE_URL"),
        # Muchos proveedores locales no honran una seed. Se declara la limitación en
        # vez de prometer un determinismo que no existe.
        "seed_honored": False,
        "seed_limitation": (
            "el proveedor no garantiza determinismo por seed: la variabilidad se "
            "controla con repeticiones e intervalos, no con reproducción exacta"
        ),
    }


def build(model_info: dict, *, seed: int, repeat: int, judge_bundle: dict) -> dict:
    """Manifiesto de procedencia, inmutable, generado antes de abrir tráfico."""
    return {
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "git": git_provenance(),
        "artifacts": artifact_digests(),
        "runtime": runtime_provenance(),
        "target_model": model_provenance(model_info),
        "judge": judge_bundle,
        "execution_design": {
            "design": "randomized_blocks(fixture, repetition)",
            "seed": seed,
            "repeat": repeat,
            "warmup_excluded": True,
        },
    }


def fingerprint(manifest: dict) -> str:
    """Huella de los artefactos. Dos runs con la misma huella son agregables."""
    import json  # noqa: PLC0415

    material = {
        "artifacts": manifest.get("artifacts"),
        "git_commit": (manifest.get("git") or {}).get("commit"),
        "git_dirty": (manifest.get("git") or {}).get("dirty"),
        "judge": manifest.get("judge"),
        "target_model": {
            clave: valor for clave, valor in (manifest.get("target_model") or {}).items()
            if clave in {"provider", "model", "digest", "max_output_tokens"}
        },
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()[:16]


def aggregation_blockers(a: dict, b: dict) -> list[str]:
    """Por qué dos runs NO pueden agregarse. Lista vacía = son comparables."""
    razones: list[str] = []
    if fingerprint(a) != fingerprint(b):
        artefactos_a = a.get("artifacts") or {}
        artefactos_b = b.get("artifacts") or {}
        distintos = sorted(
            clave for clave in set(artefactos_a) | set(artefactos_b)
            if artefactos_a.get(clave) != artefactos_b.get(clave)
        )
        razones.append(
            f"artefactos distintos: {distintos}" if distintos
            else "huella de procedencia distinta"
        )
    for manifiesto, etiqueta in ((a, "A"), (b, "B")):
        git = manifiesto.get("git") or {}
        if git.get("dirty"):
            razones.append(
                f"el run {etiqueta} corrió con el árbol de trabajo sucio: "
                "el commit no identifica el código que se ejecutó"
            )
        elif not git.get("available"):
            # No saber si el árbol estaba limpio no equivale a que lo estuviera.
            razones.append(
                f"el run {etiqueta} no registró procedencia de git: no puede afirmarse "
                "qué código lo produjo"
            )
    return razones
