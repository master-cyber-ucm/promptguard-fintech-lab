#!/usr/bin/env python3
"""Analyze Pass offline — re-juzga cada Intento de una Campaña ya ejecutada con un juez
más fuerte, SIN volver a atacar. Mismo patrón que el proyecto ya usa para la suite
estática: separa la ejecución barata (Campaña) del juicio caro (`evaluate.py` frente a
`run_attack_suite.py`). Ver plan de excelencia §B1.

Fuente de datos, en orden de preferencia:
1. `ejercicios/{tecnica_id}/{run_folder_name}.md` (B7) — transcripción completa turno a
   turno, la fuente correcta desde que B7 existe.
2. `lab/audit/runs/{run_folder_name}/run.json` — fallback para Campañas anteriores a B7
   (solo trae payload inicial + respuesta final, no el histórico multi-turno completo).

Uso:
  python analyze_campania.py 20260816_210638_redteam-agent
  python analyze_campania.py 20260816_210638_redteam-agent --judge-model qwen3.5:9b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from attacker import AttackerBrain  # noqa: E402
from ollama_client import OllamaClient  # noqa: E402
from orchestrator import cargar_taxonomia  # noqa: E402

EJERCICIOS_DIR = HERE / "ejercicios"
ANALISIS_DIR = HERE / "analisis"
RUNS_DIR = HERE.parent / "audit" / "runs"

_INTENTO_SPLIT_RE = re.compile(r"\n## Intento (\d+)\n")
_TURNO_RE = re.compile(
    r"### Turno \d+\n\n\*\*Payload\*\*:\n```\n(.*?)\n```\n\n\*\*Respuesta\*\*:\n```\n(.*?)\n```\n",
    re.DOTALL,
)
_VEREDICTO_RE = re.compile(r"\*\*Veredicto\*\*: `(\w+)` — (.*?)\n")


def _parsear_b7(path: Path) -> list[dict]:
    texto = path.read_text(encoding="utf-8")
    partes = _INTENTO_SPLIT_RE.split(texto)[1:]  # [numero, cuerpo, numero, cuerpo, ...]
    intentos = []
    for numero_str, cuerpo in zip(partes[0::2], partes[1::2]):
        turnos = [
            {"mensaje": m.group(1).strip(), "respuesta": m.group(2).strip()}
            for m in _TURNO_RE.finditer(cuerpo)
        ]
        vm = _VEREDICTO_RE.search(cuerpo)
        intentos.append({
            "numero": int(numero_str),
            "turnos": turnos,
            "veredicto_original": vm.group(1) if vm else "UNKNOWN",
            "razon_original": vm.group(2).strip() if vm else "",
        })
    return intentos


def _parsear_run_json_fallback(run_folder_name: str, tecnica_id: str) -> list[dict] | None:
    run_json = RUNS_DIR / run_folder_name / "run.json"
    if not run_json.exists():
        return None
    data = json.loads(run_json.read_text(encoding="utf-8"))
    for ejercicio in data.get("ejercicios", []):
        if ejercicio["tecnica_id"] != tecnica_id:
            continue
        return [
            {
                "numero": i["numero"],
                "turnos": [{"mensaje": i["payload_inicial"], "respuesta": i["respuesta_final"]}],
                "veredicto_original": i["veredicto"],
                "razon_original": i["razonamiento"],
            }
            for i in ejercicio["intentos"]
        ]
    return None


def cargar_intentos(run_folder_name: str, tecnica_id: str) -> tuple[list[dict], str]:
    """Devuelve (intentos, fuente) — fuente es 'b7' o 'run.json' para que quede declarado
    de dónde salió el re-análisis."""
    fichero_b7 = EJERCICIOS_DIR / tecnica_id / f"{run_folder_name}.md"
    if fichero_b7.exists():
        return _parsear_b7(fichero_b7), "b7"
    intentos = _parsear_run_json_fallback(run_folder_name, tecnica_id)
    return (intentos or []), "run.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Pass offline del Agente de red-team")
    parser.add_argument("run_folder_name")
    parser.add_argument("--judge-model", default="qwen3.5:9b")
    parser.add_argument("--ollama-host", default="localhost")
    parser.add_argument("--ollama-port", type=int, default=11434)
    parser.add_argument("--user", default="usr_001")
    parser.add_argument("--techniques", nargs="*", default=[],
                         help="Subconjunto de técnicas por id (default: todas las presentes en la Campaña)")
    args = parser.parse_args()

    tecnicas = {t["id"]: t for t in cargar_taxonomia()}
    ollama = OllamaClient(f"http://{args.ollama_host}:{args.ollama_port}", args.judge_model, temperature=0.2)
    brain = AttackerBrain(ollama, args.user)

    # El universo de técnicas a revisar es la unión de lo que trae ejercicios/ (B7) y lo
    # que trae run.json (fallback) para esta Campaña — no solo una de las dos fuentes.
    tecnicas_con_datos = {p.name for p in EJERCICIOS_DIR.iterdir() if p.is_dir()} if EJERCICIOS_DIR.exists() else set()
    run_json_path = RUNS_DIR / args.run_folder_name / "run.json"
    if run_json_path.exists():
        data = json.loads(run_json_path.read_text(encoding="utf-8"))
        tecnicas_con_datos |= {e["tecnica_id"] for e in data.get("ejercicios", [])}
    if args.techniques:
        tecnicas_con_datos &= set(args.techniques)

    resultados: dict[str, list[dict]] = {}
    discrepancias = 0
    total = 0

    for tecnica_id in sorted(tecnicas_con_datos):
        tecnica = tecnicas.get(tecnica_id)
        if not tecnica:
            continue
        intentos, fuente = cargar_intentos(args.run_folder_name, tecnica_id)
        if not intentos:
            continue
        print(f"\n── {tecnica['nombre']} ({tecnica_id}) — fuente: {fuente} ──")
        resultados[tecnica_id] = []
        for intento in intentos:
            total += 1
            veredicto, razon = brain.juzgar(
                tecnica, intento["turnos"], historial=[], soc_eventos=None, turnos_restantes=0,
            )
            original = intento["veredicto_original"]
            coincide = veredicto == original or (original == "CONTINUE" and veredicto == "FAILED")
            if not coincide:
                discrepancias += 1
            resultados[tecnica_id].append({
                "numero": intento["numero"], "fuente": fuente,
                "veredicto_original": original, "razon_original": intento["razon_original"],
                "veredicto_reanalizado": veredicto, "razon_reanalizada": razon,
                "coincide": coincide,
            })
            marca = "" if coincide else "  ⚠ DISCREPANCIA"
            print(f"  intento {intento['numero']}: {original} → {veredicto}{marca}")

    ANALISIS_DIR.mkdir(exist_ok=True)
    salida = ANALISIS_DIR / f"{args.run_folder_name}.reanalizado.json"
    salida.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n═══ {discrepancias}/{total} discrepancias entre juez en caliente y Analyze Pass ═══")
    print(f"Detalle: {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
