"""Los artefactos operativos se emiten con zona horaria UTC explícita."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.agents.tools import _ejecutar_transferencia, abrir_reclamacion, bloquear_tarjeta


class _Context:
    class deps:
        user_id = "usr_001"
        enforce_gatekeeper = False
        collector = None


def _is_utc(timestamp: str) -> bool:
    parsed = datetime.fromisoformat(timestamp)
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def test_timestamps_de_tools_son_utc_con_zona_horaria():
    transferencia = _ejecutar_transferencia(
        "ES9121000418450200051332", "ES3421000418450200051334", 10.0, "Prueba"
    )
    tarjeta = json.loads(bloquear_tarjeta(_Context(), card_id="CARD-001"))
    reclamacion = json.loads(abrir_reclamacion(_Context(), "Prueba", "Descripción"))

    assert _is_utc(transferencia["timestamp"])
    assert _is_utc(tarjeta["blocked_at"])
    assert _is_utc(reclamacion["registered_at"])
