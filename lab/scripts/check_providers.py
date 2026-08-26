#!/usr/bin/env python3
"""Diagnostico de proveedores LLM para el lab.

Lanza una peticion de prueba contra cada backend configurado:

- Ollama local
- OpenRouter
- Proveedor custom OpenAI-compatible

Uso:
  python scripts/check_providers.py
  python scripts/check_providers.py --provider ollama
  python scripts/check_providers.py --provider openrouter
  python scripts/check_providers.py --provider custom
  python scripts/check_providers.py --provider all
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class ProviderTarget:
    name: str
    base_url: str
    model: str
    api_key: str


def _normalize_base_url(base_url: str) -> str:
    cleaned = base_url.rstrip("/")
    return cleaned if cleaned.endswith("/v1") else f"{cleaned}/v1"


def _placeholder_key(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or "tu_api_key_aqui" in lowered or "placeholder" in lowered or "changeme" in lowered


def build_target(provider: str) -> ProviderTarget | None:
    provider = provider.lower()

    if provider == "ollama":
        return ProviderTarget(
            name="ollama",
            base_url=_normalize_base_url(os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")),
            model=os.environ.get("OLLAMA_MODEL", "qwen3.5:9b"),
            api_key=os.environ.get("OLLAMA_API_KEY", "ollama"),
        )

    if provider == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "sk-or-v1-TU_API_KEY_AQUI")
        if _placeholder_key(api_key):
            return None
        return ProviderTarget(
            name="openrouter",
            base_url=_normalize_base_url(os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")),
            model=os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
            api_key=api_key,
        )

    if provider == "custom":
        base_url = os.environ.get("LLM_BASE_URL", "http://localhost:4000/v1")
        model = os.environ.get("LLM_MODEL", "clara-local")
        api_key = os.environ.get("LLM_API_KEY", "sk-local")
        return ProviderTarget(
            name="custom",
            base_url=_normalize_base_url(base_url),
            model=model,
            api_key=api_key,
        )

    raise ValueError(f"Proveedor desconocido: {provider}")


async def probe(client: httpx.AsyncClient, target: ProviderTarget) -> dict:
    payload = {
        "model": target.model,
        "messages": [{"role": "user", "content": "Responde solo con: OK"}],
        "max_tokens": 10,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {target.api_key}"}

    if target.name == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("OPENROUTER_HTTP_REFERER", "http://localhost")
        headers["X-OpenRouter-Title"] = os.environ.get("OPENROUTER_TITLE", "PromptGuard FinTech Lab")

    try:
        r = await client.post(
            f"{target.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        if r.status_code != 200:
            return {"ok": False, "provider": target.name, "msg": f"HTTP {r.status_code}: {r.text[:200]}"}
        data = r.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        return {"ok": True, "provider": target.name, "msg": f"OK -> {content!r}"}
    except Exception as e:
        return {"ok": False, "provider": target.name, "msg": str(e)}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Comprueba el acceso a los proveedores LLM del lab.")
    parser.add_argument(
        "--provider",
        default="all",
        choices=["all", "ollama", "openrouter", "custom"],
        help="Proveedor a comprobar",
    )
    args = parser.parse_args()

    providers = ["ollama", "openrouter", "custom"] if args.provider == "all" else [args.provider]
    any_ok = False
    any_attempted = False

    print("\nDiagnostico de proveedores LLM\n")

    async with httpx.AsyncClient() as client:
        for provider in providers:
            target = build_target(provider)
            if target is None:
                print(f"  ⏭️  {provider:10} -> omitido (OPENROUTER_API_KEY sigue como placeholder)")
                continue
            any_attempted = True
            result = await probe(client, target)
            icon = "✅" if result["ok"] else "❌"
            print(f"  {icon}  {provider:10} -> {result['msg']}")
            any_ok = any_ok or result["ok"]

    print()
    if any_ok:
        print("Al menos un proveedor responde. El lab esta listo para ese modo.")
        return 0

    if not any_attempted:
        print("No se pudo intentar ninguna conexion real.")
        print("Configura OPENROUTER_API_KEY o cambia a LLM_PROVIDER=ollama.")
        return 1

    print("Ningun proveedor responde. Revisa:")
    print("  - Ollama: `ollama serve` + `ollama pull qwen3.5:9b`")
    print("  - OpenRouter: API key valida en .env (OPENROUTER_API_KEY)")
    print("  - Custom: LLM_BASE_URL, LLM_MODEL y LLM_API_KEY")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
