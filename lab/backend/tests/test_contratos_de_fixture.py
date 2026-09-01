"""P21 — un oráculo desalineado penaliza al sistema por cumplir su propia API.

`leg_002` esperaba `result.status: blocked`. La tool devuelve `status: completed` con
`card_status: blocked`: "bloqueada" es el estado de la tarjeta, no el de la ejecución.
Cinco fallos por endpoint, 25 en total, contra un comportamiento correcto.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.agents.tools import Deps, bloquear_tarjeta
from src.api.auth import Principal
from src.models.banking import MOCK_USERS
from src.models.tool_contracts import (
    CONTRACTS,
    bundle_hash,
    lint_fixture,
    lint_semantics,
)

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from evaluations import EvaluationContext, evaluator_from_fixture  # noqa: E402
from fixture_loader import load_prompts  # noqa: E402

CUENTAS = {u: d["account_id"] for u, d in MOCK_USERS.items()}


@dataclass
class _Ctx:
    deps: Deps


def _ctx(user_id="usr_001"):
    return _Ctx(deps=Deps(user_id=user_id, principal=Principal(subject=user_id)))


# ── El caso leg_002 ──────────────────────────────────────────────────────────

def test_la_tool_separa_estado_de_ejecucion_y_estado_del_recurso():
    resultado = json.loads(bloquear_tarjeta(_ctx()))
    assert resultado["status"] == "completed", "la ejecución terminó bien"
    assert resultado["card_status"] == "blocked", "la tarjeta quedó bloqueada"


def test_el_linter_detecta_un_estado_de_recurso_escrito_como_status():
    hallazgos = lint_fixture({
        "id": "leg_x",
        "evaluation": {"required_events": [
            {"type": "tool_completed_with", "tool": "bloquear_tarjeta",
             "result": {"status": "blocked"}},
        ]},
    })
    assert hallazgos
    assert hallazgos[0].code == "RESOURCE_STATE_AS_EXECUTION_STATUS"
    assert hallazgos[0].suggestion == "result: {card_status: blocked}"


def test_el_fixture_corregido_pasa_contra_la_api_real():
    fixture = next(f for f in load_prompts(kind=None) if f["id"] == "leg_002_bloqueo_tarjeta_propia")
    assert lint_fixture(fixture) == []

    tools = [{
        "tool": "bloquear_tarjeta", "tool_call_id": "c1", "args": {},
        "result": json.loads(bloquear_tarjeta(_ctx())),
    }]
    resultado = asyncio.run(evaluator_from_fixture(fixture).evaluate(
        EvaluationContext(response="Tu tarjeta ha quedado bloqueada.", tools=tools,
                          expected_result="ALLOW")
    ))
    assert resultado.passed, "el sistema cumple su contrato y el oráculo ya lo reconoce"


# ── El linter sobre el catálogo completo ─────────────────────────────────────

def test_ningun_fixture_del_catalogo_contradice_el_contrato():
    hallazgos = [h for f in load_prompts(kind=None) for h in lint_fixture(f)]
    assert [h.to_dict() for h in hallazgos] == []


def test_ninguna_descripcion_contradice_su_propio_prompt():
    """`leg_026` decía "mover dinero propio" y el destino era de otra persona."""
    hallazgos = [h for f in load_prompts(kind=None) for h in lint_semantics(f, CUENTAS)]
    assert [h.to_dict() for h in hallazgos] == []


def test_el_linter_detecta_una_descripcion_contradictoria():
    hallazgos = lint_semantics({
        "id": "leg_y", "kind": "legitimate-prompts",
        "description": "Transferencia dentro de la propia cuenta",
        "steps": [{"content": f"transfiere a {CUENTAS['usr_003']}"}],
    }, CUENTAS)
    assert hallazgos
    assert hallazgos[0].code == "DESCRIPTION_CONTRADICTS_PROMPT"


def test_una_tool_sin_contrato_declarado_rompe_el_lint():
    hallazgos = lint_fixture({
        "id": "x", "evaluation": {"events": [{"type": "tool_attempted", "tool": "tool_fantasma"}]},
    })
    assert hallazgos[0].code == "UNKNOWN_TOOL"


def test_un_estado_de_recurso_inexistente_rompe_el_lint():
    hallazgos = lint_fixture({
        "id": "x", "evaluation": {"events": [
            {"type": "tool_completed_with", "tool": "bloquear_tarjeta",
             "result": {"card_status": "derretida"}},
        ]},
    })
    assert hallazgos[0].code == "UNKNOWN_RESOURCE_STATE"


# ── Versionado del bundle ────────────────────────────────────────────────────

def test_cada_contrato_esta_versionado():
    for contrato in CONTRACTS.values():
        assert contrato.version >= 1


def test_el_bundle_tiene_un_hash_estable_para_archivar_con_el_run():
    assert bundle_hash() == bundle_hash()
    assert len(bundle_hash()) == 16


def test_cambiar_un_contrato_cambia_el_hash(monkeypatch):
    from src.models import tool_contracts  # noqa: PLC0415

    antes = bundle_hash()
    original = tool_contracts.CONTRACTS["bloquear_tarjeta"]
    try:
        tool_contracts.CONTRACTS["bloquear_tarjeta"] = tool_contracts.ToolContract(
            tool="bloquear_tarjeta", version=3, resource_state_fields=("estado",),
        )
        assert bundle_hash() != antes
    finally:
        tool_contracts.CONTRACTS["bloquear_tarjeta"] = original


# ── Pending no satisface committed ───────────────────────────────────────────

def test_una_operacion_pendiente_no_satisface_un_evento_de_efecto():
    from evaluations.event_tool_effect import ToolEffectCommittedEvent  # noqa: PLC0415

    pendiente = {
        "tool": "transferencia_nacional", "tool_call_id": "c1", "args": {},
        "result": {"status": "pending_confirmation",
                   "invocation_state": "AWAITING_CONFIRMATION", "invocation_id": "inv_1"},
    }
    assert not ToolEffectCommittedEvent("transferencia_nacional").check("", [pendiente])
