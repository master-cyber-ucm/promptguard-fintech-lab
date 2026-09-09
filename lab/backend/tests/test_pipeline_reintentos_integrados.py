"""Contrato del cierre automático del pipeline suite → evaluate → report."""

from __future__ import annotations

import json
import sys
import asyncio
from pathlib import Path

import httpx

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import evaluate as evaluate_module  # noqa: E402
import run_attack_suite as suite  # noqa: E402
from evaluate import existing_eval_inconclusive, has_eval, process_run  # noqa: E402


def _evento(execution_id: str, *, status: str, retryable: bool) -> dict:
    return {
        "event": "FINISHED",
        "fixture_execution_id": execution_id,
        "execution_status": status,
        "failure": {"retryable": retryable} if status == "TECHNICAL_ERROR" else None,
    }


def test_retryable_usa_la_ultima_terminacion_de_cada_ejecucion(tmp_path):
    ledger = tmp_path / "execution-ledger.jsonl"
    ledger.write_text(
        "\n".join([
            json.dumps(_evento("resuelto", status="TECHNICAL_ERROR", retryable=True)),
            json.dumps(_evento("resuelto", status="COMPLETED", retryable=False)),
            json.dumps(_evento("pendiente", status="TECHNICAL_ERROR", retryable=True)),
            json.dumps(_evento("no-retry", status="TECHNICAL_ERROR", retryable=False)),
        ]) + "\n",
        encoding="utf-8",
    )

    assert suite.load_retryable_execution_ids(tmp_path) == {"pendiente"}


def test_retry_reata_ids_del_plan_y_no_amplia_el_denominador(tmp_path):
    (tmp_path / "coverage-plan.json").write_text(json.dumps({
        "rows": [{
            "fixture_id": "atk_1", "target": "proxy-full", "repetition": 1,
            "fixture_execution_id": "sellado-1",
        }],
    }), encoding="utf-8")
    reconstruidas = [
        {"fixture_id": "atk_1", "target": "proxy-full", "repetition": 1,
         "fixture_execution_id": "nuevo"},
        {"fixture_id": "atk_nuevo", "target": "proxy-full", "repetition": 1,
         "fixture_execution_id": "no-permitido"},
    ]

    resultado = suite.restore_plan_execution_ids(reconstruidas, tmp_path)

    assert resultado == [{
        "fixture_id": "atk_1", "target": "proxy-full", "repetition": 1,
        "fixture_execution_id": "sellado-1",
    }]


def test_pending_signature_cuenta_inconclusos_y_solo_el_ultimo_error(tmp_path):
    endpoint = tmp_path / "proxy-full"
    endpoint.mkdir()
    (endpoint / "inconcluso.md").write_text(
        '<!-- eval: {"inconclusive": true} -->\n', encoding="utf-8",
    )
    (endpoint / "pendiente.md").write_text("sin evaluación\n", encoding="utf-8")
    (tmp_path / "execution-ledger.jsonl").write_text(
        "\n".join([
            json.dumps(_evento("resuelto", status="TECHNICAL_ERROR", retryable=True)),
            json.dumps(_evento("resuelto", status="COMPLETED", retryable=False)),
            json.dumps(_evento("pendiente", status="TECHNICAL_ERROR", retryable=True)),
        ]) + "\n",
        encoding="utf-8",
    )

    assert evaluate_module.pending_signature(tmp_path) == (1, 1, 1)


def test_session_sin_respuesta_se_cierra_como_inconclusa(tmp_path):
    endpoint = tmp_path / "proxy-full"
    endpoint.mkdir()
    tick = chr(96)
    session_text = (
        "# Sesión\n\n"
        f"**Fixture**: {tick}atk_1{tick} · attack-prompts · expected: {tick}BLOCK{tick}\n\n"
        "### Registro de turno\n\n"
        "```json\n"
        '{"schema_version": 3, "client_response": "", "model_output_raw": "", '
        '"defenses": [], "fixture_execution_id": "e1", '
        '"execution_status": "TECHNICAL_ERROR", "error": "ReadTimeout"}\n'
        "```\n"
    )
    (endpoint / "sin-respuesta.md").write_text(session_text, encoding="utf-8")

    async def _run():
        async with httpx.AsyncClient() as client:
            await process_run(
                tmp_path,
                force=False,
                fixture_by_id={"atk_1": {"id": "atk_1", "evaluation": {"method": "deterministic"}}},
                client=client,
            )

    asyncio.run(_run())

    session = endpoint / "sin-respuesta.md"
    assert has_eval(session)
    assert existing_eval_inconclusive(session) is True
