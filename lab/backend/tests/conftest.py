"""Configuración común de la suite de tests.

Aísla el almacén del SOC. Sin esto, cualquier test que ejercite un endpoint de chat
—y hay varios: `test_proxy_pipeline_vectores`, `test_confused_deputy_fixtures`,
`test_documento_exfiltracion_pii`…— escribe turnos reales en `lab/audit/soc.db`, la
base que alimenta el panel. Se detectó cuando la pantalla de Corridas empezó a listar
identificadores como `test_el_turno_bloqueado_deja_s0` junto a las campañas de verdad.

El aislamiento es de sesión y automático: ningún test tiene que acordarse de pedirlo.
"""

from __future__ import annotations

import pytest

from src.soc import store


@pytest.fixture(autouse=True, scope="session")
def _soc_aislado(tmp_path_factory):
    """Redirige el SOC a una base temporal durante toda la sesión de tests."""
    original = store.DB_PATH
    store.reset_for_tests(tmp_path_factory.mktemp("soc") / "soc.db")
    yield
    store.reset_for_tests(original)


@pytest.fixture(autouse=True)
def _policy_ledger_limpio():
    """Aísla el acumulado diario de la policy entre tests (P19).

    El `daily_limit` es estado compartido por proceso y ahora SÍ se aplica: sin este
    reset, una decena de tests que transfieren 1.500 € agotarían el cupo de `usr_001`
    y los siguientes verían denegaciones que no tienen nada que ver con su caso.
    """
    from src.core.policy_engine import default_ledger
    from src.core import transaction_authorization

    default_ledger.reset_for_tests()
    transaction_authorization.reset_for_tests()
    yield
    default_ledger.reset_for_tests()
    transaction_authorization.reset_for_tests()


@pytest.fixture(autouse=True)
def _llm10_guards_limpios():
    """Aísla Rate Limiter y Budget Guard (#8/#9, LLM10:2025) entre tests.

    Ambos son estado compartido por proceso (`core/rate_limiter.py`,
    `core/budget_guard.py`) — varios tests reutilizan `user_id="usr_001"` contra
    `/chat/proxy` (`test_proxy_pipeline_vectores.py`, `test_soc.py`...). Sin este reset,
    el orden de ejecución de la suite podría hacer que un test agotara la cuota que
    necesita otro — mismo motivo que `_soc_aislado`, aplicado a los guards nuevos.
    """
    from src.core.budget_guard import default_guard
    from src.core.rate_limiter import default_limiter

    default_limiter.reset()
    default_guard.reset()
    yield
    default_limiter.reset()
    default_guard.reset()
