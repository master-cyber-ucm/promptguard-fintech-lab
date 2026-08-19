"""Rate Limiter — contra Denegación de Servicio (#8, LLM10:2025).

Antes de este módulo, `main.py` no montaba ningún límite de peticiones: nada impedía
N peticiones/segundo a `/chat/*` desde el mismo origen. Ver
docs/defensas/LLM10-unbounded-consumption/denegacion-de-servicio.md §3.1.

Token bucket en memoria, por origen (`user_id`). Deliberadamente simple — sin Redis,
mismo principio que `session_store.py` — porque el lab corre en un solo proceso; el
diseño declara Redis como paso siguiente si el despliegue pasa a multi-instancia (ver
README de la categoría).

Se invoca dentro de `_process_chat` (mismo punto que Input Sanitizer/PII Shield), no
como middleware ASGI delante del body — decisión deliberada de consistencia: así
respeta el flag `vulnerable` de `ChatRequest` igual que el resto de defensas del
proyecto, lo que permite generar evidencia vulnerable-vs-defendida con la misma
metodología ya establecida (`lab/scripts/run_llm10_suite.py`), en vez de un mecanismo
de comparación aparte. El coste de deserializar el body antes del corte es el mismo
que ya paga cualquier otra defensa del pipeline.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

# Peticiones por ventana y tamaño de la ventana — configurables porque el límite
# correcto depende del patrón de tráfico legítimo real, no de un valor universal.
DEFAULT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", 30))
DEFAULT_WINDOW_SECONDS = float(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", 60))


@dataclass
class _Bucket:
    marcas: list[float] = field(default_factory=list)


class RateLimiter:
    """Ventana deslizante por clave (IP, o IP+user_id si se conoce). Barata: solo
    guarda timestamps, no cuenta acumulativa que requiera reset explícito."""

    def __init__(self, max_requests: int = DEFAULT_MAX_REQUESTS, window_seconds: float = DEFAULT_WINDOW_SECONDS) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def permitir(self, clave: str) -> tuple[bool, float]:
        """True si la petición entra dentro de la cuota; si no, además devuelve los
        segundos hasta que la más antigua de la ventana expire (para `Retry-After`)."""
        ahora = time.time()
        limite_ventana = ahora - self.window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(clave, _Bucket())
            bucket.marcas = [m for m in bucket.marcas if m > limite_ventana]
            if len(bucket.marcas) >= self.max_requests:
                retry_after = bucket.marcas[0] + self.window_seconds - ahora
                return False, max(retry_after, 0.0)
            bucket.marcas.append(ahora)
            return True, 0.0

    def reset(self) -> None:
        """Vacía todos los buckets — usado por los tests para no compartir estado."""
        with self._lock:
            self._buckets.clear()


# Instancia compartida por el proceso — igual que `session_store._store`, un solo
# almacén por proceso backend, no por request.
default_limiter = RateLimiter()
