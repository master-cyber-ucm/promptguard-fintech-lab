#!/usr/bin/env python3
"""Ejecuta la suite completa de fixtures contra todos los endpoints de Clara.

Envía los fixtures al backend y persiste los Session Files en el Run Folder.
No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass.

  lab/audit/runs/{timestamp}_{model}/
  ├── simple-prompt/          ← Session Files de este endpoint
  ├── complex-prompt/
  ├── complex-with-context/
  └── (run.md y run.json los genera `analyze.py` después)

Uso:
  python run_attack_suite.py                           # todos los endpoints y kinds
  python run_attack_suite.py --endpoint simple-prompt  # solo un endpoint
  python run_attack_suite.py --kind attack-prompts     # solo ataques
  python run_attack_suite.py --type DIRECT_INJECTION
  python run_attack_suite.py --id atk_001
  python run_attack_suite.py --repeat 5                # 5 repeticiones por fixture
  python run_attack_suite.py --user usr_002
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts

RUNS_DIR = HERE.parent / "audit" / "runs"

ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]

CHAT_ENDPOINTS: dict[str, str] = {
    "simple-prompt":        "/api/v1/chat/simple-prompt",
    "complex-prompt":       "/api/v1/chat/complex-prompt",
    "complex-with-context": "/api/v1/chat/complex-with-context",
}


# ---------------------------------------------------------------------------
# Single fixture execution
# ---------------------------------------------------------------------------

async def _run_fixture(
    client: httpx.AsyncClient,
    fixture: dict,
    user_id: str,
    api_base: str,
    endpoint_path: str,
    audit_subdir: str,
    *,
    repeat: int = 1,
) -> dict:
    start = time.time()
    session_id = f"suite_{fixture['id']}_{int(start)}"
    error: str | None = None
    last_response = ""

    for _ in range(repeat):
        try:
            for step in fixture.get("rendered_steps", []):
                body = {
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": step.get("content", ""),
                    "fixture_id": fixture.get("id"),
                    "fixture_kind": fixture.get("kind"),
                    "fixture_expected_result": fixture.get("expected_result"),
                    "audit_subdir": audit_subdir,
                }
                resp = await client.post(
                    f"{api_base}{endpoint_path}", json=body, timeout=90.0
                )
                data = resp.json()
                last_response = data.get("response", "")
                error = data.get("error") or None
        except Exception as exc:
            error = str(exc)

    latency_ms = (time.time() - start) * 1000
    return {
        "id": fixture.get("id"),
        "name": fixture.get("name"),
        "kind": fixture.get("kind"),
        "latency_ms": round(latency_ms, 1),
        "response_preview": last_response[:120].replace("\n", " "),
        "error": error,
        "session_id": session_id,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


async def main():
    parser = argparse.ArgumentParser(description="PromptGuard suite runner")
    parser.add_argument("--kind", choices=ALL_KINDS, help="Ejecutar solo este kind")
    parser.add_argument("--type", dest="attack_type", help="Filtrar por attack_type")
    parser.add_argument("--id", dest="fixture_id", help="Ejecutar un fixture concreto")
    parser.add_argument("--user", default="usr_001")
    parser.add_argument("--host", default=os.environ.get("SUITE_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SUITE_PORT", "8000")))
    parser.add_argument(
        "--endpoint",
        choices=list(CHAT_ENDPOINTS),
        action="append",
        dest="endpoints",
        metavar="ENDPOINT",
        help=f"Endpoint(s) a usar (puede repetirse). Por defecto todos: {list(CHAT_ENDPOINTS)}",
    )
    parser.add_argument("--repeat", type=int, default=1, metavar="N",
                        help="Repetir cada fixture N veces (default: 1)")
    args = parser.parse_args()

    api_base = f"http://{args.host}:{args.port}"

    endpoints: dict[str, str] = (
        {k: v for k, v in CHAT_ENDPOINTS.items() if k in args.endpoints}
        if args.endpoints
        else CHAT_ENDPOINTS
    )

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

    run_ts    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_slug = (model_info.get("model") or "unknown").replace(":", "-").replace("/", "-")
    ts_file   = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{model_slug}"
    run_folder = RUNS_DIR / ts_file

    # Create run folder and endpoint subdirs
    for ep_name in endpoints:
        (run_folder / ep_name).mkdir(parents=True, exist_ok=True)

    total = len(fixtures) * len(endpoints) * args.repeat

    _flush(SEP2)
    _flush(f"  🎯 PromptGuard Suite Run · {run_ts}")
    _flush(f"  Modelo    : {model_info.get('model')} ({model_info.get('provider')})")
    _flush(f"  Endpoints : {', '.join(endpoints)}")
    _flush(f"  Fixtures  : {len(fixtures)} · Ejecuciones totales: {total}")
    if args.repeat > 1:
        _flush(f"  Repeticiones: {args.repeat}x por fixture")
    _flush(f"  Run Folder: {run_folder.relative_to(HERE.parent.parent)}")
    _flush(SEP2)

    errors = 0
    sent   = 0

    async with httpx.AsyncClient() as client:
        for idx, fixture in enumerate(fixtures, 1):
            fid   = fixture.get("id", "?")
            fname = fixture.get("name", "?")
            fkind = fixture.get("kind", "?")
            fsev  = fixture.get("severity", "?")

            _flush("")
            _flush(f"[{idx:>3}/{len(fixtures)}] {fid} · {fname}")
            _flush(f"          kind={fkind}  severity={fsev}")
            _flush(SEP)

            for ep_name, ep_path in endpoints.items():
                audit_subdir = str(run_folder / ep_name)
                print(f"  ↳ {ep_name:<26}", end="", flush=True)
                t0 = time.time()

                result = await _run_fixture(
                    client, fixture, args.user, api_base, ep_path, audit_subdir,
                    repeat=args.repeat,
                )

                elapsed_ms = (time.time() - t0) * 1000
                if result["error"]:
                    errors += 1
                    print(f"❌ ERROR  {elapsed_ms:>7.0f}ms  {result['error'][:60]}", flush=True)
                else:
                    sent += 1
                    preview = result["response_preview"][:60]
                    print(f"✓        {elapsed_ms:>7.0f}ms  «{preview}»", flush=True)

    _flush("")
    _flush(SEP2)
    _flush(f"  SUITE COMPLETADA — {sent} enviados · {errors} errores")
    _flush(f"  Run Folder : {run_folder.relative_to(HERE.parent.parent)}")
    _flush(f"  Siguiente  : python scripts/analyze.py --run {run_folder}")
    _flush(SEP2)


if __name__ == "__main__":
    asyncio.run(main())
