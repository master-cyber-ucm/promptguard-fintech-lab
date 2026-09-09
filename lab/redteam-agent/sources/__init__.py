"""Fuentes de semillas — payloads de apertura ya escritos, no generados en el
momento por el Modelo atacante. Dos tipos: externas de solo lectura (`garak`,
escritas por un tercero, vendorizadas una vez) y la propia experiencia acumulada
del agente entre Campañas (`memoria`, se reescribe sola tras cada Campaña con los
Intentos que tuvieron tracción real). Ver `sources/README.md` y
`plan-fusion-redteam.md` para el porqué de `garak`, y `memoria_source.py` para el
porqué de `memoria`.

Cada fuente solo lee datos en `sources/data/*.json` — no requiere ninguna
dependencia pesada en tiempo de ejecución (esas viven en
`sources/tools/requirements-generate.txt`, solo para regenerar `garak_seeds.json`).

Si una Técnica no tiene semillas de la fuente elegida, `siguiente()` devuelve None
y el motor de evolución configurado (`--engine`) genera el payload como si no
hubiera fuente — el flag `--seed-source` es aditivo, nunca bloqueante.
"""

from __future__ import annotations

from typing import Protocol

FUENTES = ("ninguna", "garak", "memoria")


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
    if nombre == "memoria":
        from sources.memoria_source import MemoriaSource
        return MemoriaSource()
    raise ValueError(f"Fuente de semillas desconocida: {nombre!r} (opciones: {FUENTES})")
