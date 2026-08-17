"""Cliente hacia el target: Clara vía el backend del lab.

Mismo patrón que run_attack_suite.py: `audit_subdir` viaja como ruta CONTENEDOR
(el backend corre en Docker con ./audit:/app/audit montado) — nunca la ruta host.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

AUDIT_RUNS_DIR_CONTAINER = "/app/audit/runs"


@dataclass
class TurnoResultado:
    respuesta: str
    session_id: str
    error: str | None
    latency_ms: float
    tools_used: list


class TargetClient:
    def __init__(self, config, run_folder_name: str) -> None:
        self.config = config
        self.run_folder_name = run_folder_name
        self._client = httpx.Client(timeout=90.0)

    def audit_subdir_para(self, ejercicio_id: str) -> str:
        return f"{AUDIT_RUNS_DIR_CONTAINER}/{self.run_folder_name}/{ejercicio_id}"

    def enviar(
        self, *, mensaje: str, ejercicio_id: str, session_id: str | None = None,
    ) -> TurnoResultado:
        body = {
            "user_id": self.config.user_id,
            "message": mensaje,
            "audit_subdir": self.audit_subdir_para(ejercicio_id),
            "vulnerable": self.config.vulnerable,
        }
        if session_id:
            body["session_id"] = session_id
        t0 = time.time()
        try:
            resp = self._client.post(f"{self.config.api_base}{self.config.endpoint_path}", json=body)
            data = resp.json()
        except Exception as exc:  # backend caído, timeout, etc. — se registra como Intento fallido
            return TurnoResultado(
                respuesta="", session_id=session_id or "", error=str(exc),
                latency_ms=(time.time() - t0) * 1000, tools_used=[],
            )
        return TurnoResultado(
            respuesta=data.get("response", ""),
            session_id=data.get("session_id", session_id or ""),
            error=data.get("error"),
            latency_ms=data.get("latency_ms", (time.time() - t0) * 1000),
            tools_used=data.get("tools_used", []),
        )

    def close(self) -> None:
        self._client.close()
