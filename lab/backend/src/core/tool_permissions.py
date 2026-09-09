"""Conecta `config/rules/tool_permissions.yaml` al Tool Gatekeeper — límites de importe,
aprobación fuera de banda y parámetros prohibidos.

Hasta este módulo, `tool_permissions.yaml` era config muerta: 0 referencias en `src/`, el
Gatekeeper solo verificaba propiedad de cuenta (`agents/tools.py::_owns_account`). Ver
la validación histórica conservada en Git — el Agente de red-team
reprodujo en vivo (transferencia real sin confirmación) el vector exacto que este YAML ya
declaraba sin que nada lo aplicara.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from src.core import policy_engine
from src.utils.crypto import sign_payload

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "rules" / "tool_permissions.yaml"
_PERMISOS: Optional[dict[str, Any]] = None
_COMPILADA: Optional[dict] = None

# TTL de una confirmación pendiente. El diseño (acciones-no-autorizadas.md §4) pide que
# la confirmación tenga TTL corto y sea de un solo uso — ambas propiedades se aplican en
# `confirmar()`.
TTL_SEGUNDOS = 120


def _cargar() -> dict[str, Any]:
    global _PERMISOS
    if _PERMISOS is None:
        data = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        _PERMISOS = data.get("tools", {})
    return _PERMISOS


def recargar() -> None:
    """Fuerza releer el YAML — usado por los tests para no compartir estado entre casos."""
    global _PERMISOS, _COMPILADA
    _PERMISOS = None
    _COMPILADA = None


def politica_compilada() -> dict:
    """Policy compilada y validada. Falla al arrancar si el YAML es inválido.

    Fail-closed: una configuración que no compila no puede degradar a "permitir todo"
    — sería exactamente la falsa confianza que P19 documenta.
    """
    global _COMPILADA
    if _COMPILADA is None:
        _COMPILADA = policy_engine.compile_policy({"tools": _cargar()})
    return _COMPILADA


def snapshot() -> dict[str, Any]:
    """Copia de solo lectura de la policy efectiva.

    La usa la Postura experimental para hashear la policy con la que corrió un turno:
    dos posturas que difieren en `tool_permissions.yaml` no son comparables aunque
    tengan los mismos controles activos.
    """
    return dict(_cargar())


def permisos_de(tool: str) -> Optional[dict]:
    """None si la tool no está declarada en el YAML — fail-closed: quien llama debe
    denegar la ejecución, no asumir permisos por defecto (diseño §4.1)."""
    return _cargar().get(tool)


def limite_para(tool: str, role: str) -> Optional[dict]:
    permisos = permisos_de(tool)
    if not permisos:
        return None
    return (permisos.get("limits") or {}).get(role)


def forbidden_presentes(tool: str, kwargs: dict) -> list[str]:
    """Parámetros que el LLM intentó pasar y que el YAML declara prohibidos para esta
    tool (`override_limit`, `bypass_approval`, `admin_mode`, ...)."""
    permisos = permisos_de(tool) or {}
    prohibidos = set(permisos.get("forbidden_params", []))
    return sorted(prohibidos & set(kwargs.keys()))


# --- Confirmación fuera de banda ---
#
# En un despliegue real el token viajaría por push/SMS — un canal que el propio ataque no
# puede tocar (ver README de la categoría, "confirmación humana cómo se hace bien"). En
# el lab, sin canal push real, el token se devuelve en la misma respuesta de la tool para
# poder probar el flujo end-to-end con `curl`/el Agente de red-team — está documentado
# como simplificación de laboratorio, no como el diseño de producción.

_PENDIENTES: dict[str, dict[str, Any]] = {}


def crear_pendiente(*, tool: str, user_id: str, detalle: dict, ejecutar: Callable[[], dict]) -> tuple[str, str]:
    """Registra una operación pendiente de confirmación. `ejecutar` se evalúa de forma
    perezosa — nunca al crear el pendiente — para que nada ocurra sin el paso de
    confirmación."""
    operation_id = f"op_{uuid.uuid4().hex[:12]}"
    token = sign_payload({"operation_id": operation_id, "tool": tool, "user_id": user_id})
    _PENDIENTES[operation_id] = {
        "token": token, "tool": tool, "user_id": user_id, "detalle": detalle,
        "ejecutar": ejecutar, "expira_en": time.time() + TTL_SEGUNDOS, "consumida": False,
    }
    return operation_id, token


def confirmar(operation_id: str, token: str, user_id: str) -> dict:
    """Ejecuta la operación pendiente si el token es válido, no expiró y no se consumió
    ya. Devuelve el resultado real de la tool, o `{"status": "denied", "reason": ...}`."""
    pendiente = _PENDIENTES.get(operation_id)
    if pendiente is None:
        return {"status": "denied", "reason": "operation_id desconocido o ya procesado"}
    if pendiente["user_id"] != user_id:
        return {"status": "denied", "reason": "La operación pendiente no pertenece a este usuario"}
    if pendiente["consumida"]:
        return {"status": "denied", "reason": "Token de un solo uso ya consumido"}
    if time.time() > pendiente["expira_en"]:
        del _PENDIENTES[operation_id]
        return {"status": "denied", "reason": f"Confirmación expirada (TTL {TTL_SEGUNDOS}s)"}
    if token != pendiente["token"]:
        return {"status": "denied", "reason": "Token inválido"}
    pendiente["consumida"] = True
    resultado = pendiente["ejecutar"]()
    del _PENDIENTES[operation_id]
    return resultado


def limpiar_pendientes() -> None:
    """Usado por los tests para no compartir estado entre casos."""
    _PENDIENTES.clear()
