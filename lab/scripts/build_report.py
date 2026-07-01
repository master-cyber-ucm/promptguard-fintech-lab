#!/usr/bin/env python3
"""Comparación y reporte final — genera run.md + run.json comparando ambos evaluadores.

Lee ## Evaluación Determinista y ## Evaluación Juez de cada Session File.
Escribe run.md y run.json en la raíz de cada Run Folder.

Uso:
  python build_report.py                          # runs con ambas evaluaciones y sin run.md
  python build_report.py --force                  # regenera run.md + run.json aunque existan
  python build_report.py --run audit/runs/20260628_X/  # run específico (forzado)
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

SUCCESS    = "SUCCESS"
BLOCKED    = "BLOCKED"
CONFIRMADO = "CONFIRMADO"
DUDOSO     = "DUDOSO"

# ──────────────────────────────────────────────────────────────────────────────
# Parsing de secciones de evaluación
# ──────────────────────────────────────────────────────────────────────────────

_FIXTURE_RE   = re.compile(r'\*\*Fixture\*\*:\s*`([^`]+)`\s*·\s*([^\s·]+)\s*·\s*expected:\s*`([^`]+)`')
_MODEL_RE     = re.compile(r'\| Modelo \| `([^`]+)` \|')
_DET_BLOCK_RE = re.compile(r'## Evaluación Determinista ·.*?(?=## Evaluación|\Z)', re.DOTALL)
_JUDGE_BLOCK_RE = re.compile(r'## Evaluación Juez ·.*?(?=## Evaluación|\Z)', re.DOTALL)
_VERDICT_RE   = re.compile(r'\| Verdict \| \*\*(\w+)\*\*')
_TRIGGER_RE   = re.compile(r'\*\*Evento disparado:\*\* `([^`]+)`')
_JUDGE_RAW_RE = re.compile(r'\| Juez raw \| (\w+) \|')


def _extract_verdict(block: str) -> str | None:
    m = _VERDICT_RE.search(block)
    return m.group(1) if m else None


def parse_session_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    fixture_matches = _FIXTURE_RE.findall(text)
    if not fixture_matches:
        return None
    fixture_id, fixture_kind, expected_result = fixture_matches[0]
    model_match = _MODEL_RE.search(text)
    model = model_match.group(1) if model_match else "unknown"

    det_block   = _DET_BLOCK_RE.search(text)
    judge_block = _JUDGE_BLOCK_RE.search(text)

    det_verdict   = _extract_verdict(det_block.group(0))   if det_block   else None
    judge_verdict = _extract_verdict(judge_block.group(0)) if judge_block else None

    trigger_m   = _TRIGGER_RE.search(det_block.group(0)) if det_block else None
    triggered   = trigger_m.group(1) if trigger_m else None

    judge_raw_m = _JUDGE_RAW_RE.search(judge_block.group(0)) if judge_block else None
    judge_raw   = judge_raw_m.group(1) if judge_raw_m else None

    agreement = None
    if det_verdict and judge_verdict:
        agreement = CONFIRMADO if det_verdict == judge_verdict else DUDOSO

    return {
        "fixture_id":      fixture_id,
        "fixture_kind":    fixture_kind,
        "expected_result": expected_result,
        "model":           model,
        "det_verdict":     det_verdict,
        "judge_verdict":   judge_verdict,
        "judge_raw":       judge_raw,
        "triggered_event": triggered,
        "agreement":       agreement,
        "path":            str(path),
    }


def _match_icon(expected: str, verdict: str | None) -> str:
    if verdict is None:
        return "❓"
    expected = expected.upper()
    if expected in ("BLOCK", "REFUSE"):
        return "✅" if verdict == BLOCKED else "❌"
    elif expected == "ALLOW":
        return "✅" if verdict == SUCCESS else "❌"
    return "❓"


# ──────────────────────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────────────────────

def _endpoint_stats(results: list[dict]) -> dict:
    by_kind:     dict[str, dict] = {}
    by_category: dict[str, dict] = {}

    counts = {
        "total":       0,
        CONFIRMADO:    0,
        DUDOSO:        0,
        "sin_det":     0,
        "sin_judge":   0,
        "atk_success": 0,
        "atk_total":   0,
        "leg_fp":      0,
        "leg_total":   0,
    }

    for r in results:
        kind    = r.get("fixture_kind") or "unknown"
        cat     = r.get("category")     or "unknown"
        agr     = r.get("agreement")    or "PENDING"

        counts["total"] += 1
        if agr == CONFIRMADO:
            counts[CONFIRMADO] += 1
        elif agr == DUDOSO:
            counts[DUDOSO] += 1
        if r.get("det_verdict") is None:
            counts["sin_det"] += 1
        if r.get("judge_verdict") is None:
            counts["sin_judge"] += 1

        if kind == "attack-prompts":
            counts["atk_total"] += 1
            if r.get("det_verdict") == SUCCESS:
                counts["atk_success"] += 1
        elif kind == "legitimate-prompts":
            counts["leg_total"] += 1
            if r.get("det_verdict") == BLOCKED:
                counts["leg_fp"] += 1

        for bucket, key in [(by_kind, kind), (by_category, cat)]:
            if key not in bucket:
                bucket[key] = {"total": 0, CONFIRMADO: 0, DUDOSO: 0, "PENDING": 0}
            bucket[key]["total"] += 1
            bucket[key][agr if agr in (CONFIRMADO, DUDOSO) else "PENDING"] += 1

    return {
        "summary": {
            "total":              counts["total"],
            "confirmados":        counts[CONFIRMADO],
            "dudosos":            counts[DUDOSO],
            "sin_det":            counts["sin_det"],
            "sin_judge":          counts["sin_judge"],
            "atk_success_rate":   round(counts["atk_success"] / counts["atk_total"] * 100, 1) if counts["atk_total"] else None,
            "leg_fp_rate":        round(counts["leg_fp"]      / counts["leg_total"] * 100, 1) if counts["leg_total"] else None,
        },
        "by_kind":     by_kind,
        "by_category": by_category,
        "fixtures":    results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# JSON y Markdown del reporte
# ──────────────────────────────────────────────────────────────────────────────

def _build_json(all_results: dict[str, list[dict]], model_info: dict, run_ts: str) -> dict:
    endpoints_run = list(all_results.keys())
    by_endpoint   = {ep: _endpoint_stats(r) for ep, r in all_results.items()}

    fixture_ids: list[str] = []
    seen: set[str] = set()
    for results in all_results.values():
        for r in results:
            if r["fixture_id"] not in seen:
                fixture_ids.append(r["fixture_id"])
                seen.add(r["fixture_id"])

    comparison = []
    for fid in fixture_ids:
        meta = next((r for results in all_results.values() for r in results if r["fixture_id"] == fid), None)
        if meta is None:
            continue
        entry = {
            "id":              fid,
            "kind":            meta.get("fixture_kind", ""),
            "expected_result": meta.get("expected_result", ""),
            "verdicts": {
                ep: next(
                    ({"det": r["det_verdict"], "judge": r["judge_verdict"], "agreement": r["agreement"]}
                     for r in results if r["fixture_id"] == fid),
                    None,
                )
                for ep, results in all_results.items()
            },
        }
        comparison.append(entry)

    return {
        "run_timestamp": run_ts,
        "model":         model_info,
        "endpoints_run": endpoints_run,
        "by_endpoint":   by_endpoint,
        "comparison":    comparison,
    }


def _agr_icon(agr: str | None) -> str:
    if agr == CONFIRMADO: return "✅"
    if agr == DUDOSO:     return "⚠️"
    return "❓"


def _build_md(data: dict) -> str:
    ts        = data["run_timestamp"]
    model     = data["model"]
    endpoints = data["endpoints_run"]
    lines: list[str] = []

    lines += [
        f"# Suite Run — {ts}",
        "",
        "## Contexto",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| Timestamp | `{ts}` |",
        f"| Proveedor | `{model.get('provider', '?')}` |",
        f"| Modelo | `{model.get('model', '?')}` |",
        f"| Endpoints | {', '.join(f'`{e}`' for e in endpoints)} |",
        "",
        "> Leyenda de acuerdo: ✅ CONFIRMADO · ⚠️ DUDOSO · ❓ pendiente",
        "",
    ]

    for ep in endpoints:
        ep_data = data["by_endpoint"][ep]
        s = ep_data["summary"]
        lines += [f"## Endpoint: `{ep}`", "", "| Métrica | Valor |", "|---------|-------|"]
        lines.append(f"| Total fixtures | {s['total']} |")
        lines.append(f"| Confirmados | **{s['confirmados']}** ({round(s['confirmados']/s['total']*100) if s['total'] else 0}%) |")
        lines.append(f"| Dudosos | {s['dudosos']} |")
        if s["atk_success_rate"] is not None:
            lines.append(f"| Tasa de éxito de ataques (det.) | **{s['atk_success_rate']}%** |")
        if s["leg_fp_rate"] is not None:
            lines.append(f"| Falsos positivos en legítimos (det.) | {s['leg_fp_rate']}% |")
        if s["sin_det"]:
            lines.append(f"| Sin evaluación determinista | {s['sin_det']} |")
        if s["sin_judge"]:
            lines.append(f"| Sin evaluación juez | {s['sin_judge']} |")
        lines.append("")

    lines += [
        "## Tabla comparativa por fixture",
        "",
        "| ID | Kind | Expected | Det | Juez | Acuerdo |",
        "|----|------|----------|-----|------|---------|",
    ]
    for entry in data["comparison"]:
        for ep, vd in (entry.get("verdicts") or {}).items():
            if vd is None:
                continue
            det   = vd.get("det")   or "?"
            judge = vd.get("judge") or "?"
            agr   = vd.get("agreement")
            mi    = _match_icon(entry.get("expected_result",""), det if det != "?" else None)
            lines.append(
                f"| `{entry['id']}` | {entry.get('kind','')} | `{entry.get('expected_result','')}` "
                f"| {det} {mi} | {judge} | {_agr_icon(agr)} {agr or 'PENDING'} |"
            )
    lines.append("")

    for ep in endpoints:
        lines += [f"## Detalle: `{ep}`", ""]
        for r in data["by_endpoint"][ep]["fixtures"]:
            agr    = r.get("agreement")
            det    = r.get("det_verdict") or "?"
            judge  = r.get("judge_verdict") or "?"
            mi     = _match_icon(r.get("expected_result",""), det if det != "?" else None)
            lines.append(
                f"- {_agr_icon(agr)} **`{r['fixture_id']}`** `{r.get('fixture_kind','')}`"
                f" · det={det}{mi} · juez={judge} · {agr or 'PENDING'}"
            )
            if r.get("triggered_event"):
                lines.append(f"  - _evento: {r['triggered_event']}_")
        lines.append("")

    return "\n".join(lines) + "\n"


# ──────────────────────────────────────────────────────────────────────────────
# Lógica de run folders
# ──────────────────────────────────────────────────────────────────────────────

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


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
    model_info = {"provider": "unknown", "model": run_folder.name}

    for ep_dir in ep_dirs:
        session_files = sorted(ep_dir.glob("*.md"))
        if not session_files:
            continue
        _flush(f"\n  Endpoint: {ep_dir.name}")

        ep_results: list[dict] = []
        for sf in session_files:
            parsed = parse_session_file(sf)
            if parsed is None:
                continue

            fixture = fixture_by_id.get(parsed["fixture_id"], {})
            parsed["category"] = fixture.get("category", "unknown")

            if model_info["model"] == run_folder.name:
                model_info["model"] = parsed["model"]

            agr = parsed.get("agreement")
            icon = _agr_icon(agr)
            det   = parsed.get("det_verdict")   or "?"
            judge = parsed.get("judge_verdict") or "?"
            _flush(f"  {icon}  {parsed['fixture_id']:<35} det={det:<8} juez={judge}")

            ep_results.append(parsed)

        if ep_results:
            all_results[ep_dir.name] = ep_results

    if not all_results:
        _flush("  ⚠ Sin resultados — run.md no generado")
        return

    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_data = _build_json(all_results, model_info, run_ts)

    json_path = run_folder / "run.json"
    md_path   = run_folder / "run.md"
    json_path.write_text(json.dumps(run_data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(_build_md(run_data), encoding="utf-8")

    _flush("")
    _flush(f"  📄 run.md   → {md_path.relative_to(HERE.parent.parent)}")
    _flush(f"  📋 run.json → {json_path.relative_to(HERE.parent.parent)}")

    # Quick summary
    _flush("")
    _flush(f"  {'Endpoint':<26}  {'Confirm%':>9}  {'Dudosos':>8}  {'AtkOK%':>7}  {'FP%':>6}")
    _flush(SEP)
    for ep, ep_data in run_data["by_endpoint"].items():
        s = ep_data["summary"]
        total = s["total"] or 1
        conf  = f"{round(s['confirmados']/total*100)}%"
        dud   = str(s["dudosos"])
        atk   = f"{s['atk_success_rate']}%" if s["atk_success_rate"] is not None else "n/a"
        fp    = f"{s['leg_fp_rate']}%"       if s["leg_fp_rate"]       is not None else "n/a"
        _flush(f"  {ep:<26}  {conf:>9}  {dud:>8}  {atk:>7}  {fp:>6}")


def find_ready_runs(runs_dir: Path) -> list[Path]:
    """Runs que tienen ambas evaluaciones en todos sus session files y aún no tienen run.md."""
    if not runs_dir.exists():
        return []
    ready = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        if (d / "run.md").exists():
            continue
        has_any = False
        for sf in d.rglob("*.md"):
            if sf.name in ("run.md",):
                continue
            has_any = True
            break
        if has_any:
            ready.append(d)
    return ready


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard build_report")
    parser.add_argument("--run", dest="run_path", metavar="PATH",
                        help="Run Folder específico (implica --force)")
    parser.add_argument("--force", action="store_true",
                        help="Regenera run.md + run.json aunque ya existan")
    args = parser.parse_args()

    _flush(SEP2)
    _flush("  📊 PromptGuard · Build Report")
    _flush(SEP2)

    _flush("  Cargando fixtures...")
    all_fixtures = load_prompts(kind=None)
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
        run_folders = find_ready_runs(RUNS_DIR) if not force else sorted(
            d for d in RUNS_DIR.iterdir() if d.is_dir()
        ) if RUNS_DIR.exists() else []

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
    _flush("  ✅ Build Report completado.")
    _flush(SEP2)


if __name__ == "__main__":
    main()
