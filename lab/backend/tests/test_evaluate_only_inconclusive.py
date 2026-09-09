"""P29 (feedback profesor 2026-09-05): cerrar el gate de cobertura del 99% con
`evaluate.py --run <run> --force` reevalúa las ~2415 ejecuciones del run para
arreglar las ~300 `INCONCLUSIVE` — recorre también las ~2100 ya concluyentes sin
necesidad. `--only-inconclusive` acota el reintento a las que de verdad lo
necesitan, dejando intacta cualquier sesión que ya tenga una evaluación concluyente.
"""

from __future__ import annotations

import asyncio
import json

import httpx

import scripts.evaluate as evaluate_module
from scripts.evaluate import existing_eval_inconclusive, process_run
from scripts.evaluations.base import EvaluationResult

SESSION_TEMPLATE = """# Sesión `ses_x`

## Turno 1 — 00:00:00

**Fixture**: `{fixture_id}` · attack-prompts · expected: `BLOCK`

### Registro de turno

```json
{registro}
```
{evaluacion}
"""


def _session_text(fixture_id: str, *, con_eval: bool, inconclusive: bool = False) -> str:
    registro = json.dumps({
        "schema_version": 3,
        "client_response": "respuesta del modelo",
        "model_output_raw": "respuesta del modelo",
        "defenses": [],
        "fixture_execution_id": "e1",
    })
    evaluacion = (
        f'\n---\n\n## Evaluación · 2026-09-05T00:00:00Z\n\n'
        f'<!-- eval: {json.dumps({"inconclusive": inconclusive})} -->\n'
        if con_eval else ""
    )
    return SESSION_TEMPLATE.format(fixture_id=fixture_id, registro=registro, evaluacion=evaluacion)


# ── existing_eval_inconclusive: lectura pura del bloque ya escrito ──────────────

def test_sin_marcador_de_evaluacion_se_trata_como_pendiente(tmp_path):
    sf = tmp_path / "s.md"
    sf.write_text(_session_text("atk_1", con_eval=False), encoding="utf-8")
    assert existing_eval_inconclusive(sf) is None


def test_evaluacion_concluyente_devuelve_false(tmp_path):
    sf = tmp_path / "s.md"
    sf.write_text(_session_text("atk_1", con_eval=True, inconclusive=False), encoding="utf-8")
    assert existing_eval_inconclusive(sf) is False


def test_evaluacion_inconclusa_devuelve_true(tmp_path):
    sf = tmp_path / "s.md"
    sf.write_text(_session_text("atk_1", con_eval=True, inconclusive=True), encoding="utf-8")
    assert existing_eval_inconclusive(sf) is True


def test_bloque_eval_malformado_se_trata_como_pendiente_no_como_concluyente(tmp_path):
    sf = tmp_path / "s.md"
    texto = _session_text("atk_1", con_eval=False) + "\n<!-- eval: {esto-no-es-json -->\n"
    sf.write_text(texto, encoding="utf-8")
    assert existing_eval_inconclusive(sf) is None


# ── process_run(only_inconclusive=True): efecto de punta a punta ───────────────

class _StubEvaluator:
    """Evaluador de prueba: siempre concluye BLOCKED, y cuenta cuántas veces corrió."""

    calls: list[str] = []

    async def evaluate(self, ctx):
        _StubEvaluator.calls.append(ctx.fixture_execution_id)
        return EvaluationResult(
            verdict="BLOCKED", passed=True, inconclusive=False,
            status="PASS", disposition="SECURITY_BLOCK", decision_source="stub",
        )


def _fixture_by_id() -> dict:
    base = {"evaluation": {"method": "deterministic", "applicable_controls": ["tool_gatekeeper"]}}
    return {"atk_1": {"id": "atk_1", **base}, "atk_2": {"id": "atk_2", **base}}


def test_only_inconclusive_no_reevalua_las_sesiones_ya_concluyentes(tmp_path, monkeypatch):
    ep_dir = tmp_path / "run" / "proxy-full"
    ep_dir.mkdir(parents=True)
    concluyente = ep_dir / "concluyente.md"
    concluyente.write_text(
        _session_text("atk_1", con_eval=True, inconclusive=False), encoding="utf-8",
    )

    _StubEvaluator.calls = []
    monkeypatch.setattr(
        evaluate_module, "evaluator_from_fixture", lambda fixture: _StubEvaluator(),
    )

    async def _run():
        async with httpx.AsyncClient() as client:
            await process_run(
                ep_dir.parent, force=True, fixture_by_id=_fixture_by_id(), client=client,
                only_inconclusive=True,
            )

    asyncio.run(_run())

    assert _StubEvaluator.calls == []
    # El fichero no se tocó: sigue con su bloque de evaluación original.
    assert existing_eval_inconclusive(concluyente) is False


def test_only_inconclusive_si_reevalua_las_sesiones_inconclusas(tmp_path, monkeypatch):
    ep_dir = tmp_path / "run" / "proxy-full"
    ep_dir.mkdir(parents=True)
    inconclusa = ep_dir / "inconclusa.md"
    inconclusa.write_text(
        _session_text("atk_2", con_eval=True, inconclusive=True), encoding="utf-8",
    )

    _StubEvaluator.calls = []
    monkeypatch.setattr(
        evaluate_module, "evaluator_from_fixture", lambda fixture: _StubEvaluator(),
    )

    async def _run():
        async with httpx.AsyncClient() as client:
            await process_run(
                ep_dir.parent, force=True, fixture_by_id=_fixture_by_id(), client=client,
                only_inconclusive=True,
            )

    asyncio.run(_run())

    assert _StubEvaluator.calls == ["e1"]
    # El stub la deja concluyente: el reintento cerró el gap para esta sesión.
    assert existing_eval_inconclusive(inconclusa) is False


def test_sin_only_inconclusive_force_reevalua_todo_como_antes(tmp_path, monkeypatch):
    """Comportamiento previo intacto: `--force` sin `--only-inconclusive` no cambia."""
    ep_dir = tmp_path / "run" / "proxy-full"
    ep_dir.mkdir(parents=True)
    concluyente = ep_dir / "concluyente.md"
    concluyente.write_text(
        _session_text("atk_1", con_eval=True, inconclusive=False), encoding="utf-8",
    )

    _StubEvaluator.calls = []
    monkeypatch.setattr(
        evaluate_module, "evaluator_from_fixture", lambda fixture: _StubEvaluator(),
    )

    async def _run():
        async with httpx.AsyncClient() as client:
            await process_run(
                ep_dir.parent, force=True, fixture_by_id=_fixture_by_id(), client=client,
                only_inconclusive=False,
            )

    asyncio.run(_run())

    assert _StubEvaluator.calls == ["e1"]
