"""Fuente de semillas vendorizada desde probes reales de Garak (NVIDIA/CyberArk) —
ver `sources/tools/generate_garak_seeds.py` para cómo se generó
`sources/data/garak_seeds.json`, y `sources/README.md` para el mapeo curado a mano
entre probes y Técnicas.

Sin dependencia de `garak` en tiempo de ejecución: solo lee el JSON ya generado.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "garak_seeds.json"

name = "garak"


class GarakSource:
    name = name

    def __init__(self, data_path: Path | None = None) -> None:
        path = data_path or DATA_PATH
        if not path.exists():
            raise FileNotFoundError(
                f"No existe {path}. Genera las semillas primero con:\n"
                f"  pip install -r sources/tools/requirements-generate.txt\n"
                f"  python sources/tools/generate_garak_seeds.py"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        self._pools: dict[str, list[dict]] = data["seeds"]
        self._cursor: dict[str, int] = {}

    def siguiente(self, tecnica: dict) -> str | None:
        tid = tecnica["id"]
        pool = self._pools.get(tid)
        if not pool:
            return None
        idx = self._cursor.get(tid, 0)
        if idx >= len(pool):
            return None
        self._cursor[tid] = idx + 1
        return pool[idx]["text"]
