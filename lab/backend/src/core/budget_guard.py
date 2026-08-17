"""Budget Guard — contra Denial of Wallet (#9, LLM10:2025).

Antes de este módulo no existía ningún acumulador de tokens consumidos por usuario —
un volumen de peticiones, incluso por debajo del Rate Limiter, podía consumir tokens
sin límite superior. Ver
docs/defensas/LLM10-unbounded-consumption/denial-of-wallet.md §3.1.

Acumulador en memoria por `user_id`, con corte duro ANTES de llamar al proveedor
(§3.1 del diseño: "el corte tiene que estar en la unidad que el proveedor factura").
Se descuenta después de cada respuesta real (`result.usage()` de pydantic-ai), no se
estima por adelantado — el coste exacto de una petición solo se conoce tras la
respuesta.

Mismo patrón que `rate_limiter.py`: invocado dentro de `_process_chat`, respeta el
flag `vulnerable` de `ChatRequest` para poder generar evidencia comparable con la
metodología ya establecida del proyecto.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

# Presupuesto de tokens por usuario y ventana de reinicio — configurables porque el
# valor correcto depende del proveedor activo (ver denial-of-wallet.md §3.2: Ollama
# local no tiene coste monetario, un proveedor de pago sí).
DEFAULT_TOKEN_BUDGET = int(os.environ.get("BUDGET_GUARD_TOKEN_LIMIT", 20_000))
DEFAULT_WINDOW_SECONDS = float(os.environ.get("BUDGET_GUARD_WINDOW_SECONDS", 3600))  # 1h


@dataclass
class _Cuenta:
    consumidos: int = 0
    ventana_inicio: float = field(default_factory=time.time)


class BudgetGuard:
    """Corte duro por `user_id`: se comprueba ANTES de llamar al proveedor
    (`hay_presupuesto`) y se descuenta DESPUÉS con el consumo real (`registrar_consumo`).
    Ninguna llamada al proveedor ocurre entre ambas sin que el llamador las invoque —
    el propio guard no intercepta la llamada, solo informa la decisión."""

    def __init__(self, token_budget: int = DEFAULT_TOKEN_BUDGET, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self.token_budget = token_budget
        self.window_seconds = window_seconds
        self._cuentas: dict[str, _Cuenta] = {}
        self._lock = threading.Lock()

    def _cuenta_vigente_locked(self, user_id: str) -> _Cuenta:
        ahora = time.time()
        cuenta = self._cuentas.get(user_id)
        if cuenta is None or (ahora - cuenta.ventana_inicio) > self.window_seconds:
            cuenta = _Cuenta(consumidos=0, ventana_inicio=ahora)
            self._cuentas[user_id] = cuenta
        return cuenta

    def hay_presupuesto(self, user_id: str) -> tuple[bool, int]:
        """True si el usuario tiene presupuesto restante; siempre devuelve también los
        tokens ya consumidos en la ventana vigente (para el Analysis Event)."""
        with self._lock:
            cuenta = self._cuenta_vigente_locked(user_id)
            return cuenta.consumidos < self.token_budget, cuenta.consumidos

    def registrar_consumo(self, user_id: str, tokens: int) -> int:
        """Descuenta `tokens` del presupuesto vigente del usuario. Devuelve el total
        consumido en la ventana tras el descuento."""
        with self._lock:
            cuenta = self._cuenta_vigente_locked(user_id)
            cuenta.consumidos += max(tokens, 0)
            return cuenta.consumidos

    def restante(self, user_id: str) -> int:
        with self._lock:
            cuenta = self._cuenta_vigente_locked(user_id)
            return max(self.token_budget - cuenta.consumidos, 0)

    def reset(self) -> None:
        """Vacía todas las cuentas — usado por los tests para no compartir estado."""
        with self._lock:
            self._cuentas.clear()


default_guard = BudgetGuard()
