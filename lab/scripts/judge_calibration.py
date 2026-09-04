#!/usr/bin/env python3
"""Calibra el juez semántico contra el corpus oro antes de dejarle tocar una métrica.

P07: el juez se usaba con su propia `confidence` como único control de calidad. Aquí se
mide su acuerdo con etiquetas humanas por clase y se comprueba contra umbrales
declarados. Si no los alcanza, no se relaja el gate: los casos semánticos quedan
inconclusos.

    python scripts/judge_calibration.py                  # informe por consola
    python scripts/judge_calibration.py --json out.json  # artefacto reproducible
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab_paths import ensure_src_importable, find_config  # noqa: E402

ensure_src_importable()
from evaluations import EvaluationContext  # noqa: E402
from evaluations.semantic_judge import SemanticJudge, judge_bundle  # noqa: E402

GOLD_SET_FILENAME = "judge-gold-set.yaml"


def load_gold_set() -> dict:
    path = find_config(GOLD_SET_FILENAME, env_var="JUDGE_GOLD_SET")
    if path is None:
        raise FileNotFoundError(f"no se encontró {GOLD_SET_FILENAME}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


async def judge_case(case: dict, client: httpx.AsyncClient) -> str:
    judge = SemanticJudge(rubric=case.get("rubric", ""), system="neutral", include=None)
    context = EvaluationContext(
        response=case.get("response", ""),
        tools=case.get("tools") or [],
        expected_result="ALLOW",
        prompts=[case.get("prompt", "")],
        client=client,
    )
    return (await judge.judge(context)).disposition


def score(observed: list[tuple[str, str, bool]], thresholds: dict) -> dict:
    """Acuerdo por clase y global, con el veredicto de cada umbral.

    `observed` son tripletas (esperado, obtenido, must_abstain).
    """
    por_clase: dict[str, dict[str, int]] = {}
    aciertos = 0
    for esperado, obtenido, must_abstain in observed:
        bucket = por_clase.setdefault(esperado, {"total": 0, "agreed": 0})
        bucket["total"] += 1
        # En un caso de abstención obligatoria, cualquier veredicto distinto de
        # "evidencia insuficiente" es peor que no decidir: no cuenta como acierto.
        correcto = obtenido == esperado
        if must_abstain and obtenido != "EVIDENCE_INSUFFICIENT":
            correcto = False
        bucket["agreed"] += int(correcto)
        aciertos += int(correcto)

    clases = {
        clase: {
            **datos,
            "agreement": round(datos["agreed"] / datos["total"], 3) if datos["total"] else None,
            "threshold": thresholds.get(clase),
            "meets_threshold": (
                datos["agreed"] / datos["total"] >= thresholds.get(clase, 0)
                if datos["total"] else False
            ),
        }
        for clase, datos in por_clase.items()
    }
    total = len(observed)
    global_agreement = round(aciertos / total, 3) if total else None
    return {
        "judge_bundle": judge_bundle(),
        "total_cases": total,
        "overall_agreement": global_agreement,
        "overall_threshold": thresholds.get("overall"),
        "by_class": clases,
        "calibrated": bool(
            total
            and global_agreement >= thresholds.get("overall", 1.0)
            and all(datos["meets_threshold"] for datos in clases.values())
        ),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard · calibración del juez")
    parser.add_argument("--json", dest="json_path", help="Ruta del informe reproducible")
    args = parser.parse_args()

    gold = load_gold_set()
    casos = gold.get("cases") or []
    thresholds = gold.get("thresholds") or {}

    observed: list[tuple[str, str, bool]] = []
    async with httpx.AsyncClient() as client:
        for caso in casos:
            obtenido = await judge_case(caso, client)
            observed.append((caso["expected_disposition"], obtenido, bool(caso.get("must_abstain"))))
            marca = "✓" if obtenido == caso["expected_disposition"] else "✗"
            print(f"  {marca} {caso['id']:<45} esperado={caso['expected_disposition']:<22} obtenido={obtenido}", flush=True)

    informe = score(observed, thresholds)
    print("")
    print(f"  Acuerdo global: {informe['overall_agreement']} (umbral {informe['overall_threshold']})")
    for clase, datos in sorted(informe["by_class"].items()):
        print(f"    · {clase:<24} {datos['agreed']}/{datos['total']} = {datos['agreement']}")
    print(f"  Calibrado: {'sí' if informe['calibrated'] else 'NO — los casos semánticos quedan inconclusos'}")

    if args.json_path:
        Path(args.json_path).write_text(
            json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
        )
    sys.exit(0 if informe["calibrated"] else 1)


if __name__ == "__main__":
    asyncio.run(main())
