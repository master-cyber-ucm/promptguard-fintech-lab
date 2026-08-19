"""Cliente SOC — solo se usa en Modo caja gris.

Lee los Analysis Events de un Intento vía la API de lectura del SOC
(GET /soc/sessions/{session_id}), la misma que sirve al panel. En caja negra este
módulo no se importa desde la ruta de decisión — ver orchestrator.py.
"""

from __future__ import annotations

import httpx


def eventos_del_ultimo_turno(api_base: str, session_id: str) -> list[dict]:
    """Devuelve los Analysis Events (componente, acción, regla, razón) del último Turn
    de la sesión, o [] si la sesión no existe todavía (p.ej. quedó bloqueada antes de
    persistirse) o el SOC no responde — el agente sigue en caja negra ese Intento en
    vez de fallar la Campaña por un problema de observabilidad."""
    try:
        resp = httpx.get(f"{api_base}/soc/sessions/{session_id}", timeout=10.0)
        if resp.status_code != 200:
            return []
        turnos = resp.json().get("turnos", [])
        if not turnos:
            return []
        return turnos[-1].get("eventos", [])
    except Exception:
        return []
