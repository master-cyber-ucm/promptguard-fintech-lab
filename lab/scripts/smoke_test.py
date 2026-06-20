#!/usr/bin/env python3
"""Verifica que el stack PromptGuard funciona correctamente.

Comprueba, en orden:
  1) Backend FastAPI vivo (/health)
  2) Proveedor LLM alcanzable y lista modelos (/api/v1/health/llm)
  3) Chat end-to-end con un mensaje legítimo
  4) Chat end-to-end con un ataque de muestra

Uso:
  python scripts/smoke_test.py                # espera backend en localhost:8000
  python scripts/smoke_test.py --host 1.2.3.4
  python scripts/smoke_test.py --no-attack    # sólo legítimo
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent / "backend" / "tests" / "fixtures"


def banner(t: str) -> None:
    print("\n" + "=" * 70)
    print(f"  {t}")
    print("=" * 70)


async def step(name: str, coro):
    print(f"\n▶ {name} ...")
    result = await coro
    ok = result.get("ok", False)
    icon = "✅" if ok else "❌"
    print(f"  {icon} {result.get('msg', '')}")
    if not ok:
        if "hint" in result:
            print(f"     Hint: {result['hint']}")
    return ok


async def check_backend(client: httpx.AsyncClient, base: str):
    try:
        r = await client.get(f"{base}/api/v1/health", timeout=5.0)
        r.raise_for_status()
        data = r.json()
        return {"ok": True, "msg": f"Backend up. mode={data.get('mode')} defenses={data.get('defenses')}"}
    except Exception as e:
        return {"ok": False, "msg": f"Backend no responde: {e}",
                "hint": "Arranca el stack: `cd lab && docker compose up --build`"}


async def check_llm(client: httpx.AsyncClient, base: str):
    try:
        r = await client.get(f"{base}/api/v1/health/llm", timeout=8.0)
        data = r.json()
        if data.get("status") == "ok":
            models = data.get("available_models", [])
            cfg = data.get("configured_model")
            provider = data.get("provider", "unknown")
            return {"ok": True,
                    "msg": f"Proveedor OK ({provider}). Modelo configurado: {cfg}. Disponibles: {models}"}
        return {"ok": False, "msg": f"Proveedor reporta error: {data.get('error', '?')}",
                "hint": data.get("hint")}
    except Exception as e:
        return {"ok": False, "msg": f"No se pudo consultar /health/llm: {e}"}


async def check_legit_chat(client: httpx.AsyncClient, base: str, user: str):
    payload = {"user_id": user, "message": "Hola Clara, ¿cuál es el saldo de mi cuenta?"}
    try:
        r = await client.post(f"{base}/api/v1/chat", json=payload, timeout=90.0)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            return {"ok": False, "msg": f"Chat legítimo devolvió error: {data['error']}"}
        resp = (data.get("response") or "").strip()
        if not resp:
            return {"ok": False, "msg": "Chat legítimo devolvió respuesta vacía"}
        return {"ok": True,
                "msg": f"Respuesta legítima OK ({data.get('latency_ms')}ms): {resp[:80]!r}"}
    except Exception as e:
        return {"ok": False, "msg": f"Chat legítimo falló: {e}"}


async def check_attack_chat(client: httpx.AsyncClient, base: str, user: str):
    # Payload de un ataque de muestra del fixture
    attack_file = FIXTURES / "attack_prompts.jsonl"
    if not attack_file.exists():
        return {"ok": False, "msg": f"No encuentro {attack_file}"}
    import json
    attack = None
    for line in attack_file.read_text().splitlines():
        obj = json.loads(line)
        if obj["id"] == "atk_001":  # ignore_instructions_es
            attack = obj
            break
    if not attack:
        return {"ok": False, "msg": "atk_001 no encontrado en fixtures"}

    payload = {"user_id": user, "message": attack["payload"]}
    try:
        r = await client.post(f"{base}/api/v1/chat", json=payload, timeout=90.0)
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            return {"ok": False, "msg": f"Ataque devolvió error: {data['error']}"}
        # En modo vulnerable, esperamos respuesta (no bloqueo). La respuesta en
        # sí puede filtrar o no datos; aquí sólo validamos que el pipeline
        # completo ataque→LLM→respuesta funciona.
        resp = (data.get("response") or "").strip()
        return {"ok": bool(resp),
                "msg": f"Pipeline de ataque responde ({len(resp)} chars): {resp[:80]!r}"}
    except Exception as e:
        return {"ok": False, "msg": f"Chat de ataque falló: {e}"}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("SMOKE_HOST", "localhost"))
    ap.add_argument("--port", default=int(os.environ.get("SMOKE_PORT", "8000")))
    ap.add_argument("--user", default="usr_001")
    ap.add_argument("--no-attack", action="store_true", help="Sólo prueba legítima")
    args = ap.parse_args()

    base = f"http://{args.host}:{args.port}"
    banner(f"Smoke test del lab contra {base}")

    async with httpx.AsyncClient() as client:
        results = []
        results.append(await step("Backend health", check_backend(client, base)))
        results.append(await step("Proveedor LLM reachability", check_llm(client, base)))
        results.append(await step("Chat legítimo", check_legit_chat(client, base, args.user)))
        if not args.no_attack:
            results.append(await step("Chat de ataque (atk_001)", check_attack_chat(client, base, args.user)))

    banner("Resultado")
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"  {passed}/{total} pasos superados")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
