#!/usr/bin/env python3
"""Comprueba si un Run Folder contiene evidencia para cada fixture-endpoint esperado.

Uso:
  python scripts/check_suite_run.py --run 20260827_133926_qwen2.5-3b

El comando no evalúa respuestas ni llama al modelo. Contrasta el catálogo actual
de fixtures con los Session Files existentes y devuelve código 1 si hay huecos,
por lo que también sirve para automatizar la recuperación de una corrida larga.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from fixture_loader import load_prompts
from run_attack_suite import CHAT_ENDPOINTS, DOCUMENT_ENDPOINT_NAME

RUNS_DIR = HERE.parent / "audit" / "runs"
FIXTURE_RE = re.compile(r"\*\*Fixture\*\*:\s*`([^`]+)`")
KINDS = ("attack-prompts", "legitimate-prompts", "navi-prompts")


def _run_folder(name: str) -> Path:
    candidate = Path(name)
    if candidate.name != name or name in {".", ".."}:
        raise ValueError("--run debe ser solo el nombre de un Run Folder")
    return RUNS_DIR / name


def _expected_pairs(targets: list[str] | None = None) -> set[tuple[str, str]]:
    fixtures = [fixture for kind in KINDS for fixture in load_prompts(kind=kind)]
    targets = targets or list(CHAT_ENDPOINTS)
    pairs: set[tuple[str, str]] = set()
    for fixture in fixtures:
        applicable = fixture.get("applicable_endpoints")
        is_document = bool(fixture.get("document"))
        for target in targets:
            endpoint = "proxy" if target.startswith("proxy-") else target
            if (endpoint == DOCUMENT_ENDPOINT_NAME) != is_document:
                continue
            if applicable and endpoint not in applicable and endpoint != DOCUMENT_ENDPOINT_NAME:
                continue
            pairs.add((fixture["id"], target))
    return pairs


def _targets_from_manifest(folder: Path) -> list[str] | None:
    """Usa exactamente la matriz con que se lanzó el Run Folder.

    Las campañas históricas sin manifiesto conservan el comportamiento anterior
    (todos los endpoints), pero una suite actual excluye documentos y desdobla el
    proxy por perfil; verificarla contra la matriz vieja produciría falsos huecos.
    """
    manifest = folder / "suite-config.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    targets = data.get("targets")
    return targets if isinstance(targets, list) and all(isinstance(t, str) for t in targets) else None


def _evidence_pairs(folder: Path) -> tuple[set[tuple[str, str]], Counter[str]]:
    pairs: set[tuple[str, str]] = set()
    files_by_endpoint: Counter[str] = Counter()
    for path in folder.rglob("*.md"):
        match = FIXTURE_RE.search(path.read_text(encoding="utf-8", errors="replace"))
        if not match:
            continue
        pairs.add((match.group(1), path.parent.name))
        files_by_endpoint[path.parent.name] += 1
    return pairs, files_by_endpoint


def main() -> int:
    parser = argparse.ArgumentParser(description="Verifica la completitud de una Suite Run")
    parser.add_argument("--run", required=True, metavar="RUN_FOLDER")
    args = parser.parse_args()

    try:
        folder = _run_folder(args.run)
    except ValueError as error:
        parser.error(str(error))
    if not folder.is_dir():
        parser.error(f"Run Folder no encontrado: {folder}")

    targets = _targets_from_manifest(folder)
    expected = _expected_pairs(targets)
    evidence, files_by_endpoint = _evidence_pairs(folder)
    missing = sorted(expected - evidence)
    unexpected = sorted(evidence - expected)

    print(f"Run Folder : {folder.relative_to(HERE.parent.parent)}")
    print(f"Esperadas  : {len(expected)} combinaciones fixture-endpoint")
    print(f"Evidencia  : {len(evidence)} combinaciones únicas · {sum(files_by_endpoint.values())} Session Files")
    print("Por endpoint:")
    for endpoint in targets or CHAT_ENDPOINTS:
        print(f"  - {endpoint:<26} {files_by_endpoint[endpoint]} Session Files")

    if missing:
        print(f"\nFALTAN ({len(missing)}):")
        for fixture_id, endpoint in missing:
            print(f"  - {fixture_id} --endpoint {endpoint}")
    else:
        print("\nCOMPLETA: cada combinación esperada dejó al menos un Session File.")

    if unexpected:
        print(f"\nAviso: {len(unexpected)} pares no pertenecen al catálogo actual:")
        for fixture_id, endpoint in unexpected:
            print(f"  - {fixture_id} --endpoint {endpoint}")

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
