"""PR6 — reintentos trazables y presupuestados a nivel de Fixture Execution.

Antes de este PR, `executions.json` mostraba `attempt_no=1, retry_of=null` para las
2.305 ejecuciones del run: los cuatro `ReadTimeout` y siete `BackendError` observados
nunca se reintentaban, aunque el propio contrato de `execution_errors.py` ya
distinguía fases reintentables (`RETRYABLE_PHASES`) de las que no lo son.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import run_attack_suite as suite  # noqa: E402


def _resultado(*, error=None, phase=None, retryable=False, block_code=None):
    return {
        "fixture_execution_id": "exec-1", "fixture_id": "atk_1", "target": "proxy-full",
        "repetition": 1, "latency_ms": 10.0, "response_preview": "", "error": error,
        "block_code": block_code, "session_id": "s1", "execution_status": "COMPLETED",
        "failure": ({"phase": phase, "retryable": retryable, "exception_type": "X",
                     "message": "m", "status_code": None} if error else None),
        "posture": {}, "posture_divergences": [], "attempt_no": 1, "retry_of": None,
    }


# ── Decisión pura de reintento ───────────────────────────────────────────────

def test_un_fallo_transitorio_dentro_del_presupuesto_se_reintenta():
    assert suite._should_retry(1, _resultado(error="timeout", phase="MODEL", retryable=True))


def test_una_denegacion_deterministica_no_se_reintenta():
    """`retryable=False` es justo lo que `execution_errors.classify()` decide para
    fases no transitorias (PARSE, PERSIST) — nunca para una denegación de policy,
    que ni siquiera llega aquí como `error` (usa `block_code`)."""
    assert not suite._should_retry(1, _resultado(error="fallo de parseo", phase="PARSE", retryable=False))


def test_un_bloqueo_esperado_no_es_un_error_y_no_se_reintenta():
    assert not suite._should_retry(1, _resultado(block_code="BLOCKED_BY_GATEKEEPER"))


def test_un_exito_no_necesita_reintento():
    assert not suite._should_retry(1, _resultado())


def test_se_agota_el_presupuesto_de_reintentos():
    fallo = _resultado(error="timeout", phase="MODEL", retryable=True)
    assert not suite._should_retry(suite.MAX_RETRY_ATTEMPTS + 1, fallo)


# ── Bucle de reintento completo ──────────────────────────────────────────────

def test_un_fallo_transitorio_seguido_de_exito_queda_marcado_como_reintentado(monkeypatch):
    intentos = [
        _resultado(error="timeout", phase="MODEL", retryable=True),
        {**_resultado(), "error": None, "failure": None},
    ]

    async def _falso_run_execution(client, execution, user_id, api_base):
        return intentos.pop(0)

    monkeypatch.setattr(suite, "run_execution", _falso_run_execution)
    monkeypatch.setattr(suite.asyncio, "sleep", _no_op_sleep)

    resultado = asyncio.run(suite.run_execution_with_retries(
        client=None, execution={"fixture_execution_id": "exec-1"}, user_id="usr_001", api_base="",
    ))
    assert resultado["attempt_no"] == 2
    assert resultado["retry_of"] == "exec-1"
    assert len(resultado["attempts"]) == 2
    assert resultado["attempts"][0]["outcome"] == "error"
    assert resultado["attempts"][1]["outcome"] == "ok"
    assert suite._attempt_outcome(resultado) == "ok"


def test_un_fallo_no_transitorio_no_se_reintenta_ni_una_vez(monkeypatch):
    llamadas = []

    async def _falso_run_execution(client, execution, user_id, api_base):
        llamadas.append(1)
        return _resultado(error="denegado", phase="BACKEND", retryable=False)

    monkeypatch.setattr(suite, "run_execution", _falso_run_execution)
    monkeypatch.setattr(suite.asyncio, "sleep", _no_op_sleep)

    resultado = asyncio.run(suite.run_execution_with_retries(
        client=None, execution={"fixture_execution_id": "exec-2"}, user_id="usr_001", api_base="",
    ))
    assert len(llamadas) == 1
    assert resultado["retry_of"] is None
    assert len(resultado["attempts"]) == 1


def test_un_fallo_persistente_se_agota_en_el_presupuesto(monkeypatch):
    llamadas = []

    async def _falso_run_execution(client, execution, user_id, api_base):
        llamadas.append(1)
        return _resultado(error="timeout", phase="MODEL", retryable=True)

    monkeypatch.setattr(suite, "run_execution", _falso_run_execution)
    monkeypatch.setattr(suite.asyncio, "sleep", _no_op_sleep)

    resultado = asyncio.run(suite.run_execution_with_retries(
        client=None, execution={"fixture_execution_id": "exec-3"}, user_id="usr_001", api_base="",
    ))
    # 1 intento inicial + MAX_RETRY_ATTEMPTS reintentos, nunca más.
    assert len(llamadas) == suite.MAX_RETRY_ATTEMPTS + 1
    assert len(resultado["attempts"]) == suite.MAX_RETRY_ATTEMPTS + 1
    assert suite._attempt_outcome(resultado) == "error"


async def _no_op_sleep(_seconds: float) -> None:
    """No esperar de verdad en tests — el backoff real se ejerce en producción."""
    return None
