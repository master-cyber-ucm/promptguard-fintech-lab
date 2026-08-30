#!/usr/bin/env python3
"""Evalúa los Session Files de un Run Folder con la nueva estructura de evaluación.

Lee cada Session File, aplica el evaluador definido en el bloque `evaluation:`
del fixture correspondiente (deterministic o llm) y añade ## Evaluación · al fichero.

Uso:
  python scripts/evaluate.py                               # runs pendientes
  python scripts/evaluate.py --run audit/runs/20260628_X/  # run específico (--force implícito)
  python scripts/evaluate.py --force                        # re-evalúa todos

Variables de entorno para el evaluador LLM:
  JUDGE_BASE_URL   (default: http://localhost:11434)
  JUDGE_MODEL      (default: qwen3.5:9b)
  JUDGE_TIMEOUT    (default: 60)
  JUDGE_API_FORMAT ollama | openai  (default: ollama)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts
from evaluations import EvaluationContext, evaluator_from_fixture

RUNS_DIR = HERE.parent / "audit" / "runs"
EVAL_MARKER = "## Evaluación ·"
EVAL_COMMENT = "<!-- eval:"

# ──────────────────────────────────────────────────────────────────────────────
# User context lookup
# ──────────────────────────────────────────────────────────────────────────────

_USER_CTX = {
    "usr_001":   "user_id=usr_001, nombre=María García López, cuenta=ES9121000418450200051332",
    "usr_002":   "user_id=usr_002, nombre=Carlos Rodríguez Martín, cuenta=ES7621000418450200051333",
    "usr_003":   "user_id=usr_003, nombre=Ana Fernández Ruiz, cuenta=ES3421000418450200051334",
    "usr_admin": "user_id=usr_admin, nombre=Admin Banco, cuenta=ES5821000418450200051335",
}


def _user_context(user_id: str) -> str | None:
    ctx = _USER_CTX.get(user_id)
    return f"[Contexto del usuario autenticado: {ctx}]" if ctx else None


# ──────────────────────────────────────────────────────────────────────────────
# Session file parsing
# ──────────────────────────────────────────────────────────────────────────────

_FIXTURE_RE       = re.compile(r'\*\*Fixture\*\*:\s*`([^`]+)`\s*·\s*([^\s·]+)\s*·\s*expected:\s*`([^`]+)`')
# Captura el contenido entre la fence de apertura de "### Respuesta" y la fence de
# cierre que precede al siguiente encabezado de sección (### / ## / --- / EOF).
# El lookahead evita truncar respuestas que contienen fences de código anidadas.
_RESPONSE_RE      = re.compile(
    r'### Respuesta\s+```[^\n]*\n(.*?)\n```(?=\s*(?:#{2,3}\s|---|\Z))',
    re.DOTALL,
)
_SYSTEM_PROMPT_RE = re.compile(r'### System Prompt\s+```\s*(.*?)\s*```', re.DOTALL)
_USER_RE          = re.compile(r'\| Usuario \| `([^`]+)` \|')
_TOOL_BLOCK_RE    = re.compile(r'### Tools invocadas\s+(.*?)(?=\n###|\Z)', re.DOTALL)
_TOOL_ENTRY_RE    = re.compile(
    r'-\s+\*\*`([^`]+)`\*\*'
    r'(?:\s+-\s+args:\s+`({.*?})`)?'
    r'(?:\s+-\s+resultado:\s+`({.*?})`)?',
    re.DOTALL,
)
# Cuando una guardia de salida (Output Auditor, Leak Guard, PII Shield) sustituye la
# respuesta antes de enviarla al cliente, `append_turn` conserva a propósito el texto
# CRUDO en el Session File (trazabilidad forense, ver core/leak_guard.py) con esta
# etiqueta delante. Ese texto NO es lo que recibió el cliente — response=response_text
# en chat.py ya es la versión redactada. Si el evaluador aplica response_contains sobre
# el log crudo, confunde "la guardia bloqueó" con "hubo fuga real".
_GUARD_MARKER_RE = re.compile(
    r'^\[(?:GUARDIA DE SALIDA ACTIVADA|PII SHIELD)\b[^\]]*\]\s*\n?',
    re.IGNORECASE,
)
_GUARD_REDACTED_PLACEHOLDER = (
    "[[respuesta sustituida por una guardia de salida antes de llegar al cliente — "
    "ver Session File para el detalle crudo]]"
)


def _redact_guard_logged_response(raw: str) -> tuple[str, bool]:
    """Si `raw` está marcado como sustituido por una guardia de salida, devuelve un
    marcador neutro en su lugar (para que los evaluadores no vean el secreto crudo)
    y señala que una guardia disparó en este turno."""
    if _GUARD_MARKER_RE.match(raw):
        return _GUARD_REDACTED_PLACEHOLDER, True
    return raw, False


def _parse_tools(text: str) -> list[dict]:
    # Acumula las tools de TODOS los turnos (cada turno tiene su propio bloque
    # "### Tools invocadas"). En fixtures multi-step, una tool invocada en el
    # turno 2+ debe contar igual que la del turno 1.
    tools = []
    for m in _TOOL_BLOCK_RE.finditer(text):
        for tm in _TOOL_ENTRY_RE.finditer(m.group(1)):
            try:
                args = json.loads(tm.group(2)) if tm.group(2) else {}
            except json.JSONDecodeError:
                args = {}
            try:
                result = json.loads(tm.group(3)) if tm.group(3) else {}
            except json.JSONDecodeError:
                result = {}
            # El Session File serializa args y resultado como dos entradas con el
            # mismo nombre de tool. Se recombinan aquí para que un resultado
            # ``denied`` quede asociado a los argumentos que el Gatekeeper negó.
            if result and not args and tools and tools[-1]["tool"] == tm.group(1) and not tools[-1]["result"]:
                tools[-1]["result"] = result
            else:
                tools.append({"tool": tm.group(1), "args": args, "result": result})
    return tools


def parse_session_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = _FIXTURE_RE.search(text)
    if not m:
        return None
    fixture_id, fixture_kind, expected_result = m.groups()

    # Une la respuesta de TODOS los turnos: en un ataque multi-step la brecha puede
    # producirse en cualquier turno (p.ej. volcado en T1, transferencia en T2), y un
    # evento response_contains debe dispararse aunque el indicador no esté en el último.
    raw_matches = [r.strip() for r in _RESPONSE_RE.findall(text)]
    response_matches = []
    guard_fired = False
    for raw in raw_matches:
        redacted, fired = _redact_guard_logged_response(raw)
        response_matches.append(redacted)
        guard_fired = guard_fired or fired
    combined_response = "\n\n".join(response_matches)
    
    sp_m = _SYSTEM_PROMPT_RE.search(text)
    system_prompt = sp_m.group(1).strip() if sp_m else None

    user_m = _USER_RE.search(text)
    user_id = user_m.group(1) if user_m else "usr_001"

    return {
        "fixture_id":      fixture_id,
        "fixture_kind":    fixture_kind,
        "expected_result": expected_result,
        "response":        combined_response,
        "last_response":   response_matches[-1] if response_matches else "",
        "tools":           _parse_tools(text),
        "system_prompt":   system_prompt,
        "user_id":         user_id,
        "path":            path,
        "guard_fired":     guard_fired,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Eval section management
# ──────────────────────────────────────────────────────────────────────────────

_STRIP_PREFIXES = [
    "\n---\n\n## Evaluación ·",
    "\n---\n\n## Evaluación Determinista",
    "\n---\n\n## Evaluación Juez",
]


def _strip_evals(text: str) -> str:
    indices = [text.find(p) for p in _STRIP_PREFIXES if text.find(p) != -1]
    return text[:min(indices)] if indices else text


def has_eval(path: Path) -> bool:
    # Una sesión cuenta como evaluada solo si tiene el marcador legible por máquina
    # que consume el reporte. Los bloques heurísticos antiguos (## Evaluación ·) sin
    # este comentario NO cuentan, evitando que queden fuera del run.json.
    return EVAL_COMMENT in path.read_text(encoding="utf-8")


def append_eval(
    path: Path,
    *,
    fixture_id: str,
    fixture_kind: str,
    expected_result: str,
    method: str,
    verdict: str,
    passed: bool,
    detail: str | None,
) -> None:
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    icon = "✅" if passed else "❌"

    data = {
        "fixture_id":      fixture_id,
        "fixture_kind":    fixture_kind,
        "expected_result": expected_result,
        "method":          method,
        "verdict":         verdict,
        "passed":          passed,
        "detail":          detail or "",
    }

    lines = [
        "",
        "---",
        "",
        f"## Evaluación · {ts}",
        "",
        f"<!-- eval: {json.dumps(data, ensure_ascii=False)} -->",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| Fixture | `{fixture_id}` |",
        f"| Kind | {fixture_kind} |",
        f"| Expected | `{expected_result}` |",
        f"| Método | {method} |",
        f"| Verdict | **{verdict}** {icon} |",
        "",
        f"**Detalle:** {detail[:300] if detail else '—'}",
        "",
    ]

    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Run processing
# ──────────────────────────────────────────────────────────────────────────────

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


async def process_run(
    run_folder: Path,
    *,
    force: bool,
    fixture_by_id: dict,
    client: httpx.AsyncClient,
) -> None:
    _flush(f"\n  📂 {run_folder.name}")
    _flush(SEP)

    ep_dirs = sorted(d for d in run_folder.iterdir() if d.is_dir())
    if not ep_dirs:
        _flush("  ⚠ Sin subcarpetas de endpoint — skipping")
        return

    for ep_dir in ep_dirs:
        session_files = sorted(ep_dir.glob("*.md"))
        if not session_files:
            continue
        _flush(f"\n  Endpoint: {ep_dir.name} ({len(session_files)} session files)")

        for sf in session_files:
            if not force and has_eval(sf):
                _flush(f"  ↷  {sf.name} — ya evaluado, skip")
                continue

            parsed = parse_session_file(sf)
            if parsed is None:
                _flush(f"  ⚠ {sf.name} — sin metadatos de fixture")
                continue

            fixture = fixture_by_id.get(parsed["fixture_id"])
            if fixture is None:
                _flush(f"  ⚠ {parsed['fixture_id']} — fixture no encontrado en librería")
                continue

            if not parsed["response"]:
                _flush(f"  ⚠ {parsed['fixture_id']} — sin respuesta, skip")
                continue

            # Strip old eval sections before appending new one
            text = sf.read_text(encoding="utf-8")
            cleaned = _strip_evals(text)
            if cleaned != text:
                sf.write_text(cleaned, encoding="utf-8")

            method = (fixture.get("evaluation") or {}).get("method", "deterministic")
            evaluator = evaluator_from_fixture(fixture)
            ctx = EvaluationContext(
                response=parsed["response"],
                tools=parsed["tools"],
                expected_result=parsed["expected_result"],
                system_prompt=parsed["system_prompt"],
                user_context=_user_context(parsed["user_id"]),
                client=client,
            )
            result = await evaluator.evaluate(ctx)

            icon = "✅" if result.passed else "❌"
            _flush(f"  {icon}  {parsed['fixture_id']:<35} {result.verdict:<8}  [{method}]")

            append_eval(
                sf,
                fixture_id=parsed["fixture_id"],
                fixture_kind=parsed["fixture_kind"],
                expected_result=parsed["expected_result"],
                method=method,
                verdict=result.verdict,
                passed=result.passed,
                detail=result.detail,
            )


def find_pending_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    pending = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        for sf in d.rglob("*.md"):
            if sf.name == "run.md":
                continue
            if not has_eval(sf):
                pending.append(d)
                break
    return pending


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard · evaluate")
    parser.add_argument("--run", dest="run_path", metavar="PATH",
                        help="Run Folder específico (implica --force)")
    parser.add_argument("--force", action="store_true",
                        help="Re-evalúa aunque ya exista sección de Evaluación")
    args = parser.parse_args()

    _flush(SEP2)
    _flush("  🔍 PromptGuard · Evaluación")
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
            run_folders = find_pending_runs(RUNS_DIR)

    if not run_folders:
        _flush("  No hay runs pendientes.")
        return

    _flush(f"  {len(run_folders)} run(s) a procesar:")
    for rf in run_folders:
        _flush(f"    · {rf.name}")

    async with httpx.AsyncClient() as client:
        for run_folder in run_folders:
            await process_run(run_folder, force=force, fixture_by_id=fixture_by_id, client=client)

    _flush("")
    _flush(SEP2)
    _flush("  ✅ Evaluación completada.")
    _flush(SEP2)
    _flush("")
    _flush("  Siguiente: python scripts/report.py")


if __name__ == "__main__":
    asyncio.run(main())
