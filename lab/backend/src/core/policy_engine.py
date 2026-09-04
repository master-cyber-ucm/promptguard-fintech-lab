"""Motor único de política: el YAML es la fuente de verdad, no una decoración.

P19: `tool_permissions.yaml` declaraba `daily_limit`, `requires_approval_above`,
`allowed_roles` y `required_params`, pero la ejecución no las aplicaba de manera
uniforme. `requires_approval: true` y `requires_approval_above: 1000` convivían, y
ganaba el primero: TODA transferencia autorizada quedaba pendiente, con independencia
del importe. El `daily_limit` estaba declarado y no se aplicaba en absoluto, así que
varias operaciones individualmente válidas podían superar el total diario.

Revisar el YAML no permitía conocer la política efectiva. Ahora:

* una sola función decide, y devuelve `ALLOW | DENY | REQUIRE_CONFIRMATION` con
  `rule_id` y versión — la decisión es reconciliable con la línea del YAML;
* `approval.mode` sustituye al par ambiguo: `never | always | above_threshold`;
* el acumulado diario se reserva y se consume de forma transaccional;
* una policy inválida **bloquea** al arrancar; no hay fallback permisivo.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

POLICY_SCHEMA_VERSION = 2


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Effect(_Str):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_CONFIRMATION = "REQUIRE_CONFIRMATION"


class ApprovalMode(_Str):
    """Cuándo hace falta una autorización independiente."""

    NEVER = "never"
    ALWAYS = "always"
    ABOVE_THRESHOLD = "above_threshold"


class PolicyError(ValueError):
    """La configuración no puede compilarse. Fail-closed: nada se ejecuta."""


@dataclass(frozen=True)
class PolicyDecision:
    """Resultado tipado de evaluar Principal, acción, recurso y contexto."""

    effect: Effect
    rule_id: str
    policy_version: int = POLICY_SCHEMA_VERSION
    reason: str = ""
    threshold: float | None = None
    remaining_daily: float | None = None

    @property
    def allowed(self) -> bool:
        return self.effect != Effect.DENY

    def to_dict(self) -> dict:
        return {
            "effect": str(self.effect),
            "rule_id": self.rule_id,
            "policy_version": self.policy_version,
            "reason": self.reason,
            "threshold": self.threshold,
            "remaining_daily": self.remaining_daily,
        }


@dataclass(frozen=True)
class RoleLimits:
    max_amount: float | None = None
    daily_limit: float | None = None
    approval_mode: ApprovalMode = ApprovalMode.ALWAYS
    approval_threshold: float | None = None


@dataclass(frozen=True)
class ToolPolicy:
    tool: str
    allowed_roles: tuple[str, ...]
    require_own_account: bool = True
    required_params: tuple[str, ...] = ()
    forbidden_params: tuple[str, ...] = ()
    limits: dict[str, RoleLimits] = field(default_factory=dict)
    default_approval: ApprovalMode = ApprovalMode.NEVER

    def limits_for(self, role: str) -> RoleLimits:
        return self.limits.get(role, RoleLimits(approval_mode=self.default_approval))


_KNOWN_TOOL_FIELDS = {
    "description", "risk_level", "allowed_roles", "require_own_account",
    "max_amount_visible", "requires_approval", "approval", "limits",
    "required_params", "forbidden_params",
}
_KNOWN_LIMIT_FIELDS = {"max_amount", "daily_limit", "requires_approval_above", "approval"}


def compile_policy(raw: dict) -> dict[str, ToolPolicy]:
    """Compila y valida el YAML. Un campo desconocido es un error, no un aviso.

    Tolerarlos permitía que una regla mal escrita pareciera activa: es exactamente la
    falsa confianza que P19 describe.
    """
    tools = (raw or {}).get("tools")
    if not isinstance(tools, dict) or not tools:
        raise PolicyError("la policy no declara ninguna tool")

    compiladas: dict[str, ToolPolicy] = {}
    for nombre, cfg in tools.items():
        if not isinstance(cfg, dict):
            raise PolicyError(f"{nombre}: la definición debe ser un objeto")
        desconocidos = sorted(set(cfg) - _KNOWN_TOOL_FIELDS)
        if desconocidos:
            raise PolicyError(f"{nombre}: campos desconocidos {desconocidos}")
        roles = cfg.get("allowed_roles")
        if not roles:
            raise PolicyError(f"{nombre}: sin allowed_roles — deny-by-default exige declararlos")

        limites: dict[str, RoleLimits] = {}
        for rol, valores in (cfg.get("limits") or {}).items():
            desconocidos = sorted(set(valores) - _KNOWN_LIMIT_FIELDS)
            if desconocidos:
                raise PolicyError(f"{nombre}.{rol}: campos desconocidos {desconocidos}")
            limites[rol] = _role_limits(nombre, rol, cfg, valores)

        compiladas[nombre] = ToolPolicy(
            tool=nombre,
            allowed_roles=tuple(roles),
            require_own_account=bool(cfg.get("require_own_account", True)),
            required_params=tuple(cfg.get("required_params") or ()),
            forbidden_params=tuple(cfg.get("forbidden_params") or ()),
            limits=limites,
            default_approval=_default_approval(nombre, cfg),
        )
    return compiladas


def _default_approval(tool: str, cfg: dict) -> ApprovalMode:
    modo = (cfg.get("approval") or {}).get("mode")
    if modo is not None:
        return _approval_mode(tool, modo)
    # Compatibilidad con el schema v1: `requires_approval` booleano.
    return ApprovalMode.ALWAYS if cfg.get("requires_approval") else ApprovalMode.NEVER


def _role_limits(tool: str, role: str, cfg: dict, valores: dict) -> RoleLimits:
    approval = valores.get("approval") or {}
    umbral = valores.get("requires_approval_above")
    if approval.get("mode"):
        modo = _approval_mode(tool, approval["mode"])
        umbral = approval.get("threshold", umbral)
    elif umbral is not None:
        # El par ambiguo del schema v1: un umbral declarado significa "por encima de",
        # no "siempre". Antes ganaba `requires_approval: true` y el umbral no hacía nada.
        modo = ApprovalMode.ABOVE_THRESHOLD
    else:
        modo = _default_approval(tool, cfg)

    if modo == ApprovalMode.ABOVE_THRESHOLD and umbral is None:
        raise PolicyError(f"{tool}.{role}: approval above_threshold sin umbral declarado")
    return RoleLimits(
        max_amount=valores.get("max_amount"),
        daily_limit=valores.get("daily_limit"),
        approval_mode=modo,
        approval_threshold=umbral,
    )


def _approval_mode(tool: str, valor) -> ApprovalMode:
    texto = str(valor).lower()
    if texto not in {m.value for m in ApprovalMode}:
        raise PolicyError(f"{tool}: approval.mode desconocido {valor!r}")
    return ApprovalMode(texto)


# ── Acumulado diario transaccional ───────────────────────────────────────────

@dataclass
class _Reservation:
    reservation_id: str
    subject: str
    tool: str
    amount: float
    day: str
    consumed: bool = False
    released: bool = False


class DailyLedger:
    """Reserva y consumo del cupo diario.

    Comprobar el acumulado y después ejecutar deja una ventana en la que dos
    transferencias concurrentes pasan el mismo cheque. Aquí se **reserva** dentro del
    lock y solo después se ejecuta: el cupo no puede excederse por una carrera.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._reservations: dict[str, _Reservation] = {}
        self._next_id = 0

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def used(self, subject: str, tool: str) -> float:
        with self._lock:
            return self._used_locked(subject, tool)

    def _used_locked(self, subject: str, tool: str) -> float:
        hoy = self._today()
        return sum(
            r.amount for r in self._reservations.values()
            if r.subject == subject and r.tool == tool and r.day == hoy and not r.released
        )

    def reserve(self, subject: str, tool: str, amount: float, limit: float | None) -> str | None:
        """Reserva cupo. Devuelve el id, o `None` si no cabe."""
        with self._lock:
            if limit is not None and self._used_locked(subject, tool) + amount > limit:
                return None
            self._next_id += 1
            reservation_id = f"res_{self._next_id}"
            self._reservations[reservation_id] = _Reservation(
                reservation_id=reservation_id, subject=subject, tool=tool,
                amount=amount, day=self._today(),
            )
            return reservation_id

    def consume(self, reservation_id: str) -> bool:
        with self._lock:
            reserva = self._reservations.get(reservation_id)
            if reserva is None or reserva.consumed or reserva.released:
                return False
            reserva.consumed = True
            return True

    def release(self, reservation_id: str) -> bool:
        """Libera una reserva no consumida. Exactamente una vez."""
        with self._lock:
            reserva = self._reservations.get(reservation_id)
            if reserva is None or reserva.consumed or reserva.released:
                return False
            reserva.released = True
            return True

    def reset_for_tests(self) -> None:
        with self._lock:
            self._reservations.clear()
            self._next_id = 0


