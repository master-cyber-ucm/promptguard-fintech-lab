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
