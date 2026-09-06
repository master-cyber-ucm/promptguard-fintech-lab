"""Informe de Campaña — mismo par de artefactos (run.json/run.md) que un Run Report,
en el mismo sitio (raíz del Run Folder), pero generado por el propio Agente de
red-team al cerrar la Campaña, no por el Analyze Pass — ver CONTEXT.md § Run Report.
"""

from __future__ import annotations

import json
from pathlib import Path

from models import Campania

RUNS_DIR = Path(__file__).resolve().parent.parent / "audit" / "runs"


def escribir_informe(campania: Campania) -> Path:
    run_folder = RUNS_DIR / campania.run_folder_name
    run_folder.mkdir(parents=True, exist_ok=True)

    data = {
        "run_folder": campania.run_folder_name,
        "config": campania.config,
        "inicio": campania.inicio,
        "fin": campania.fin,
        "ejercicios": [
            {
                "tecnica_id": e.tecnica_id, "nombre": e.nombre, "objetivo": e.objetivo,
                "exito": e.exito, "detenido_por": e.detenido_por, "n_intentos": e.n_intentos,
                "intentos": [
                    {
                        "numero": i.numero, "veredicto": i.veredicto, "razonamiento": i.razonamiento,
                        "n_turnos": len(i.turnos), "payload_inicial": i.payload_inicial,
                        "respuesta_final": i.respuesta_final, "session_id": i.session_id,
                        "soc_eventos": i.soc_eventos, "fuente": i.fuente,
                        "tools_used": i.turnos[-1].tools_used if i.turnos else [],
                    }
                    for i in e.intentos
                ],
            }
            for e in campania.ejercicios
        ],
    }
    (run_folder / "run.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (run_folder / "run.md").write_text(_render_md(campania), encoding="utf-8")
    return run_folder


def _render_md(campania: Campania) -> str:
    total = len(campania.ejercicios)
    bypasses = sum(1 for e in campania.ejercicios if e.exito)
    total_intentos = sum(e.n_intentos for e in campania.ejercicios)

    lines = [
        f"# Informe de Campaña — {campania.run_folder_name}\n",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Inicio | {campania.inicio} |",
        f"| Fin | {campania.fin} |",
        f"| Target | `{campania.config['target']}`{' (vulnerable=True, control)' if campania.config['vulnerable'] else ''} |",
        f"| Modo | `{campania.config['modo']}` |",
        f"| Motor de evolución | `{campania.config['motor']}` |",
        f"| Fuente de semillas | `{campania.config.get('fuente_semillas', 'ninguna')}` |",
        f"| Modelo atacante | `{campania.config['attacker_model']}` |",
        f"| Presupuesto por Ejercicio | {campania.config['max_intentos_por_ejercicio']} intentos |",
        f"| Ejercicios | {total} |",
        f"| **Salvaguardas superadas** | **{bypasses}/{total}** |",
        f"| Intentos totales | {total_intentos} |",
        "\n---\n",
        "## Resumen por Ejercicio\n",
        "| Técnica | Resultado | Intentos | Detenido por |",
        "|---|---|---|---|",
    ]
    for e in campania.ejercicios:
        resultado = "🔴 SUPERADA" if e.exito else "🟢 CONTUVO"
        lines.append(f"| {e.nombre} | {resultado} | {e.n_intentos}/{campania.config['max_intentos_por_ejercicio']} | {e.detenido_por} |")

    lines.append("\n---\n")
    for e in campania.ejercicios:
        lines.append(f"## {e.nombre} (`{e.tecnica_id}`)\n")
        lines.append(f"**Objetivo**: {e.objetivo}\n")
        lines.append(f"**Resultado**: {'🔴 salvaguarda superada' if e.exito else '🟢 contenido'} — {e.n_intentos} intento(s), detenido por `{e.detenido_por}`\n")
        if e.exito:
            ultimo = e.intentos[-1]
            lines.append("### Payload que superó las salvaguardas\n")
            lines.append(f"```\n{ultimo.payload_inicial}\n```\n")
            lines.append("### Respuesta de Clara\n")
            lines.append(f"```\n{ultimo.respuesta_final}\n```\n")
            if ultimo.turnos and ultimo.turnos[-1].tools_used:
                lines.append("### Tools realmente invocadas (evidencia estructural, no solo texto)\n")
                for t in ultimo.turnos[-1].tools_used:
                    lines.append(f"- `{t.get('tool')}` — {t.get('args') or t.get('result')}\n")
            lines.append(f"**Juicio del agente atacante**: {ultimo.razonamiento}\n")
            lines.append(f"**Session**: `{ultimo.session_id}` — ver Session File en `{e.tecnica_id}/`\n")
        lines.append("\n<details><summary>Todos los intentos</summary>\n")
        for i in e.intentos:
            origen = f" — fuente: `{i.fuente}`" if i.fuente != "propio" else ""
            lines.append(f"\n**Intento {i.numero}** — {i.veredicto} — {i.razonamiento}{origen}\n")
            lines.append(f"```\n{i.payload_inicial}\n```\n")
        lines.append("\n</details>\n\n---\n")

    return "\n".join(lines) + "\n"
