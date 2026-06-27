#!/usr/bin/env python3
"""Ejecuta la suite completa de fixtures contra Clara y genera un Run Report.

Corre los tres kinds (attack-prompts, legitimate-prompts, navi-prompts) en
una sola pasada. El Verdict de cada fixture se calcula con sus propios
indicators.success / indicators.blocked definidos en el YAML.

Salida:
  lab/audit/runs/{timestamp}_run.json  — datos estructurados
  lab/audit/runs/{timestamp}_run.md    — resumen legible

Uso:
  python run_attack_suite.py                        # todo el catálogo
  python run_attack_suite.py --kind attack-prompts  # solo ataques
  python run_attack_suite.py --type DIRECT_INJECTION
  python run_attack_suite.py --id atk_001
  python run_attack_suite.py --concurrency 3        # para OpenRouter
  python run_attack_suite.py --user usr_002
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts

API_BASE = "http://localhost:8000"
RUNS_DIR = HERE.parent / "audit" / "runs"

ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]

# Verdict values
SUCCESS = "SUCCESS"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Verdict calculation
# ---------------------------------------------------------------------------

def _verdict(fixture: dict, response: str, error: str | None) -> tuple[str, list[str]]:
    """Calcula el Verdict comparando la respuesta con los fixture indicators."""
    if error:
        return UNKNOWN, [f"error: {error}"]

    resp_lower = response.lower()
    indicators: dict = fixture.get("indicators") or {}
    matched: list[str] = []

    for kw in indicators.get("success", []):
        if kw.lower() in resp_lower:
            matched.append(f"success indicator: «{kw}»")

    if matched:
        return SUCCESS, matched

    for kw in indicators.get("blocked", []):
        if kw.lower() in resp_lower:
            matched.append(f"blocked indicator: «{kw}»")

    if matched:
        return BLOCKED, matched

    return UNKNOWN, ["no indicators matched"]


# ---------------------------------------------------------------------------
# Single fixture execution
# ---------------------------------------------------------------------------

async def _run_fixture(
    client: httpx.AsyncClient,
    fixture: dict,
    user_id: str,
    semaphore: asyncio.Semaphore,
    api_base: str = API_BASE,
) -> dict:
    async with semaphore:
        start = time.time()
        session_id = f"suite_{fixture['id']}_{int(start)}"
        steps_out: list[dict] = []
        last_response = ""
        last_error: str | None = None
        all_tools: list = []

        try:
            for step in fixture.get("rendered_steps", []):
                body = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": step.get("content", ""),
                    "fixture_id": fixture.get("id"),
                    "fixture_kind": fixture.get("kind"),
                    "fixture_expected_result": fixture.get("expected_result"),
                }
                resp = await client.post(
                    f"{api_base}/api/v1/chat", json=body, timeout=90.0
                )
                data = resp.json()
                last_response = data.get("response", "")
                last_error = data.get("error") or None
                tools = data.get("tools_used") or []
                all_tools.extend(tools)
                steps_out.append({
                    "step": step.get("step", len(steps_out) + 1),
                    "message": step.get("content", "")[:200],
                    "response": last_response[:300],
                    "tools": tools,
                    "latency_ms": data.get("latency_ms", 0),
                    "error": last_error,
                    "audit_file": data.get("audit_file"),
                })

        except Exception as exc:
            last_error = str(exc)
            steps_out.append({"error": last_error})

        latency_ms = (time.time() - start) * 1000
        verdict, matched = _verdict(fixture, last_response, last_error)

        return {
            "id": fixture.get("id"),
            "name": fixture.get("name"),
            "kind": fixture.get("kind"),
            "category": fixture.get("category"),
            "attack": fixture.get("attack"),
            "attack_type": fixture.get("attack_type"),
            "severity": fixture.get("severity"),
            "expected_result": fixture.get("expected_result"),
            "variant": fixture.get("variant", {}),
            "verdict": verdict,
            "matched_indicators": matched,
            "latency_ms": round(latency_ms, 1),
            "tools_used": all_tools,
            "steps": steps_out,
            "session_id": session_id,
        }


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _build_json(results: list[dict], model_info: dict, run_ts: str) -> dict:
    total = len(results)
    by_kind: dict[str, dict] = {}
    by_category: dict[str, dict] = {}

    for r in results:
        kind = r["kind"] or "unknown"
        cat = r["category"] or "unknown"
        verdict = r["verdict"]

        for bucket, key in [(by_kind, kind), (by_category, cat)]:
            if key not in bucket:
                bucket[key] = {"total": 0, "SUCCESS": 0, "BLOCKED": 0, "UNKNOWN": 0, "latency_ms": []}
            bucket[key]["total"] += 1
            bucket[key][verdict] += 1
            bucket[key]["latency_ms"].append(r["latency_ms"])

    def _avg(lst): return round(sum(lst) / len(lst), 1) if lst else 0

    for b in list(by_kind.values()) + list(by_category.values()):
        b["avg_latency_ms"] = _avg(b.pop("latency_ms"))

    attacks = [r for r in results if r["kind"] == "attack-prompts"]
    legit   = [r for r in results if r["kind"] == "legitimate-prompts"]
    navi    = [r for r in results if r["kind"] == "navi-prompts"]

    return {
        "run_timestamp": run_ts,
        "model": model_info,
        "summary": {
            "total_fixtures": total,
            "attack_success_rate": round(
                sum(1 for r in attacks if r["verdict"] == SUCCESS) / len(attacks) * 100, 1
            ) if attacks else None,
            "legitimate_false_positive_rate": round(
                sum(1 for r in legit if r["verdict"] == BLOCKED) / len(legit) * 100, 1
            ) if legit else None,
            "navi_self_block_rate": round(
                sum(1 for r in navi if r["verdict"] == BLOCKED) / len(navi) * 100, 1
            ) if navi else None,
            "avg_latency_ms": _avg([r["latency_ms"] for r in results]),
        },
        "by_kind": by_kind,
        "by_category": by_category,
        "fixtures": results,
    }


def _build_md(data: dict) -> str:
    s = data["summary"]
    ts = data["run_timestamp"]
    model = data["model"]
    lines: list[str] = []

    lines += [
        f"# Suite Run — {ts}",
        "",
        "## Contexto",
        "",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Timestamp | `{ts}` |",
        f"| Proveedor | `{model.get('provider', '?')}` |",
        f"| Modelo | `{model.get('model', '?')}` |",
        f"| Total fixtures | {s['total_fixtures']} |",
        "",
        "## Resumen de métricas",
        "",
        "| Métrica | Valor |",
        "|---------|-------|",
    ]

    if s["attack_success_rate"] is not None:
        lines.append(f"| Tasa de éxito de ataques | **{s['attack_success_rate']}%** |")
    if s["legitimate_false_positive_rate"] is not None:
        lines.append(f"| Falsos positivos (legítimos bloqueados) | {s['legitimate_false_positive_rate']}% |")
    if s["navi_self_block_rate"] is not None:
        lines.append(f"| Auto-bloqueo naïve | {s['navi_self_block_rate']}% |")
    lines.append(f"| Latencia media | {s['avg_latency_ms']} ms |")

    lines += ["", "## Por categoría OWASP", ""]
    lines += ["| Categoría | Total | SUCCESS | BLOCKED | UNKNOWN | Latencia media |",
              "|-----------|-------|---------|---------|---------|----------------|"]
    for cat, b in sorted(data["by_category"].items()):
        lines.append(
            f"| {cat} | {b['total']} | {b['SUCCESS']} | {b['BLOCKED']} | {b['UNKNOWN']} | {b['avg_latency_ms']} ms |"
        )

    lines += ["", "## Por kind", ""]
    lines += ["| Kind | Total | SUCCESS | BLOCKED | UNKNOWN |",
              "|------|-------|---------|---------|---------|"]
    for kind, b in data["by_kind"].items():
        lines.append(f"| {kind} | {b['total']} | {b['SUCCESS']} | {b['BLOCKED']} | {b['UNKNOWN']} |")

    lines += ["", "## Detalle por fixture", ""]
    for r in data["fixtures"]:
        icon = "🔴" if r["verdict"] == SUCCESS else ("🟢" if r["verdict"] == BLOCKED else "🟡")
        exp = r.get("expected_result", "")
        match_icon = ""
        if exp == "BLOCK" and r["verdict"] == BLOCKED:
            match_icon = " ✅"
        elif exp == "ALLOW" and r["verdict"] == SUCCESS:
            match_icon = " ✅"
        elif r["verdict"] == UNKNOWN:
            match_icon = " ❓"
        else:
            match_icon = " ❌"

        lines.append(
            f"- {icon} **`{r['id']}`** `{r['name']}`{match_icon} "
            f"· {r['kind']} · {r['severity']} · {r['verdict']} "
            f"· {r['latency_ms']:.0f}ms"
        )
        for ind in r["matched_indicators"]:
            lines.append(f"  - _{ind}_")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    parser = argparse.ArgumentParser(description="PromptGuard suite runner")
    parser.add_argument("--kind", choices=ALL_KINDS, help="Ejecutar solo este kind")
    parser.add_argument("--type", dest="attack_type", help="Filtrar por attack_type")
    parser.add_argument("--id", dest="fixture_id", help="Ejecutar un fixture concreto")
    parser.add_argument("--user", default="usr_001")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--api", default=API_BASE, help="Base URL del backend")
    parser.add_argument("--no-save", action="store_true", help="No guardar Run Report en disco")
    args = parser.parse_args()

    api_base = args.api

    kinds = [args.kind] if args.kind else ALL_KINDS
    fixtures: list[dict] = []
    for k in kinds:
        fixtures.extend(
            load_prompts(kind=k, attack_type=args.attack_type, prompt_id=args.fixture_id)
        )

    if not fixtures:
        print("No se encontraron fixtures con los filtros indicados.", file=sys.stderr)
        sys.exit(1)

    # Fetch model info
    model_info: dict = {}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{api_base}/api/v1/health/llm", timeout=5.0)
            d = r.json()
            model_info = {"provider": d.get("provider"), "model": d.get("configured_model")}
        except Exception:
            model_info = {"provider": "unknown", "model": "unknown"}

    print(f"🎯 Suite Run — {len(fixtures)} fixtures · concurrencia {args.concurrency}")
    print(f"   Modelo: {model_info.get('model')} ({model_info.get('provider')})")
    print()

    semaphore = asyncio.Semaphore(args.concurrency)
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    results: list[dict] = []

    async with httpx.AsyncClient() as client:
        tasks = [_run_fixture(client, f, args.user, semaphore, api_base) for f in fixtures]
        for coro in asyncio.as_completed(tasks):
            r = await coro
            results.append(r)
            icon = "🔴" if r["verdict"] == SUCCESS else ("🟢" if r["verdict"] == BLOCKED else "🟡")
            print(f"  {icon} [{r['id']}] {r['name']} — {r['verdict']} ({r['latency_ms']:.0f}ms)")

    # Sort results to match fixture order
    id_order = {f["id"]: i for i, f in enumerate(fixtures)}
    results.sort(key=lambda r: id_order.get(r["id"], 9999))

    run_data = _build_json(results, model_info, run_ts)
    md_text = _build_md(run_data)

    # Print summary
    s = run_data["summary"]
    print()
    print("=" * 60)
    print(f"  Total: {s['total_fixtures']} fixtures")
    if s["attack_success_rate"] is not None:
        print(f"  Tasa de éxito ataques:   {s['attack_success_rate']}%")
    if s["legitimate_false_positive_rate"] is not None:
        print(f"  Falsos positivos:         {s['legitimate_false_positive_rate']}%")
    if s["navi_self_block_rate"] is not None:
        print(f"  Auto-bloqueo naïve:       {s['navi_self_block_rate']}%")
    print(f"  Latencia media:           {s['avg_latency_ms']} ms")
    print("=" * 60)

    if not args.no_save:
        RUNS_DIR.mkdir(parents=True, exist_ok=True)
        ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        json_path = RUNS_DIR / f"{ts_file}_run.json"
        md_path   = RUNS_DIR / f"{ts_file}_run.md"
        json_path.write_text(json.dumps(run_data, indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(md_text, encoding="utf-8")
        print(f"\n  📁 JSON: {json_path.relative_to(HERE.parent.parent)}")
        print(f"  📄 MD:   {md_path.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    asyncio.run(main())
