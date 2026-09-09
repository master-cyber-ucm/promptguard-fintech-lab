"""P29 (feedback profesor 2026-09-05): el aviso de cobertura insuficiente vivía solo
como prosa bajo ## Cobertura, dos secciones antes de ## Resultado del sistema — la
tabla que un lector realmente se lleva. Aquí se comprueba que el mismo bloqueo es
visible fila a fila en esa tabla, no solo en un párrafo aparte.
"""

from __future__ import annotations

from scripts.report import _build_md, _compute_stats
from test_report_resultado_del_sistema import _muestra


def _run_data_con_cobertura(*, run_allowed: bool, blocked_endpoints: set[str]) -> dict:
    endpoints = ["proxy-baseline", "proxy-full"]
    by_target_gates = {
        ep: {
            "scope": ep,
            "allowed": ep not in blocked_endpoints,
            "blockers": (
                [] if ep not in blocked_endpoints
                else [f"cobertura evaluable 82.5% < 99.0%"]
            ),
        }
        for ep in endpoints
    }
    gates = {
        "run": {
            "scope": "run",
            "allowed": run_allowed,
            "blockers": [] if run_allowed else ["cobertura evaluable 87.5% < 99.0%"],
        },
        **by_target_gates,
    }
    coverage_cell = {
        "planned": 100, "conclusive": 90, "inconclusive": 10, "missing": 0,
        "technical_error": 0, "reconciles": True,
        "conservative_rate_pct": 30.0, "conditional_rate_pct": 33.3,
        "bounds_pct": [30.0, 40.0], "confidence_interval_pct": [25.0, 35.0],
    }
    return {
        "run_timestamp": "2026-09-05T00:00:00Z",
        "model": "qwen2.5:3b",
        "model_provenance": {"requested_model": "qwen2.5:3b", "provider": "ollama",
                             "effective_models_by_endpoint": {}, "instrumentation_errors": []},
        "endpoints_run": endpoints,
        "suite_config": {},
        "coverage": {
            "plan_present": True,
            "run": coverage_cell,
            "by_target": {ep: coverage_cell for ep in endpoints},
            "gates": gates,
        },
        "by_endpoint": {ep: _compute_stats(_muestra()) for ep in endpoints},
    }


def _fila_resultado_del_sistema(md: str, endpoint: str) -> str:
    """La tabla de ## Resultado del sistema, no cualquier otra que mencione el endpoint."""
    tabla = md[md.index("| Endpoint | Ataques | Infraestructura"):]
    return next(l for l in tabla.splitlines() if l.startswith(f"| `{endpoint}` |"))


def test_la_tabla_de_resultado_marca_con_advertencia_los_endpoints_bloqueados():
    run_data = _run_data_con_cobertura(
        run_allowed=False, blocked_endpoints={"proxy-full"},
    )
    md = _build_md(run_data)

    assert "Gate cobertura" in md
    # proxy-full está bloqueado: su fila debe llevar el marcador de advertencia.
    assert _fila_resultado_del_sistema(md, "proxy-full").rstrip().endswith("| ⚠ |")
    # proxy-baseline no está bloqueado: su fila debe llevar el marcador positivo.
    assert _fila_resultado_del_sistema(md, "proxy-baseline").rstrip().endswith("| ✅ |")


def test_el_run_bloqueado_muestra_un_aviso_antes_de_la_tabla_no_solo_en_cobertura():
    run_data = _run_data_con_cobertura(
        run_allowed=False, blocked_endpoints={"proxy-full"},
    )
    md = _build_md(run_data)

    idx_resultado = md.index("## Resultado del sistema")
    idx_aviso = md.index("La cobertura de este run no alcanza el gate del proyecto")
    idx_tabla = md.index("| Endpoint | Ataques | Infraestructura")
    # El aviso vive dentro de ## Resultado del sistema, antes de su tabla —
    # un lector que salta directo a esa sección ya no puede perdérselo.
    assert idx_resultado < idx_aviso < idx_tabla


def test_el_run_no_bloqueado_no_muestra_ningun_aviso():
    run_data = _run_data_con_cobertura(run_allowed=True, blocked_endpoints=set())
    md = _build_md(run_data)

    assert "La cobertura de este run no alcanza el gate del proyecto" not in md
    assert "Por qué falla `Gate cobertura`" not in md
    assert _fila_resultado_del_sistema(md, "proxy-full").rstrip().endswith("| ✅ |")


def test_la_razon_del_bloqueo_se_publica_junto_a_la_tabla():
    run_data = _run_data_con_cobertura(
        run_allowed=False, blocked_endpoints={"proxy-full"},
    )
    md = _build_md(run_data)

    assert "Por qué falla `Gate cobertura` (⚠):" in md
    assert "`proxy-full`: cobertura evaluable 82.5% < 99.0%" in md
    # proxy-baseline no está bloqueado: no debe aparecer en la lista de motivos.
    seccion = md[md.index("Por qué falla `Gate cobertura`"):]
    seccion = seccion[:seccion.index("| Endpoint | Efecto dañino")]
    assert "`proxy-baseline`" not in seccion
