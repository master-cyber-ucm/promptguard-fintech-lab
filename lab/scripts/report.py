#!/usr/bin/env python3
"""Genera run.json + run.md a partir de las secciones ## Evaluación · de los Session Files.

Usa el bloque JSON embebido <!-- eval: {...} --> para extraer los resultados
sin depender de parseo frágil de markdown.

Uso:
  python scripts/report.py                               # runs con evaluación y sin run.md
  python scripts/report.py --run audit/runs/20260628_X/  # run específico (--force implícito)
  python scripts/report.py --force                        # regenera aunque ya exista run.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts

RUNS_DIR = HERE.parent / "audit" / "runs"

SUCCESS = "SUCCESS"
BLOCKED = "BLOCKED"

_EVAL_DATA_RE = re.compile(r'<!-- eval: ({.*?}) -->')
_MODEL_RE     = re.compile(r'\| Modelo \| `([^`]+)` \|')

SEP  = "─" * 70
SEP2 = "═" * 70

_PIPELINE_MODEL_LABELS = re.compile(r"^(?:proxy-|document-sanitizer$)")

def _model_provenance(suite_config: dict, results_by_endpoint: dict[str, list[dict]]) -> dict:
    """No confunde etiquetas de defensa con el modelo de inferencia."""
    requested = suite_config.get("requested_model") or suite_config.get("model") or "unknown"
    observed, discrepancies = {}, []
    for endpoint, results in results_by_endpoint.items():
        models = sorted({r["model"] for r in results if r.get("model") not in {None, "", "unknown"} and not _PIPELINE_MODEL_LABELS.match(r["model"])})
        observed[endpoint] = models
        for model in models:
            if requested != "unknown" and model != requested:
                discrepancies.append({"endpoint": endpoint, "requested_model": requested, "effective_model": model, "reason": "modelo efectivo distinto del solicitado"})
    return {"requested_model": requested, "provider": suite_config.get("provider", "unknown"), "effective_models_by_endpoint": observed, "instrumentation_errors": discrepancies}


def _flush(text: str) -> None:
    print(text, flush=True)


# ──────────────────────────────────────────────────────────────────────────────
# Session file parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_session_file(path: Path, fixture_by_id: dict) -> dict | None:
    text = path.read_text(encoding="utf-8")

    m = _EVAL_DATA_RE.search(text)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    model_m = _MODEL_RE.search(text)
    fixture = fixture_by_id.get(data["fixture_id"], {})

    return {
        "fixture_id":      data["fixture_id"],
        "fixture_kind":    data["fixture_kind"],
        "expected_result": data["expected_result"],
        "method":          data.get("method", "unknown"),
        "verdict":         data["verdict"],
        "passed":          data["passed"],
        "detail":          data.get("detail", ""),
        "model_attempted_leak": data.get("model_attempted_leak", False),
        "client_exposed_leak": data.get("client_exposed_leak", False),
        "model":           model_m.group(1) if model_m else "unknown",
        "name":            fixture.get("name", data["fixture_id"]),
        "category":        fixture.get("category", ""),
        "owasp":           fixture.get("owasp", ""),
        "severity":        fixture.get("severity", ""),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────────

def _compute_stats(results: list[dict]) -> dict:
    attacks = [r for r in results if r["fixture_kind"] in ("attack-prompts", "navi-prompts")]
    legit   = [r for r in results if r["fixture_kind"] == "legitimate-prompts"]

    by_category: dict[str, dict] = {}
    for r in results:
        cat = r["category"] or "unknown"
        if cat not in by_category:
            by_category[cat] = {"total": 0, "passed": 0, "failed": 0}
        by_category[cat]["total"] += 1
        if r["passed"]:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1

    total        = len(results)
    atk_total    = len(attacks)
    leg_total    = len(legit)
    atk_blocked  = sum(1 for r in attacks if r["passed"])
    leg_passed   = sum(1 for r in legit   if r["passed"])

    return {
        "summary": {
            "total":                total,
            "passed":               sum(1 for r in results if r["passed"]),
            "failed":               sum(1 for r in results if not r["passed"]),
            "attack_block_rate":    round(atk_blocked / atk_total * 100, 1)              if atk_total else None,
            "attack_breach_rate":   round((atk_total - atk_blocked) / atk_total * 100, 1) if atk_total else None,
            "legitimate_pass_rate": round(leg_passed  / leg_total   * 100, 1)              if leg_total else None,
            "legitimate_fp_rate":   round((leg_total - leg_passed)  / leg_total  * 100, 1) if leg_total else None,
            "model_attempted_leaks": sum(1 for r in results if r.get("model_attempted_leak")),
            "client_exposed_leaks": sum(1 for r in results if r.get("client_exposed_leak")),
        },
        "by_category": by_category,
        "fixtures":    results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Markdown report
# ──────────────────────────────────────────────────────────────────────────────

def _build_md(run_data: dict) -> str:
    ts        = run_data["run_timestamp"]
    model     = run_data["model"]
    endpoints = run_data["endpoints_run"]
    lines: list[str] = []

    lines += [
        f"# Suite Run — {ts}",
        "",
        "## Contexto",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| Timestamp | `{ts}` |",
        f"| Modelo | `{model}` |",
        f"| Endpoints | {', '.join(f'`{e}`' for e in endpoints)} |",
        "",
    ]

    for ep in endpoints:
        ep_data = run_data["by_endpoint"][ep]
        s = ep_data["summary"]
        total = s["total"] or 1

        lines += [f"## Endpoint: `{ep}`", "", "| Métrica | Valor |", "|---------|-------|"]
        lines.append(f"| Total fixtures | {s['total']} |")
        lines.append(f"| Pasados ✅ | **{s['passed']}** ({round(s['passed']/total*100)}%) |")
        lines.append(f"| Fallados ❌ | {s['failed']} |")
        lines.append(f"| Fugas generadas por el modelo | {s['model_attempted_leaks']} |")
        lines.append(f"| Fugas expuestas al cliente | {s['client_exposed_leaks']} |")
        if s["attack_block_rate"] is not None:
            lines.append(f"| Bloqueo de ataques | **{s['attack_block_rate']}%** |")
        if s["attack_breach_rate"] is not None:
            lines.append(f"| Tasa de brechas | **{s['attack_breach_rate']}%** |")
        if s["legitimate_pass_rate"] is not None:
            lines.append(f"| Atención legítima | {s['legitimate_pass_rate']}% |")
        if s["legitimate_fp_rate"] is not None:
            lines.append(f"| Falsos positivos | {s['legitimate_fp_rate']}% |")
        lines.append("")

        lines += [
            "### Por categoría OWASP",
            "",
            "| Categoría | Total | Pasados | Fallados |",
            "|-----------|-------|---------|----------|",
        ]
        for cat, b in sorted(ep_data["by_category"].items()):
            lines.append(f"| {cat} | {b['total']} | {b['passed']} | {b['failed']} |")
        lines.append("")

    # Comparison table
    all_fids: list[str] = []
    seen: set[str] = set()
    for ep_data in run_data["by_endpoint"].values():
        for r in ep_data["fixtures"]:
            if r["fixture_id"] not in seen:
                all_fids.append(r["fixture_id"])
                seen.add(r["fixture_id"])

    lines += [
        "## Tabla comparativa por fixture",
        "",
        "Leyenda: ✅ passed · ❌ failed",
        "",
    ]

    header = "| ID | Nombre | Kind | Cat | Sev |" + "".join(f" {ep[:14]} |" for ep in endpoints)
    sep    = "|----|--------|------|-----|-----|" + "".join("-" * 16 + "|" for _ in endpoints)
    lines += [header, sep]

    for fid in all_fids:
        meta = next(
            (r for ep_data in run_data["by_endpoint"].values()
             for r in ep_data["fixtures"] if r["fixture_id"] == fid),
            None,
        )
        if meta is None:
            continue
        cells = ""
        for ep in endpoints:
            r = next((r for r in run_data["by_endpoint"][ep]["fixtures"] if r["fixture_id"] == fid), None)
            cells += f" {'✅' if (r and r['passed']) else ('❌' if r else '-')} |"
        lines.append(
            f"| `{fid}` | {meta['name'][:28]} | {meta['fixture_kind']} "
            f"| {meta['category']} | {meta['severity']} |{cells}"
        )
    lines.append("")

    # Detail per endpoint
    for ep in endpoints:
        lines += [f"## Detalle: `{ep}`", ""]
        for r in run_data["by_endpoint"][ep]["fixtures"]:
            icon = "✅" if r["passed"] else "❌"
            lines.append(
                f"- {icon} **`{r['fixture_id']}`** `{r['fixture_kind']}`"
                f" · verdict={r['verdict']} · [{r['method']}]"
            )
            if r.get("detail"):
                lines.append(f"  - _{r['detail'][:200]}_")
        lines.append("")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Run processing
# ──────────────────────────────────────────────────────────────────────────────

def process_run(run_folder: Path, *, force: bool, fixture_by_id: dict) -> None:
    _flush(f"\n  📂 {run_folder.name}")
    _flush(SEP)

    if not force and (run_folder / "run.md").exists():
        _flush("  run.md ya existe — skip (usa --force para regenerar)")
        return

    ep_dirs = sorted(d for d in run_folder.iterdir() if d.is_dir())
    if not ep_dirs:
        _flush("  ⚠ Sin subcarpetas de endpoint — skipping")
        return

    all_results: dict[str, list[dict]] = {}
    model = run_folder.name

    for ep_dir in ep_dirs:
        session_files = sorted(ep_dir.glob("*.md"))
        if not session_files:
            continue
        _flush(f"\n  Endpoint: {ep_dir.name}")

        ep_results: list[dict] = []
        for sf in session_files:
            parsed = parse_session_file(sf, fixture_by_id)
            if parsed is None:
                continue
            if parsed["model"] != "unknown":
                model = parsed["model"]
            icon = "✅" if parsed["passed"] else "❌"
            _flush(f"  {icon}  {parsed['fixture_id']:<35} {parsed['verdict']:<8}  [{parsed['method']}]")
            ep_results.append(parsed)

        if ep_results:
            all_results[ep_dir.name] = ep_results

    if not all_results:
        _flush("  ⚠ Sin evaluaciones — run.md no generado")
        return

    run_ts   = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_data = {
        "run_timestamp": run_ts,
        "model":         model,
        "endpoints_run": list(all_results.keys()),
        "by_endpoint":   {ep: _compute_stats(r) for ep, r in all_results.items()},
    }

    json_path = run_folder / "run.json"
    md_path   = run_folder / "run.md"
    json_path.write_text(json.dumps(run_data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_md(run_data), encoding="utf-8")

    _flush("")
    _flush(f"  📄 run.md   → {md_path.relative_to(HERE.parent.parent)}")
    _flush(f"  📋 run.json → {json_path.relative_to(HERE.parent.parent)}")

    _flush("")
    _flush(f"  {'Endpoint':<26}  {'Bloqueo':>8}  {'Brechas':>8}  {'FP%':>6}")
    _flush(SEP)
    for ep, ep_data in run_data["by_endpoint"].items():
        s   = ep_data["summary"]
        blk = f"{s['attack_block_rate']}%"     if s["attack_block_rate"]  is not None else "n/a"
        brc = f"{s['attack_breach_rate']}%"    if s["attack_breach_rate"] is not None else "n/a"
        fp  = f"{s['legitimate_fp_rate']}%"    if s["legitimate_fp_rate"] is not None else "n/a"
        _flush(f"  {ep:<26}  {blk:>8}  {brc:>8}  {fp:>6}")


def find_ready_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    ready = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir() or (d / "run.md").exists():
            continue
        for sf in d.rglob("*.md"):
            if sf.name == "run.md":
                continue
            if "<!-- eval:" in sf.read_text(encoding="utf-8"):
                ready.append(d)
                break
    return ready


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard · report")
    parser.add_argument("--run", dest="run_path", metavar="PATH",
                        help="Run Folder específico (implica --force)")
    parser.add_argument("--force", action="store_true",
                        help="Regenera run.md + run.json aunque ya existan")
    args = parser.parse_args()

    _flush(SEP2)
    _flush("  📊 PromptGuard · Report")
    _flush(SEP2)

    all_fixtures  = load_prompts(kind=None)
    fixture_by_id = {f["id"]: f for f in all_fixtures}
    _flush(f"  {len(fixture_by_id)} fixtures cargados")

    if args.run_path:
        run_folders = [Path(args.run_path).resolve()]
        if not run_folders[0].is_dir():
            print(f"Error: {args.run_path} no es un directorio válido", file=sys.stderr)
            sys.exit(1)
        force = True
    else:
        force = args.force
        if force:
            run_folders = sorted(d for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.exists() else []
        else:
            run_folders = find_ready_runs(RUNS_DIR)

    if not run_folders:
        _flush("  No hay runs listos para reportar.")
        return

    _flush(f"  {len(run_folders)} run(s) a procesar:")
    for rf in run_folders:
        _flush(f"    · {rf.name}")

    for run_folder in run_folders:
        process_run(run_folder, force=force, fixture_by_id=fixture_by_id)

    _flush("")
    _flush(SEP2)
    _flush("  ✅ Report completado.")
    _flush(SEP2)


if __name__ == "__main__":
    main()
