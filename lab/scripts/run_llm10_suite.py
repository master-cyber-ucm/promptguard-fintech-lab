#!/usr/bin/env python3
"""Suite de ataques LLM10:2025 — Unbounded Consumption (#8 Denegación de Servicio,
#9 Denial of Wallet).

Mismo patrón que `run_attack_suite.py` (envía peticiones al backend, persiste
evidencia), pero los escenarios de `llm10_scenarios.yaml` no son un payload de texto
único — son un patrón de volumen/tasa. Cada `type` tiene su propia lógica de ejecución:

  flood        → dispara `n_requests` peticiones (con `concurrency` simultáneas) y
                 cuenta cuántas quedan ALLOW vs BLOCKED_BY_RATE_LIMITER.
  token_burn   → una sola petición con un prompt diseñado para maximizar la longitud
                 de la respuesta; mide la longitud real obtenida.
  budget_burn  → dispara `n_requests` peticiones secuenciales con el MISMO user_id y
                 cuenta cuántas pasan antes de que el Budget Guard corte.

Uso:
  python run_llm10_suite.py --vulnerable          # línea base — todas las defensas de
                                                    # infraestructura desactivadas
  python run_llm10_suite.py                        # defendido — comportamiento por defecto
  python run_llm10_suite.py --id llm10_001         # un escenario concreto
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

import httpx
import yaml

HERE = Path(__file__).resolve().parent
# En Docker los fixtures están montados en /app/tests; fuera del contenedor se
# conservan bajo lab/backend/tests. La variable permite usar ambos contextos.
FIXTURES_DIR = Path(os.environ.get("FIXTURES_DIR", str(HERE.parent / "backend" / "tests" / "fixtures")))
RUNS_DIR = HERE.parent / "audit" / "runs"
AUDIT_RUNS_DIR_CONTAINER = "/app/audit/runs"


def cargar_escenarios(id_filtro: str | None = None) -> list[dict]:
    data = yaml.safe_load((FIXTURES_DIR / "llm10_scenarios.yaml").read_text(encoding="utf-8"))
    escenarios = data["scenarios"]
    if id_filtro:
        escenarios = [e for e in escenarios if e["id"] == id_filtro]
    return escenarios


def _flush(text: str) -> None:
    print(text, flush=True)


async def _un_intento(
    client: httpx.AsyncClient, api_base: str, endpoint: str, mensaje: str,
    user_id: str, vulnerable: bool, audit_subdir: str,
) -> dict:
    t0 = time.time()
    try:
        resp = await client.post(
            f"{api_base}/chat/{endpoint}",
            json={
                "user_id": user_id, "message": mensaje, "vulnerable": vulnerable,
                "audit_subdir": audit_subdir,
            },
            timeout=180.0,
        )
        data = resp.json()
    except Exception as exc:
        return {"error": str(exc), "response": "", "latency_ms": (time.time() - t0) * 1000}
    data["latency_ms_medida"] = (time.time() - t0) * 1000
    return data


async def _ejecutar_flood(escenario: dict, client: httpx.AsyncClient, api_base: str, vulnerable: bool, audit_subdir: str, user_id: str) -> dict:
    n = escenario["params"]["n_requests"]
    concurrencia = escenario["params"].get("concurrency", 1)
    endpoint = escenario["endpoint"]
    mensaje = escenario["message"]

    resultados: list[dict] = []
    sem = asyncio.Semaphore(concurrencia)

    async def _tarea():
        async with sem:
            return await _un_intento(client, api_base, endpoint, mensaje, user_id, vulnerable, audit_subdir)

    resultados = await asyncio.gather(*[_tarea() for _ in range(n)])
    bloqueadas = sum(1 for r in resultados if "RATE_LIMITER" in (r.get("error") or ""))
    permitidas = n - bloqueadas
    return {
        "n_requests": n, "concurrency": concurrencia,
        "permitidas": permitidas, "bloqueadas": bloqueadas,
        "veredicto": "BLOCKED" if bloqueadas > 0 else "ALLOW",
    }


async def _ejecutar_token_burn(escenario: dict, client: httpx.AsyncClient, api_base: str, vulnerable: bool, audit_subdir: str, user_id: str) -> dict:
    resultado = await _un_intento(client, api_base, escenario["endpoint"], escenario["message"], user_id, vulnerable, audit_subdir)
    respuesta = resultado.get("response", "") or ""
    return {
        "longitud_respuesta_caracteres": len(respuesta),
        "error": resultado.get("error"),
        "preview": respuesta[:200],
        # Umbral calibrado empíricamente contra el prompt de este escenario (ver
        # validación histórica de LLM10): sin cap, la respuesta
        # natural de qwen2.5:3b para este prompt son ~3800 caracteres; con
        # CLARA_MAX_OUTPUT_TOKENS bajado a un valor pequeño para la demo, se trunca muy
        # por debajo. 2000 separa ambos casos con margen.
        "veredicto": "BLOCKED" if len(respuesta) < 2000 else "ALLOW",
    }


async def _ejecutar_budget_burn(escenario: dict, client: httpx.AsyncClient, api_base: str, vulnerable: bool, audit_subdir: str, user_id: str) -> dict:
    n = escenario["params"]["n_requests"]
    mensaje = escenario["message"]
    endpoint = escenario["endpoint"]
    intentos_hasta_corte = None
    for i in range(1, n + 1):
        resultado = await _un_intento(client, api_base, endpoint, mensaje, user_id, vulnerable, audit_subdir)
        if "BUDGET_GUARD" in (resultado.get("error") or ""):
            intentos_hasta_corte = i
            break
    return {
        "n_requests_planeadas": n,
        "intentos_hasta_corte": intentos_hasta_corte,
        "veredicto": "BLOCKED" if intentos_hasta_corte is not None else "ALLOW",
    }


EJECUTORES = {"flood": _ejecutar_flood, "token_burn": _ejecutar_token_burn, "budget_burn": _ejecutar_budget_burn}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Suite de ataques LLM10:2025 (Unbounded Consumption)")
    parser.add_argument("--vulnerable", action="store_true", help="Línea base sin defensas de infraestructura")
    parser.add_argument("--id", dest="escenario_id", help="Ejecutar un escenario concreto")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--user", default="usr_001")
    args = parser.parse_args()

    api_base = f"http://{args.host}:{args.port}/api/v1"
    escenarios = cargar_escenarios(args.escenario_id)

    ts = time.strftime("%Y%m%d_%H%M%S")
    etiqueta = "vulnerable" if args.vulnerable else "defendido"
    run_folder_name = f"{ts}_llm10-{etiqueta}"
    audit_subdir = f"{AUDIT_RUNS_DIR_CONTAINER}/{run_folder_name}"

    _flush(f"═══ Suite LLM10 — {etiqueta} — {len(escenarios)} escenario(s) ═══")

    resultados_run: dict = {"run_folder": run_folder_name, "vulnerable": args.vulnerable, "escenarios": {}}
    async with httpx.AsyncClient() as client:
        for escenario in escenarios:
            ejecutor = EJECUTORES[escenario["type"]]
            _flush(f"\n── {escenario['id']} — {escenario['name']} ({escenario['type']}) ──")
            t0 = time.time()
            resultado = await ejecutor(escenario, client, api_base, args.vulnerable, audit_subdir, args.user)
            resultado["duracion_s"] = round(time.time() - t0, 2)
            resultado["expected_result"] = escenario["expected_result"]
            resultado["coincide_con_esperado"] = resultado["veredicto"] == escenario["expected_result"]
            resultados_run["escenarios"][escenario["id"]] = resultado
            marca = "✓" if resultado["coincide_con_esperado"] else "⚠"
            _flush(f"  {marca} veredicto={resultado['veredicto']} esperado={escenario['expected_result']} ({resultado['duracion_s']}s)")

    run_folder = RUNS_DIR / run_folder_name
    run_folder.mkdir(parents=True, exist_ok=True)
    (run_folder / "run.json").write_text(json.dumps(resultados_run, indent=2, ensure_ascii=False), encoding="utf-8")
    _flush(f"\nInforme: {run_folder / 'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
