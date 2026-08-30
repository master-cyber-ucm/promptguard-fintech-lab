#!/usr/bin/env python3
"""Ejecuta la suite completa de fixtures contra los endpoints de Clara.

Envía los fixtures al backend y persiste los Session Files en el Run Folder.
No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass.

  lab/audit/runs/{timestamp}_{model}/
  ├── simple-prompt/          ← Session Files de este endpoint
  ├── complex-prompt/
  ├── complex-with-context/
  ├── complex-with-document/  ← fixtures `type: document-upload` (ataque #7, Fase 2.9)
  └── (run.md y run.json los genera `evaluate.py` + `report.py` después)

Fixtures `type: document-upload` (campo `document: <archivo>` apuntando a
henri-tfm/01-ataque/payloads/) se envían SIEMPRE a `complex-with-document` vía
multipart, nunca a los 3 endpoints JSON — y viceversa, los fixtures normales
(`steps`) nunca se envían a `complex-with-document`. No es un cruce N×M como
con los otros 3 endpoints: cada fixture tiene un único endpoint válido según
su tipo. Las 4 capas de defensa (A/B/C/D) van con su valor por defecto
(`True`, comportamiento seguro) — no hay todavía soporte para los toggles
`defensa_*` desde la suite (ver henri-tfm/ROADMAP.md §2.9.3); para eso sigue
existiendo `henri-tfm/01-ataque/evidencia/ejecutar_evidencia.py`.

Uso:
  python run_attack_suite.py                           # todos los endpoints y kinds
  python run_attack_suite.py --endpoint simple-prompt  # solo un endpoint
  python run_attack_suite.py --endpoint complex-with-document  # solo el ataque #7 real
  python run_attack_suite.py --kind attack-prompts     # solo ataques
  python run_attack_suite.py --type INDIRECT_INJECTION
  python run_attack_suite.py --id atk_035
  python run_attack_suite.py --id atk_001_admin --id leg_024 --endpoint complex-with-context --endpoint proxy --baseline-pure
  python run_attack_suite.py --repeat 5                # 5 repeticiones por fixture
  python run_attack_suite.py --proxy-profile baseline --proxy-profile gatekeeper \\
      --proxy-profile output --proxy-profile full --repeat 5
  python run_attack_suite.py --user usr_002
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts

RUNS_DIR = HERE.parent / "audit" / "runs"
# henri-tfm/ vive fuera de lab/ — HERE = lab/scripts, .parent.parent = raíz del repo.
# En local se resuelve desde la raíz del repositorio; Docker aporta la misma
# carpeta de payloads en una ruta explícita y de solo lectura.
PAYLOADS_DIR = Path(
    os.environ.get(
        "PAYLOADS_DIR",
        str(HERE.parent.parent / "henri-tfm" / "01-ataque" / "payloads"),
    )
)
# Algunos Turns llaman varias tools y cada llamada puede consumir la salida máxima
# del modelo. 90 s bastaba para una respuesta simple, pero no para esos casos y
# dejaba el trabajo del backend vivo sin que el runner esperase su Session File.
# El límite sigue siendo configurable para entornos donde se prefiera fallar antes.
REQUEST_TIMEOUT = float(os.environ.get("SUITE_REQUEST_TIMEOUT", "300"))

# El backend corre en un contenedor con ./audit:/app/audit montado (lab/docker-compose.yml).
# `audit_subdir` viaja en la petición y lo usa `append_turn()` DENTRO del contenedor — tiene que
# ser la ruta tal como la ve el contenedor, no la ruta host de este script. Bug real encontrado
# en Fase 2.9: antes se enviaba la ruta host (`str(run_folder / ep_name)`); el contenedor la creaba
# igualmente sin fallar, pero en su propio filesystem efímero — invisible y no persistente desde
# el host. Mismo bug (y mismo arreglo) que ya se había aplicado en
# henri-tfm/01-ataque/evidencia/ejecutar_evidencia.py.
AUDIT_RUNS_DIR_CONTAINER = "/app/audit/runs"

ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]

DOCUMENT_ENDPOINT_NAME = "complex-with-document"

CHAT_ENDPOINTS: dict[str, str] = {
    "simple-prompt":        "/api/v1/chat/simple-prompt",
    "complex-prompt":       "/api/v1/chat/complex-prompt",
    "complex-with-context": "/api/v1/chat/complex-with-context",
    # El pipeline completo de defensa. Sin él no hay forma de producir una corrida
    # "defendida" que comparar contra las líneas base, que es lo que la pantalla de
    # Corridas del SOC pone una al lado de la otra.
    "proxy": "/api/v1/chat/proxy",
    DOCUMENT_ENDPOINT_NAME: "/api/v1/chat/complex-with-document",
}

PROXY_PROFILES = ("baseline", "gatekeeper", "output", "full")

DOCUMENT_CONTENT_TYPES: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------------------------------------------------------------------------
# Single fixture execution
# ---------------------------------------------------------------------------

async def _run_document_fixture(
    client: httpx.AsyncClient,
    fixture: dict,
    user_id: str,
    api_base: str,
    endpoint_path: str,
    audit_subdir: str,
    *,
    repeat: int = 1,
) -> list[dict]:
    """Envía un fixture `type: document-upload` vía multipart, adjuntando el archivo real de
    `henri-tfm/01-ataque/payloads/`. Devuelve el detalle de cada repetición."""
    doc_name = fixture["document"]
    doc_path = PAYLOADS_DIR / doc_name
    if not doc_path.is_file():
        return [
            {"attempt": attempt_number, "latency_ms": 0.0, "response_preview": "",
             "error": f"Documento no encontrado: {doc_path}", "session_id": ""}
            for attempt_number in range(1, repeat + 1)
        ]
    content_type = DOCUMENT_CONTENT_TYPES.get(doc_path.suffix.lower(), "application/octet-stream")

    attempts: list[dict] = []
    for attempt_number in range(1, repeat + 1):
        # Una repetición debe producir evidencia independiente; un id único evita
        # que las cinco peticiones se agreguen en un único Session File documental.
        session_id = f"suite_{fixture['id']}_{int(time.time() * 1000)}_{attempt_number}"
        last_response = ""
        error: str | None = None
        started_at = time.time()
        try:
            with open(doc_path, "rb") as f:
                resp = await client.post(
                    f"{api_base}{endpoint_path}",
                    data={
                        "user_id": user_id,
                        "session_id": session_id,
                        "message": fixture.get("message", ""),
                        "fixture_id": fixture.get("id"),
                        "fixture_kind": fixture.get("kind"),
                        "fixture_expected_result": fixture.get("expected_result"),
                        "audit_subdir": audit_subdir,
                    },
                    files={"document": (doc_path.name, f, content_type)},
                    timeout=REQUEST_TIMEOUT,
                )
            data = resp.json()
            last_response = data.get("response", "")
            error = data.get("error") or None
        except Exception as exc:
            error = str(exc)
        attempts.append({
            "attempt": attempt_number,
            "latency_ms": round((time.time() - started_at) * 1000, 1),
            "response_preview": last_response[:120].replace("\n", " "),
            "error": error,
            "session_id": session_id,
        })

    return attempts


async def _run_fixture(
    client: httpx.AsyncClient,
    fixture: dict,
    user_id: str,
    api_base: str,
    endpoint_path: str,
    audit_subdir: str,
    *,
    repeat: int = 1,
    vulnerable: bool = False,
    proxy_profile: str | None = None,
) -> dict:
    attempts: list[dict] = []

    if fixture.get("document"):
        attempts = await _run_document_fixture(
            client, fixture, user_id, api_base, endpoint_path, audit_subdir, repeat=repeat,
        )
    else:
        for attempt_number in range(1, repeat + 1):
            # Cada --repeat arranca una conversación nueva; dentro de la misma
            # repetición, los pasos de un fixture multi-step SÍ comparten memoria
            # real (session_store.py en el backend) — el primer step no manda
            # session_id (Clara abre sesión nueva), los siguientes reutilizan el
            # id que devuelve la API.
            session_id: str | None = None
            last_response = ""
            error: str | None = None
            block_code: str | None = None
            started_at = time.time()
            try:
                for step in fixture.get("rendered_steps", []):
                    body = {
                        "user_id": user_id,
                        "message": step.get("content", ""),
                        "fixture_id": fixture.get("id"),
                        "fixture_kind": fixture.get("kind"),
                        "fixture_expected_result": fixture.get("expected_result"),
                        "audit_subdir": audit_subdir,
                        "vulnerable": vulnerable,
                    }
                    if proxy_profile:
                        body["proxy_profile"] = proxy_profile
                    if session_id:
                        body["session_id"] = session_id
                    resp = await client.post(
                        f"{api_base}{endpoint_path}", json=body, timeout=REQUEST_TIMEOUT
                    )
                    data = resp.json()
                    last_response = data.get("response", "")
                    error = data.get("error") or None
                    block_code = data.get("block_code") or None
                    returned_id = data.get("session_id")
                    if returned_id:
                        session_id = returned_id
            except Exception as exc:
                error = str(exc)
            attempts.append({
                "attempt": attempt_number,
                "latency_ms": round((time.time() - started_at) * 1000, 1),
                "response_preview": last_response[:120].replace("\n", " "),
                "error": error,
                "block_code": block_code,
                "session_id": session_id or "",
            })

    outcomes = Counter(_attempt_outcome(attempt) for attempt in attempts)
    last_attempt = attempts[-1]
    return {
        "id": fixture.get("id"),
        "name": fixture.get("name"),
        "kind": fixture.get("kind"),
        "latency_ms": round(sum(attempt["latency_ms"] for attempt in attempts), 1),
        "response_preview": last_attempt["response_preview"],
        "error": last_attempt["error"],
        "session_id": last_attempt["session_id"],
        "attempts": attempts,
        "outcomes": dict(outcomes),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


def _attempt_outcome(attempt: dict) -> str:
    """Clasifica un intento sin confundir un bloqueo esperado con un fallo técnico."""
    if attempt.get("block_code"):
        return "blocked"
    error = attempt.get("error") or ""
    if not error:
        return "ok"
    if error.startswith("BLOCKED_BY_"):
        return "blocked"
    return "error"


def _repeat_log_summary(result: dict) -> str:
    """Resumen compacto y completo de todos los intentos de un endpoint."""
    attempts = result["attempts"]
    total = len(attempts)
    outcomes = Counter(_attempt_outcome(attempt) for attempt in attempts)
    latencies = [attempt["latency_ms"] for attempt in attempts]
    latency = f"{min(latencies):.0f}–{max(latencies):.0f}ms"
    parts = [f"✓ {outcomes['ok']}/{total}"]
    if outcomes["blocked"]:
        parts.append(f"BLOQUEADO {outcomes['blocked']}/{total}")
    if outcomes["error"]:
        parts.append(f"ERROR {outcomes['error']}/{total}")
    return " · ".join(parts) + f"  {latency}"


async def main():
    global REQUEST_TIMEOUT
    parser = argparse.ArgumentParser(description="PromptGuard suite runner")
    parser.add_argument("--kind", choices=ALL_KINDS, help="Ejecutar solo este kind")
    parser.add_argument("--type", dest="attack_type", help="Filtrar por attack_type")
    parser.add_argument(
        "--id", dest="fixture_ids", action="append", metavar="FIXTURE_ID",
        help="Ejecutar un fixture concreto; se puede repetir para una corrida curada",
    )
    parser.add_argument(
        "--proxy-profile",
        choices=PROXY_PROFILES,
        action="append",
        dest="proxy_profiles",
        metavar="PROFILE",
        help=(
            "Ejecuta el endpoint proxy con uno o varios perfiles experimentales. "
            "baseline=sin defensas; gatekeeper=autorización; output=gatekeeper+controles "
            "de salida; full=proxy completo. Sin este flag se conserva el proxy normal."
        ),
    )
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
    parser.add_argument(
        "--timeout", type=float, default=REQUEST_TIMEOUT, metavar="SEGUNDOS",
        help=(
            "Timeout por petición HTTP al backend (default: %(default)s). "
            "Auméntalo para fixtures que requieren varias tools."
        ),
    )
    parser.add_argument(
        "--resume-run", metavar="RUN_FOLDER",
        help=(
            "Reanudar una corrida en lab/audit/runs/<RUN_FOLDER>. Solo admite el "
            "nombre de carpeta; útil para completar combinaciones sin crear otro Run Folder."
        ),
    )
    parser.add_argument(
        "--baseline-pure", action="store_true",
        help=(
            "Envía vulnerable=true solo a endpoints JSON baseline (nunca a proxy) para "
            "comparar una línea base indefensa real con el pipeline defendido."
        ),
    )
    args = parser.parse_args()

    REQUEST_TIMEOUT = args.timeout

    api_base = f"http://{args.host}:{args.port}"

    endpoints: dict[str, str] = (
        {k: v for k, v in CHAT_ENDPOINTS.items() if k in args.endpoints}
        if args.endpoints
        else CHAT_ENDPOINTS
    )
    # La suite general conserva el directorio histórico `proxy`. Al pedir perfiles,
    # cada configuración recibe un directorio propio para que report.py no mezcle
    # resultados de posturas defensivas diferentes.
    proxy_profile_by_target: dict[str, str | None] = {name: None for name in endpoints}
    if args.proxy_profiles:
        if "proxy" not in endpoints:
            parser.error("--proxy-profile requiere incluir --endpoint proxy (o no filtrar endpoints)")
        proxy_path = endpoints.pop("proxy")
        proxy_profile_by_target.pop("proxy", None)
        for profile in dict.fromkeys(args.proxy_profiles):
            target = f"proxy-{profile}"
            endpoints[target] = proxy_path
            proxy_profile_by_target[target] = profile

    kinds = [args.kind] if args.kind else ALL_KINDS
    fixtures: list[dict] = []
    fixture_ids = args.fixture_ids or [None]
    for fixture_id in fixture_ids:
        for k in kinds:
            fixtures.extend(
                load_prompts(kind=k, attack_type=args.attack_type, prompt_id=fixture_id)
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
    if args.resume_run:
        resume_path = Path(args.resume_run)
        if resume_path.name != args.resume_run or args.resume_run in {".", ".."}:
            parser.error("--resume-run debe ser solo el nombre de un Run Folder")
        ts_file = args.resume_run
    else:
        ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{model_slug}"
    run_folder = RUNS_DIR / ts_file

    # Create run folder and endpoint/profile subdirs
    for ep_name in endpoints:
        (run_folder / ep_name).mkdir(parents=True, exist_ok=True)

    def _valid_endpoints_for(fixture: dict) -> int:
        # Cada fixture solo tiene UN endpoint válido: document-upload -> complex-with-document,
        # el resto -> los 3 endpoints JSON (nunca se cruzan, ver docstring del módulo).
        is_doc = bool(fixture.get("document"))
        applicable = fixture.get("applicable_endpoints")
        return sum(
            1
            for name in endpoints
            if (("proxy" if name.startswith("proxy-") else name) == DOCUMENT_ENDPOINT_NAME) == is_doc
            and (
                not applicable
                or ("proxy" if name.startswith("proxy-") else name) in applicable
                or name == DOCUMENT_ENDPOINT_NAME
            )
        )

    # Una ejecución es una combinación fixture-endpoint. No equivale siempre a
    # una petición HTTP: los fixtures multi-turn envían un turno por cada step.
    # Exponer ambas cifras hace que el coste de una corrida completa sea
    # auditable y evita documentar una estimación engañosa.
    total = sum(_valid_endpoints_for(f) for f in fixtures) * args.repeat
    requests_total = sum(
        _valid_endpoints_for(f)
        * (1 if f.get("document") else len(f.get("rendered_steps", [])))
        for f in fixtures
    ) * args.repeat

    _flush(SEP2)
    _flush(f"  🎯 PromptGuard Suite Run · {run_ts}")
    _flush(f"  Modelo    : {model_info.get('model')} ({model_info.get('provider')})")
    _flush(f"  Endpoints : {', '.join(endpoints)}")
    _flush(f"  Fixtures  : {len(fixtures)} · Ejecuciones totales: {total}")
    _flush(f"  Peticiones HTTP al backend: {requests_total}")
    if args.repeat > 1:
        _flush(f"  Repeticiones: {args.repeat}x por fixture")
    if args.baseline_pure:
        _flush("  Baseline  : puro (vulnerable=true solo fuera de proxy)")
    if args.proxy_profiles:
        _flush(f"  Perfiles proxy: {', '.join(dict.fromkeys(args.proxy_profiles))}")
    _flush(f"  Run Folder: {run_folder.relative_to(HERE.parent.parent)}")
    _flush(SEP2)

    # Manifiesto versionado: describe la intención experimental, no etiquetas de
    # pipeline que puedan aparecer en sesiones bloqueadas antes de invocar al LLM.
    manifest_path = run_folder / "suite-config.json"
    # Una recuperación suele ejecutar un subconjunto de targets. El manifiesto
    # debe describir la campaña completa original, no ese subconjunto; de otro
    # modo check-suite dejaría de exigir evidencia de los restantes endpoints.
    if not (args.resume_run and manifest_path.is_file()):
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "run_started_at": run_ts,
                    # `model` se conserva durante una versión para lectores históricos.
                    "model": model_info.get("model"),
                    "requested_model": model_info.get("model"),
                    "provider": model_info.get("provider"),
                    "defense_version": os.environ.get("DEFENSE_VERSION", "dev"),
                    "fixtures_sha256": hashlib.sha256(
                        json.dumps(fixtures, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest(),
                    "repeat": args.repeat,
                    "targets": list(endpoints),
                    "proxy_profiles": {
                        target: profile
                        for target, profile in proxy_profile_by_target.items()
                        if profile is not None
                    },
                    "baseline_pure": args.baseline_pure,
                    "fixture_count": len(fixtures),
                    "http_requests_expected": requests_total,
                },
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    errors = 0
    blocked = 0
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

            is_document_fixture = bool(fixture.get("document"))
            # A4: fixtures que declaran applicable_endpoints (p.ej. System Prompt Leakage
            # contra simple-prompt, que no tiene sección "Información interna" que filtrar)
            # se saltan en los endpoints donde el fixture no mide nada real — evita un
            # artefacto de medición (BLOCKED por ausencia de secreto, no por resistencia).
            applicable = fixture.get("applicable_endpoints")

            for ep_name, ep_path in endpoints.items():
                # Cada fixture solo va a su endpoint válido: document-upload -> siempre
                # complex-with-document; el resto -> nunca complex-with-document.
                canonical_endpoint = "proxy" if ep_name.startswith("proxy-") else ep_name
                if is_document_fixture != (canonical_endpoint == DOCUMENT_ENDPOINT_NAME):
                    continue
                if applicable and canonical_endpoint not in applicable and canonical_endpoint != DOCUMENT_ENDPOINT_NAME:
                    print(f"  ↳ {ep_name:<26}⏭  N/A para este fixture (applicable_endpoints)", flush=True)
                    continue

                audit_subdir = f"{AUDIT_RUNS_DIR_CONTAINER}/{ts_file}/{ep_name}"
                vulnerable = (
                    args.baseline_pure
                    and canonical_endpoint != "proxy"
                    and ep_name != DOCUMENT_ENDPOINT_NAME
                )
                print(f"  ↳ {ep_name:<26}", end="", flush=True)
                result = await _run_fixture(
                    client, fixture, args.user, api_base, ep_path, audit_subdir,
                    repeat=args.repeat,
                    vulnerable=vulnerable,
                    proxy_profile=proxy_profile_by_target.get(ep_name),
                )

                outcomes = Counter(_attempt_outcome(attempt) for attempt in result["attempts"])
                sent += outcomes["ok"]
                blocked += outcomes["blocked"]
                errors += outcomes["error"]
                summary = _repeat_log_summary(result)
                preview = result["response_preview"][:60]
                print(f"{summary}  «{preview}»", flush=True)

    _flush("")
    _flush(SEP2)
    _flush(
        f"  SUITE COMPLETADA — {sent} correctos · {blocked} bloqueados"
        f" · {errors} errores técnicos"
    )
    _flush(f"  Run Folder : {run_folder.relative_to(HERE.parent.parent)}")
    _flush(f"  Siguiente  : python scripts/evaluate.py --run {run_folder}")
    _flush(SEP2)


if __name__ == "__main__":
    asyncio.run(main())
