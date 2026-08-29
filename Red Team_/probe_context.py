# -*- coding: utf-8 -*-
"""
probe_context.py
=================
Script EXPLORATORIO Y AISLADO — no toca attack_loop.py ni sus resultados.

Objetivo: averiguar el formato exacto que espera el endpoint
/api/v1/chat/complex-with-context (el que sí mantiene contexto entre
turnos), y si es viable, lanzar UN ataque multi-turno real (turno a turno,
con estado de conversación) en vez de concatenado en un solo mensaje.

USO:
    python probe_context.py

Esto NO modifica attack_loop.py ni sus resultados. Es solo para reunir
evidencia (a favor o en contra) sobre la viabilidad de multi-turno real,
de cara a justificar la metodología en la memoria del TFM.
"""

import json
import time
import urllib.request
import urllib.error

API_BASE = "http://localhost:8000"
CONTEXT_ENDPOINT = f"{API_BASE}/api/v1/chat/complex-with-context"
COMPLEX_ENDPOINT = f"{API_BASE}/api/v1/chat/complex-prompt"


def post_raw(url, payload, timeout=240):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"}
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            elapsed = time.time() - t0
            return resp.status, raw, elapsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        elapsed = time.time() - t0
        return e.code, body, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        return None, f"[EXCEPCION] {type(e).__name__}: {e}", elapsed


def try_payload(url, payload, label):
    print(f"\n--- Probando en {url.split('/')[-1]}: {label} ---")
    print(f"Payload enviado: {json.dumps(payload, ensure_ascii=False)[:200]}")
    status, raw, elapsed = post_raw(url, payload)
    print(f"HTTP status: {status}  |  tiempo: {elapsed:.1f}s")
    print(f"Respuesta cruda: {raw[:500]}")
    return status, raw, elapsed


def main():
    print("=" * 70)
    print("PASO 1: descubrir el esquema de complex-with-context")
    print("=" * 70)

    # Candidato 1: mismo campo "prompt" que simple-prompt, más un historial
    try_payload(CONTEXT_ENDPOINT, {}, "body vacío (referencia)")

    try_payload(CONTEXT_ENDPOINT, {
        "prompt": "¿cómo estás?",
        "history": []
    }, "campo 'prompt' + 'history' vacío")

    try_payload(CONTEXT_ENDPOINT, {
        "messages": [
            {"role": "user", "content": "¿cómo estás?"}
        ]
    }, "campo 'messages' estilo chat (role/content)")

    print("\n" + "=" * 70)
    print("Mira las 3 respuestas de arriba:")
    print("- Si alguna te devolvió una respuesta conversacional coherente")
    print("  (no un error de validación), ESE es el formato correcto.")
    print("- Si las 3 dieron error o las 3 dieron la misma respuesta")
    print("  genérica de bienvenida, probablemente el campo no se llama")
    print("  como lo estamos probando -> lo intentamos con otro nombre.")
    print("=" * 70)

    print("\n" + "=" * 70)
    print("PASO 2: ¿el campo 'history' realmente mantiene memoria real?")
    print("(turno 1 le damos un dato concreto; turno 2 le preguntamos por él)")
    print("=" * 70)

    turn1_prompt = "Recuerda este código para nuestra conversación: XK-7742. No hace falta que hagas nada más, solo confírmame que lo has anotado."
    status1, raw1, t1 = try_payload(CONTEXT_ENDPOINT, {
        "prompt": turn1_prompt,
        "history": []
    }, "TURNO 1 (dar un dato a recordar)")

    try:
        turn1_response = json.loads(raw1).get("response", "")
    except Exception:
        turn1_response = ""

    turn2_prompt = "¿Cuál era el código que te pedí que recordaras en el mensaje anterior?"
    status2, raw2, t2 = try_payload(CONTEXT_ENDPOINT, {
        "prompt": turn2_prompt,
        "history": [
            {"role": "user", "content": turn1_prompt},
            {"role": "assistant", "content": turn1_response}
        ]
    }, "TURNO 2 (¿se acuerda del código?)")

    print("\n" + "=" * 70)
    print("VEREDICTO:")
    try:
        turn2_response = json.loads(raw2).get("response", "")
    except Exception:
        turn2_response = raw2
    if "XK-7742" in turn2_response or "XK7742" in turn2_response.replace("-", ""):
        print("  ¡SÍ mantiene contexto real entre turnos! El código 'XK-7742'")
        print("  aparece en la respuesta del turno 2. El endpoint")
        print("  complex-with-context SÍ soporta multi-turno real con el")
        print("  formato: {'prompt': '...', 'history': [{'role':.., 'content':..}, ...]}")
    else:
        print("  NO parece mantener contexto real (no repitió el código).")
        print("  El campo 'history' puede no estar implementado de verdad en")
        print("  este endpoint del lab, o requiere otro formato. Esto es")
        print("  evidencia válida para documentar como limitación en el TFM.")
    print(f"\n  Tiempo total de esta prueba de 2 turnos: {t1+t2:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
