"""Memoria persistente ENTRE Campañas — a diferencia de `garak_source.py` (datos
externos, de solo lectura, vendorizados una vez), esta es la propia experiencia
acumulada del agente: los Intentos con veredicto `SUCCESS`/`CONTINUE` de cada
Campaña se guardan aquí, y Campañas futuras los reinyectan como semilla de
apertura — mismo Protocol `SeedSource` que `GarakSource`, mismo `--seed-source`.

Antes de esto, la memoria del agente estaba acotada a un solo Ejercicio de una
sola Campaña (ADR-0008, CONTEXT.md § "Ejercicio") — cada `python cli.py` nuevo
empezaba en blanco, sin importar cuántas Campañas se hubieran corrido antes.
Encontrado al revisar 2 campañas reales de usuario (140 intentos, 0 SUCCESS/
CONTINUE): nada de ese trabajo se aprovechaba en la siguiente corrida.

Un `FAILED`, por definición, no aporta nada que reinyectar — ya sabemos que ese
payload no funciona contra las defensas actuales tal cual. Solo se persisten
`SUCCESS`/`CONTINUE`: los dos veredictos que demuestran que el payload tuvo
tracción real contra el target.

`memoria.json` NO se versiona en git (ver .gitignore) — es estado acumulado local,
distinto de `garak_seeds.json`/`harmbench_offtopic_seeds.json`, que son datasets
fijos generados una vez y sí se comparten en el repo.
"""

from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent / "data" / "memoria.json"

# FAILED/ERROR no aportan nada que reinyectar. Orden: SUCCESS antes que CONTINUE al
# reinyectar, son la señal más fuerte.
_VEREDICTOS_APRENDIBLES = {"SUCCESS": 0, "CONTINUE": 1}

name = "memoria"


def _cargar(path: Path) -> dict[str, list[dict]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


class MemoriaSource:
    """SeedSource que lee `memoria.json`. Si no existe todavía (ninguna Campaña
    anterior dejó nada aprendible), se comporta como una fuente vacía — nunca
    bloquea, cae al motor de evolución configurado igual que si no hubiera fuente."""

    name = name

    def __init__(self, data_path: Path | None = None) -> None:
        self._path = data_path or DATA_PATH
        pools = _cargar(self._path)
        self._pools: dict[str, list[dict]] = {
            tid: sorted(entradas, key=lambda e: _VEREDICTOS_APRENDIBLES.get(e.get("veredicto"), 9))
            for tid, entradas in pools.items()
        }
        self._cursor: dict[str, int] = {}

    def siguiente(self, tecnica: dict) -> str | None:
        tid = tecnica["id"]
        pool = self._pools.get(tid)
        if not pool:
            return None
        idx = self._cursor.get(tid, 0)
        if idx >= len(pool):
            return None
        self._cursor[tid] = idx + 1
        return pool[idx]["payload"]


def registrar_campania(campania, data_path: Path | None = None) -> int:
    """Se llama al cerrar cada Campaña (cli.py, tras escribir_informe), con
    independencia de qué --seed-source se haya usado — grabar no cambia ningún
    comportamiento, solo alimenta campañas futuras. Añade a la memoria persistente
    los Intentos con veredicto SUCCESS/CONTINUE de cada Ejercicio, deduplicados por
    payload exacto dentro de la misma Técnica. Devuelve cuántos se añadieron."""
    path = data_path or DATA_PATH
    memoria = _cargar(path)
    nuevos = 0
    for ejercicio in campania.ejercicios:
        tid = ejercicio.tecnica_id
        pool = memoria.setdefault(tid, [])
        existentes = {e["payload"] for e in pool}
        for intento in ejercicio.intentos:
            if intento.veredicto not in _VEREDICTOS_APRENDIBLES:
                continue
            payload = intento.payload_inicial
            if not payload or payload in existentes:
                continue
            pool.append({
                "payload": payload,
                "veredicto": intento.veredicto,
                "razonamiento": intento.razonamiento,
                "run_folder": campania.run_folder_name,
                "attacker_model": campania.config.get("attacker_model"),
            })
            existentes.add(payload)
            nuevos += 1
    if nuevos:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(memoria, indent=2, ensure_ascii=False), encoding="utf-8")
    return nuevos
