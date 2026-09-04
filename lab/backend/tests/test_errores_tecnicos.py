"""P08 — un error técnico no puede desaparecer del informe.

El runner contabilizó 12 errores que solo existían en el log de consola. Como el
informe itera Session Files, `atk_040` en `complex-prompt` mostraba dos observaciones
concluyentes sin señal de que faltaban tres.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from execution_errors import (  # noqa: E402
    ErrorPhase,
    classify,
    from_backend,
    from_exception,
    sanitize,
)
from report import _build_md, _compute_stats, error_breakdown  # noqa: E402


# ── Clasificación por fase ───────────────────────────────────────────────────

def test_un_timeout_se_clasifica_como_fallo_del_modelo():
    assert classify(httpx.ReadTimeout("timed out")) == ErrorPhase.MODEL


def test_una_conexion_rechazada_se_clasifica_como_connect():
    assert classify(httpx.ConnectError("connection refused")) == ErrorPhase.CONNECT


def test_un_json_corrupto_se_clasifica_como_parse():
    assert classify(json.JSONDecodeError("boom", "{", 0)) == ErrorPhase.PARSE


def test_un_fallo_al_persistir_se_clasifica_como_persist():
    assert classify(OSError("disk full")) == ErrorPhase.PERSIST


def test_un_5xx_sin_excepcion_se_clasifica_como_backend():
    assert classify(None, status_code=503) == ErrorPhase.BACKEND


def test_la_clasificacion_no_depende_del_texto_de_la_excepcion():
    """Los mensajes cambian entre versiones de librería; el tipo, no."""
    assert classify(httpx.ConnectTimeout("cualquier cosa")) == ErrorPhase.MODEL


def test_un_error_de_conexion_es_reintentable_y_uno_de_parseo_no():
    assert from_exception(httpx.ConnectError("x")).retryable is True
    assert from_exception(json.JSONDecodeError("x", "{", 0)).retryable is False


# ── Sanitización ─────────────────────────────────────────────────────────────

def test_un_iban_no_sobrevive_al_mensaje_de_error():
    limpio = sanitize("fallo procesando ES9121000418450200051332 en la tool")
    assert "ES9121000418450200051332" not in limpio
    assert "[IBAN]" in limpio


def test_un_token_no_sobrevive_al_mensaje_de_error():
    limpio = sanitize("Authorization: Bearer abc123def456ghi rechazado")
    assert "abc123def456ghi" not in limpio
    assert "[TOKEN]" in limpio


def test_una_clave_interna_no_sobrevive_al_mensaje_de_error():
    limpio = sanitize("respuesta contenía pg_internal_sk_a1b2c3d4e5f6")
    assert "a1b2c3d4e5f6" not in limpio


def test_un_importe_financiero_no_sobrevive_al_mensaje_de_error():
    assert "231.500,00" not in sanitize("saldo devuelto 231.500,00 € inesperado")


def test_un_correo_no_sobrevive_al_mensaje_de_error():
    assert "ana@example.com" not in sanitize("destinatario ana@example.com no válido")


def test_el_mensaje_se_recorta_para_no_arrastrar_el_prompt_entero():
    largo = sanitize("x" * 5000)
    assert len(largo) <= 240


def test_el_error_del_backend_tambien_se_sanea():
    fallo = from_backend("timeout hablando con ollama para ES9121000418450200051332")
    assert fallo.phase == ErrorPhase.MODEL
    assert "ES9121000418450200051332" not in fallo.message


# ── Desglose en el informe ───────────────────────────────────────────────────

def _ledger(*entradas):
    return list(entradas)


def _finished(exec_id, fixture_id, status="COMPLETED", fase=None, retryable=False):
    evento = {
        "event": "FINISHED", "fixture_execution_id": exec_id, "fixture_id": fixture_id,
        "target": "complex-prompt", "repetition": 1, "execution_status": status,
    }
    if fase:
        evento["failure"] = {"phase": fase, "exception_type": "ReadTimeout",
                             "message": "timed out", "retryable": retryable}
    return evento


def test_los_errores_se_agrupan_por_fase_y_por_fixture():
    desglose = error_breakdown(_ledger(
        _finished("e1", "atk_040", "TECHNICAL_ERROR", "MODEL", True),
        _finished("e2", "atk_040", "TECHNICAL_ERROR", "MODEL", True),
        _finished("e3", "atk_040", "COMPLETED"),
        _finished("e4", "leg_001", "TECHNICAL_ERROR", "CONNECT", True),
    ))
    assert desglose["total"] == 3
    assert desglose["by_phase"] == {"MODEL": 2, "CONNECT": 1}
    assert desglose["by_fixture"] == {"atk_040": 2, "leg_001": 1}


def test_cada_error_es_enlazable_desde_el_informe():
    desglose = error_breakdown(_ledger(_finished("e1", "atk_040", "TECHNICAL_ERROR", "MODEL")))
    entrada = desglose["entries"][0]
    assert entrada["fixture_execution_id"] == "e1"
    assert entrada["target"] == "complex-prompt"
    assert entrada["repetition"] == 1


def test_un_error_sin_clasificar_no_se_pierde():
    desglose = error_breakdown(_ledger(_finished("e1", "atk_1", "TECHNICAL_ERROR")))
    assert desglose["total"] == 1
    assert desglose["by_phase"] == {"UNKNOWN": 1}


def test_el_markdown_publica_los_errores_por_fase():
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["complex-prompt"], "suite_config": {},
        "errors": error_breakdown(_ledger(
            _finished("e1", "atk_040", "TECHNICAL_ERROR", "MODEL", True),
        )),
        "by_endpoint": {"complex-prompt": _compute_stats([])},
    })
    assert "## Errores técnicos" in md
    assert "`MODEL`" in md
    assert "`atk_040`" in md


def test_sin_errores_no_se_imprime_la_seccion():
    md = _build_md({
        "run_timestamp": "t", "model": "m",
        "model_provenance": {"requested_model": "m", "provider": "p",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": ["complex-prompt"], "suite_config": {},
        "errors": error_breakdown([]),
        "by_endpoint": {"complex-prompt": _compute_stats([])},
    })
    assert "## Errores técnicos" not in md
