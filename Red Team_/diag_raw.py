# -*- coding: utf-8 -*-
"""
diag_raw.py
===========
Diagnóstico: envía los prompts que están fallando y muestra el JSON
crudo devuelto por Clara, tal cual, sin intentar interpretarlo.

USO:
    python diag_raw.py
"""

import json
import urllib.request

API_BASE = "http://localhost:8000"
CHAT_ENDPOINT = f"{API_BASE}/api/v1/chat/simple-prompt"
FIXTURES_ENDPOINT = f"{API_BASE}/api/v1/fixtures"

TARGET_IDS = ["atk_001", "atk_021", "atk_030"]


def http_get_json(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post_raw(url, payload, timeout=240):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw_bytes = resp.read()
        status = resp.status
    return status, raw_bytes.decode("utf-8", errors="replace")


def flatten_steps(rendered_steps):
    return "\n\n".join(step["content"].strip() for step in rendered_steps)


def main():
    print("Descargando fixtures...")
    data = http_get_json(FIXTURES_ENDPOINT)
    fixtures = {f["id"]: f for f in data.get("fixtures", [])}

    for fid in TARGET_IDS:
        fx = fixtures.get(fid)
        if not fx:
            print(f"{fid}: no encontrado en fixtures")
            continue
        prompt_text = flatten_steps(fx["rendered_steps"])
        print("=" * 70)
        print(f"ID: {fid}")
        print(f"Prompt enviado:\n{prompt_text}\n")
        try:
            status, raw = http_post_raw(CHAT_ENDPOINT, {"prompt": prompt_text})
            print(f"HTTP status: {status}")
            print(f"JSON crudo (tal cual, sin interpretar):\n{raw}")
            print(f"\nTipo Python tras json.loads: {type(json.loads(raw))}")
        except Exception as e:
            print(f"Error al llamar: {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    main()
