#!/usr/bin/env python3
"""Consolida varias Suite Runs en el informe final de resultados del TFM.

Los Run Folders deben haberse evaluado y tener `run.json`. El informe agrega
observaciones, no promedia porcentajes: así cada fixture/repetición conserva el
mismo peso y las rutas fuente quedan registradas.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS_DIR = HERE.parent / "audit" / "runs"


def _run_folder(value: str) -> Path:
    path = Path(value)
    if path.name == value:
        path = RUNS_DIR / value
    return path.resolve()


def _label(target: str, config: dict) -> str:
    profile = (config.get("proxy_profiles") or {}).get(target)
    if profile:
        return f"Proxy · {profile}"
    labels = {
        "simple-prompt": "Simple prompt",
        "complex-prompt": "Prompt complejo",
        "complex-with-context": "Prompt complejo + contexto",
        "proxy": "Proxy · full",
        "complex-with-document": "Documento",
    }
    return labels.get(target, target.replace("proxy-", "Proxy · "))


def _summary(results: list[dict]) -> dict:
    attacks = [r for r in results if r["fixture_kind"] in ("attack-prompts", "navi-prompts")]
    legitimate = [r for r in results if r["fixture_kind"] == "legitimate-prompts"]
    blocked = sum(r["passed"] for r in attacks)
    served = sum(r["passed"] for r in legitimate)
    return {
        "attack_total": len(attacks), "attack_blocked": blocked,
        "attack_block_rate": round(100 * blocked / len(attacks), 1) if attacks else None,
        "legitimate_total": len(legitimate), "legitimate_served": served,
        "legitimate_pass_rate": round(100 * served / len(legitimate), 1) if legitimate else None,
        "legitimate_fp_rate": round(100 * (len(legitimate) - served) / len(legitimate), 1) if legitimate else None,
    }


def _by_family(results: list[dict]) -> dict[str, dict]:
    """Desglosa solo ataques por la familia declarada por cada fixture."""
    families: dict[str, dict] = {}
    for result in results:
        if result["fixture_kind"] not in ("attack-prompts", "navi-prompts"):
            continue
        # Compatibilidad con run.json anteriores a `attack_type`.
        family = result.get("attack_type") or result.get("category") or "unknown"
        bucket = families.setdefault(family, {"total": 0, "blocked": 0, "breaches": 0})
        bucket["total"] += 1
        if result["passed"]:
            bucket["blocked"] += 1
        else:
            bucket["breaches"] += 1
    for bucket in families.values():
        bucket["block_rate"] = round(100 * bucket["blocked"] / bucket["total"], 1)
    return families


def _pct(value: float | None) -> str:
    return f"{value}%" if value is not None else "n/a"


def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard · informe final de resultados")
    parser.add_argument("--run", action="append", required=True, metavar="RUN_FOLDER",
                        help="Run Folder evaluado; se puede repetir")
    parser.add_argument("--output", default="audit/final-results.md", metavar="PATH",
                        help="Informe Markdown de salida (default: %(default)s)")
    parser.add_argument("--include-document", action="store_true",
                        help="Incluye complex-with-document; por defecto queda fuera del informe")
    args = parser.parse_args()

    groups: dict[tuple[str, str], dict] = defaultdict(lambda: {"results": [], "runs": []})
    sources: list[str] = []
    for value in args.run:
        folder = _run_folder(value)
        report_path = folder / "run.json"
        if not report_path.is_file():
            parser.error(f"{folder}: falta run.json; ejecuta primero make evaluate y make report")
        data = json.loads(report_path.read_text(encoding="utf-8"))
        config, model = data.get("suite_config", {}), data.get("model", "unknown")
        sources.append(str(folder))
        for target, target_data in data.get("by_endpoint", {}).items():
            if target == "complex-with-document" and not args.include_document:
                continue
            group = groups[(model, _label(target, config))]
            group["results"].extend(target_data.get("fixtures", []))
            group["runs"].append(folder.name)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    for (model, configuration), data in sorted(groups.items()):
        rows.append({"model": model, "configuration": configuration,
                     "runs": sorted(set(data["runs"])), **_summary(data["results"]),
                     "by_family": _by_family(data["results"])})

    lines = [
        "# PromptGuard — informe final de resultados", "", f"Generado: `{generated}`.", "",
        "Este informe agrega observaciones de runs evaluados. No promedia porcentajes: cada "
        "fixture y repetición cuenta una vez. Primero presenta el consolidado y después lo "
        "segmenta por familia de ataque. `Documento` queda fuera deliberadamente salvo que se "
        "invoque `--include-document`.",
        "", "| Modelo | Configuración | Runs | Ataques bloqueados | Atención legítima | Falsos positivos |",
        "|--------|---------------|-----:|--------------------|-------------------|------------------|",
    ]
    for row in rows:
        lines.append(f"| `{row['model']}` | {row['configuration']} | {len(row['runs'])} | "
                     f"{row['attack_blocked']}/{row['attack_total']} ({_pct(row['attack_block_rate'])}) | "
                     f"{row['legitimate_served']}/{row['legitimate_total']} ({_pct(row['legitimate_pass_rate'])}) | "
                     f"{_pct(row['legitimate_fp_rate'])} |")
    lines += ["", "## Segmentación por familia de ataque", "",
              "La familia es `attack_type` del catálogo de fixtures. Los prompts legítimos no aparecen "
              "en este desglose: su coste funcional ya se refleja en la tabla consolidada.", "",
              "| Modelo | Configuración | Familia | Bloqueados | Brechas | Bloqueo |",
              "|--------|---------------|---------|------------|---------|----------|"]
    for row in rows:
        for family, stats in sorted(row["by_family"].items()):
            lines.append(f"| `{row['model']}` | {row['configuration']} | `{family}` | "
                         f"{stats['blocked']}/{stats['total']} | {stats['breaches']}/{stats['total']} | {_pct(stats['block_rate'])} |")
    lines += ["", "## Evidencia fuente", "", *(f"- `{source}`" for source in sources), ""]

    output = Path(args.output)
    if not output.is_absolute():
        output = (HERE.parent / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    output.with_suffix(".json").write_text(
        json.dumps({"generated_at": generated, "sources": sources, "rows": rows}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Informe final: {output}")


if __name__ == "__main__":
    main()
