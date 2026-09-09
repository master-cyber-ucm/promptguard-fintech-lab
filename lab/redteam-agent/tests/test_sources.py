"""Tests de la fusión con Red Team_ (Norma) — fuentes de semillas externas.
Ver plan-fusion-redteam.md. No requieren garak/pyrit instalados: solo leen JSON."""

from __future__ import annotations

import json

import pytest

from sources import get_source
from sources.garak_source import GarakSource


def _escribir_seeds(tmp_path, seeds: dict) -> "Path":
    path = tmp_path / "garak_seeds.json"
    path.write_text(json.dumps({"source": "garak", "seeds": seeds}), encoding="utf-8")
    return path


def test_get_source_ninguna_devuelve_none():
    assert get_source(None) is None
    assert get_source("ninguna") is None


def test_get_source_desconocida_lanza_error():
    with pytest.raises(ValueError):
        get_source("no-existe")


def test_get_source_garak_devuelve_garaksource():
    fuente = get_source("garak")
    assert isinstance(fuente, GarakSource)
    assert fuente.name == "garak"


def test_garak_source_cicla_y_se_agota(tmp_path):
    path = _escribir_seeds(tmp_path, {
        "directa": [{"text": "semilla 1", "probe": "x"}, {"text": "semilla 2", "probe": "y"}],
    })
    fuente = GarakSource(data_path=path)
    tecnica = {"id": "directa"}
    assert fuente.siguiente(tecnica) == "semilla 1"
    assert fuente.siguiente(tecnica) == "semilla 2"
    assert fuente.siguiente(tecnica) is None  # agotada, no repite ni inventa


def test_garak_source_tecnica_sin_semillas_devuelve_none(tmp_path):
    path = _escribir_seeds(tmp_path, {"directa": [{"text": "semilla 1", "probe": "x"}]})
    fuente = GarakSource(data_path=path)
    assert fuente.siguiente({"id": "cross-context-leakage"}) is None


def test_garak_source_data_faltante_da_error_explicito(tmp_path):
    with pytest.raises(FileNotFoundError):
        GarakSource(data_path=tmp_path / "no_existe.json")


def test_garak_seeds_vendorizado_real_tiene_las_dos_tecnicas_documentadas():
    """El JSON que se distribuye con el repo (no un fixture) debe seguir teniendo
    cobertura para las dos técnicas documentadas en generate_garak_seeds.py — si
    este test falla, alguien regeneró el fichero y rompió el mapeo curado."""
    fuente = GarakSource()
    assert fuente.siguiente({"id": "directa"}) is not None
    assert fuente.siguiente({"id": "filtrado-por-repeticion"}) is not None
    assert fuente.siguiente({"id": "pii-harvesting"}) is None
