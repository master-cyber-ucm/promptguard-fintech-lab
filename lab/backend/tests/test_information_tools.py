"""Pruebas de las tools informativas de Clara.

Cubren la separación entre datos dinámicos de la cuenta autenticada y artículos
versionados de la base de conocimiento. Ninguna de estas tools modifica estado.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.agents.tools import Deps, KB_ARTICLES, get_account_summary, get_kb_article


OWN_ACCOUNT = "ES9121000418450200051332"


@dataclass
class _FakeRunContext:
    deps: Deps


def _ctx(user_id: str = "usr_001") -> _FakeRunContext:
    return _FakeRunContext(deps=Deps(user_id=user_id))


def test_get_account_summary_resuelve_la_cuenta_autenticada():
    result = json.loads(get_account_summary(_ctx()))

    assert result["status"] == "ok"
    assert result["account_id"] == OWN_ACCOUNT
    assert result["account_id_masked"] == "ES91····1332"
    assert result["available_balance"] == "15,420.50 €"
    assert result["as_of"]


def test_get_kb_article_devuelve_el_articulo_versionado_por_clave():
    result = json.loads(get_kb_article("payments.sepa.overview"))

    assert result["schema_version"] == 1
    assert result["status"] == "ok"
    assert result["key"] == "payments.sepa.overview"
    assert result["version"]
    assert result["title"] == "Transferencias SEPA"
    assert "IBAN" in result["content"]


def test_get_kb_article_informa_las_claves_definidas_si_no_existe_la_solicitada():
    result = json.loads(get_kb_article("loans.hypothetical.keypoints"))

    assert result["status"] == "not_found"
    assert "documents.summary.missing_input" in result["available_keys"]


def test_la_base_de_conocimiento_cubre_los_playbooks_informativos_p1():
    assert set(KB_ARTICLES) == {
        "app.consultar_saldo",
        "payments.sepa.overview",
        "credentials.password.change",
        "documents.summary.missing_input",
        "privacy.erasure.request",
        "transfers.guidance",
        "own_accounts.transfer.guidance",
        "delegations.power_of_attorney.guidance",
    }
