"""Fuentes de semillas externas — payloads de apertura ya escritos por un tercero
(no generados por el propio Modelo atacante), para el primer Intento de un
Ejercicio. Ver `sources/README.md` y `plan-fusion-redteam.md` para el porqué.

Cada fuente solo lee datos vendorizados en `sources/data/*.json` — no requiere
ninguna dependencia pesada en tiempo de ejecución (esas viven en
`sources/tools/requirements-generate.txt`, solo para regenerar los JSON).

Si una Técnica no tiene semillas de la fuente elegida, `siguiente()` devuelve None
y el motor de evolución configurado (`--engine`) genera el payload como si no
hubiera fuente — el flag `--seed-source` es aditivo, nunca bloqueante.
"""

from __future__ import annotations

from typing import Protocol

FUENTES = ("ninguna", "garak")


class SeedSource(Protocol):
    name: str

    def siguiente(self, tecnica: dict) -> str | None:
        """Devuelve el siguiente payload semilla para esta Técnica, o None si no
        quedan semillas de esta fuente para ella."""
        ...


def get_source(nombre: str | None) -> SeedSource | None:
    if not nombre or nombre == "ninguna":
        return None
    if nombre == "garak":
        from sources.garak_source import GarakSource
        return GarakSource()
    raise ValueError(f"Fuente de semillas desconocida: {nombre!r} (opciones: {FUENTES})")
