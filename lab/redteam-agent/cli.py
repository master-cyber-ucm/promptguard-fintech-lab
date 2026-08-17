#!/usr/bin/env python3
"""Punto de entrada del Agente de red-team.

Uso:
  python cli.py                                        # target=proxy, caja-negra, autorreflexivo, 20 intentos/ejercicio
  python cli.py --target proxy --vulnerable             # control: mismo target, defensas OFF
  python cli.py --mode caja-gris                        # lee también eventos del SOC
  python cli.py --engine genetico --max-attempts 12
  python cli.py --techniques directa cross-context-leakage
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from config import parse_args  # noqa: E402
from orchestrator import ejecutar_campania  # noqa: E402
from reporting import escribir_informe  # noqa: E402


def main() -> int:
    config = parse_args()
    campania = ejecutar_campania(config)
    run_folder = escribir_informe(campania)

    total = len(campania.ejercicios)
    bypasses = sum(1 for e in campania.ejercicios if e.exito)
    print(f"\n═══ Campaña terminada: {bypasses}/{total} salvaguardas superadas ═══")
    print(f"Informe: {run_folder / 'run.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