default_ledger = DailyLedger()


# ── Decisión ─────────────────────────────────────────────────────────────────

DENY_UNKNOWN_TOOL = PolicyDecision(
    effect=Effect.DENY,
    rule_id="deny_by_default.unknown_tool",
    reason="la tool no está declarada en la policy",
)


def decide(
    policies: dict[str, ToolPolicy],
    *,
    tool: str,
    role: str,
    params: dict,
    subject: str = "",
    amount: float | None = None,
    ledger: DailyLedger | None = None,
) -> tuple[PolicyDecision, str | None]:
    """Evalúa la política efectiva. Devuelve la decisión y la reserva de cupo si la hay.

    El orden importa y es el mismo para todas las tools: tool declarada → rol
    permitido → parámetros → límite individual → cupo diario → aprobación.
    """
    politica = policies.get(tool)
    if politica is None:
        return DENY_UNKNOWN_TOOL, None

    if role not in politica.allowed_roles:
        return PolicyDecision(
            Effect.DENY, f"{tool}.allowed_roles",
            reason=f"el rol {role!r} no está autorizado para esta tool",
        ), None

    prohibidos = sorted(set(politica.forbidden_params) & set(params))
    if prohibidos:
        return PolicyDecision(
            Effect.DENY, f"{tool}.forbidden_params",
            reason=f"parámetros prohibidos presentes: {prohibidos}",
        ), None

    faltantes = sorted(
        p for p in politica.required_params
        if params.get(p) in (None, "")
    )
    if faltantes:
        return PolicyDecision(
            Effect.DENY, f"{tool}.required_params",
            reason=f"faltan parámetros obligatorios: {faltantes}",
        ), None

    limites = politica.limits_for(role)

    if amount is not None and limites.max_amount is not None and amount > limites.max_amount:
        return PolicyDecision(
            Effect.DENY, f"{tool}.limits.{role}.max_amount",
            reason="el importe supera el máximo permitido para el rol",
            threshold=limites.max_amount,
        ), None

    reserva = None
    restante = None
    if amount is not None and limites.daily_limit is not None:
        ledger = ledger or default_ledger
        reserva = ledger.reserve(subject, tool, amount, limites.daily_limit)
        if reserva is None:
            return PolicyDecision(
                Effect.DENY, f"{tool}.limits.{role}.daily_limit",
                reason="la operación supera el acumulado diario del rol",
                threshold=limites.daily_limit,
                remaining_daily=max(0.0, limites.daily_limit - ledger.used(subject, tool)),
            ), None
        restante = max(0.0, limites.daily_limit - ledger.used(subject, tool))

    if limites.approval_mode == ApprovalMode.ALWAYS:
        return PolicyDecision(
            Effect.REQUIRE_CONFIRMATION, f"{tool}.approval.always",
            reason="esta acción siempre requiere autorización independiente",
            remaining_daily=restante,
        ), reserva

    if limites.approval_mode == ApprovalMode.ABOVE_THRESHOLD:
        umbral = limites.approval_threshold
        if amount is not None and umbral is not None and amount > umbral:
            return PolicyDecision(
                Effect.REQUIRE_CONFIRMATION,
                f"{tool}.limits.{role}.requires_approval_above",
                reason="el importe supera el umbral de aprobación del rol",
                threshold=umbral, remaining_daily=restante,
            ), reserva
        return PolicyDecision(
            Effect.ALLOW, f"{tool}.limits.{role}.requires_approval_above",
            reason="el importe está por debajo del umbral de aprobación",
            threshold=umbral, remaining_daily=restante,
        ), reserva

    return PolicyDecision(
        Effect.ALLOW, f"{tool}.approval.never",
        reason="la acción no requiere autorización independiente",
        remaining_daily=restante,
    ), reserva


def dry_run(policies: dict[str, ToolPolicy], tool_names: list[str]) -> list[str]:
    """Tools registradas que la policy no cubre. Ninguna puede quedar sin mapping."""
    return sorted(nombre for nombre in tool_names if nombre not in policies)
