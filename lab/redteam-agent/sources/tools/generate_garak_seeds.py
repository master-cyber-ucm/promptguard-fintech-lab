#!/usr/bin/env python3
"""Genera sources/data/garak_seeds.json a partir de probes reales de Garak.

Requiere `pip install -r sources/tools/requirements-generate.txt` (garak, ~7 GB
con torch/transformers) — NO es una dependencia del agente en ejecución, solo de
este script de generación puntual. El JSON resultante SÍ se versiona en el repo,
así que el agente nunca necesita garak instalado para usar estas semillas.

Mapeo curado a mano (no automático) entre probes de Garak y las Técnicas de
taxonomy.yaml — solo se incluyen las dos técnicas para las que Garak tiene
cobertura real y relevante para un chatbot conversacional. El resto de técnicas
del harness (cross-context-leakage, pii-harvesting, acciones-no-autorizadas,
confused-deputy) son específicas del dominio bancario/multi-usuario de VerdaBank;
ninguna librería pública de probes genéricos tiene equivalente, así que no se
inventa un mapeo forzado — GarakSource.siguiente() devuelve None para esas
técnicas y el motor de evolución configurado sigue generando por su cuenta.

Uso:
    python sources/tools/generate_garak_seeds.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parent.parent / "data" / "garak_seeds.json"

# tecnica_id -> [(modulo.Clase, límite de prompts a tomar de esa clase), ...]
MAPEO = {
    "directa": [
        ("garak.probes.dan", "DanInTheWild", 15),
        ("garak.probes.promptinject", "HijackLongPrompt", 10),
        ("garak.probes.encoding", "InjectBase64", 5),
        ("garak.probes.encoding", "InjectROT13", 5),
    ],
    "filtrado-por-repeticion": [
        ("garak.probes.divergence", "Repeat", 10),
        ("garak.probes.divergence", "RepeatedToken", 10),
    ],
}

MAX_LEN = 800  # payloads más largos que esto no caben cómodamente en un solo turno de chat


def _cargar_prompts(modulo: str, clase: str, limite: int) -> list[dict]:
    mod = __import__(modulo, fromlist=[clase])
    cls = getattr(mod, clase)
    inst = cls()
    prompts = list(dict.fromkeys(inst.prompts))  # dedup preservando orden
    prompts = [p for p in prompts if p and len(p) <= MAX_LEN]
    origen = f"{modulo}.{clase}"
    return [{"text": p, "probe": origen} for p in prompts[:limite]]


def main() -> None:
    import garak

    seeds: dict[str, list[dict]] = {}
    for tecnica_id, fuentes in MAPEO.items():
        pool: list[dict] = []
        for modulo, clase, limite in fuentes:
            extraidos = _cargar_prompts(modulo, clase, limite)
            print(f"  {tecnica_id:<25} {modulo}.{clase:<20} -> {len(extraidos)} prompts")
            pool.extend(extraidos)
        seeds[tecnica_id] = pool

    data = {
        "source": "garak",
        "garak_version": garak.__version__,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mapeo_curado_a_mano": True,
        "nota": (
            "Solo 'directa' y 'filtrado-por-repeticion' tienen cobertura real en "
            "probes públicos de Garak; el resto de técnicas del harness son "
            "específicas del dominio bancario multi-usuario y no tienen equivalente "
            "en una librería de probes genérica — ver docstring de este script."
        ),
        "seeds": seeds,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in seeds.values())
    print(f"\n{total} semillas escritas en {OUT_PATH}")


if __name__ == "__main__":
    main()
