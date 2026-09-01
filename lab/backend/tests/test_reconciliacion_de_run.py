"""P09 — una repetición que falta no puede pasar por una suite completa.

El checker construía pares `(fixture, endpoint)`: un único Session File satisfacía la
combinación aunque el manifiesto pidiera cinco repeticiones. Una campaña con 2.293 de
2.305 ejecuciones se declaró correcta y `atk_040`/`complex-prompt` conservaba 2 de 5.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from check_suite_run import (  # noqa: E402
    EXIT_EVALUATION,
    EXIT_EVIDENCE,
    EXIT_EXECUTION,
    EXIT_OK,
    EXIT_PLAN,
    reconcile,
)

SESSION_TEMPLATE = """# Sesión `ses_x`

## Turno 1 — 00:00:00

**Fixture**: `{fixture_id}` · attack-prompts · expected: `BLOCK`

### Registro de turno

```json
{registro}
```
{evaluacion}
"""


def _run(tmp_path: Path, *, filas, eventos, sesiones=()):
    carpeta = tmp_path / "20260831_000000_qwen"
    (carpeta / "proxy-full").mkdir(parents=True)
    (carpeta / "coverage-plan.json").write_text(
        json.dumps({"schema_version": 1, "rows": filas}), encoding="utf-8",
    )
    (carpeta / "execution-ledger.jsonl").write_text(
        "\n".join(json.dumps(e) for e in eventos) + ("\n" if eventos else ""),
        encoding="utf-8",
    )
    for i, (exec_id, fixture_id, con_eval) in enumerate(sesiones):
        registro = json.dumps({"schema_version": 3, "fixture_execution_id": exec_id})
        (carpeta / "proxy-full" / f"s{i}.md").write_text(
            SESSION_TEMPLATE.format(
                fixture_id=fixture_id, registro=registro,
                evaluacion='\n<!-- eval: {"passed": true} -->\n' if con_eval else "",
            ),
            encoding="utf-8",
        )
    return carpeta


def _fila(exec_id, fixture_id="atk_040", target="proxy-full", repetition=1):
    return {"fixture_execution_id": exec_id, "fixture_id": fixture_id,
            "target": target, "repetition": repetition}


def _finished(exec_id, status="COMPLETED", **extra):
    return {"event": "FINISHED", "fixture_execution_id": exec_id,
            "execution_status": status, **extra}


def _codes(informe):
    return {hallazgo["code"] for hallazgo in informe["findings"]}


# ── Repeticiones ─────────────────────────────────────────────────────────────

def test_repeat_3_exige_tres_identidades_no_una_combinacion(tmp_path):
    """El caso atk_040: dos repeticiones presentes de tres planificadas."""
    filas = [_fila(f"e{i}", repetition=i) for i in (1, 2, 3)]
    carpeta = _run(
        tmp_path, filas=filas,
        eventos=[_finished("e1"), _finished("e2")],
        sesiones=[("e1", "atk_040", True), ("e2", "atk_040", True)],
    )
    informe = reconcile(carpeta)
    assert informe["planned"] == 3
    assert informe["terminal"] == 2
    assert informe["reconciles"] is False
    assert "EXECUTION_MISSING" in _codes(informe)
    assert informe["exit_code"] == EXIT_EXECUTION


def test_dos_respuestas_identicas_siguen_siendo_dos_ejecuciones(tmp_path):
    filas = [_fila("e1", repetition=1), _fila("e2", repetition=2)]
    carpeta = _run(
        tmp_path, filas=filas, eventos=[_finished("e1"), _finished("e2")],
        sesiones=[("e1", "atk_040", True), ("e2", "atk_040", True)],
    )
    informe = reconcile(carpeta)
    assert informe["reconciles"] is True
    assert informe["exit_code"] == EXIT_OK


# ── Códigos distintos para problemas distintos ───────────────────────────────

def test_un_terminal_duplicado_tiene_su_propio_codigo(tmp_path):
    carpeta = _run(
        tmp_path, filas=[_fila("e1")],
        eventos=[_finished("e1"), _finished("e1")],
        sesiones=[("e1", "atk_040", True)],
    )
    assert "EXECUTION_DUPLICATE_TERMINAL" in _codes(reconcile(carpeta))


def test_un_reintento_declarado_no_es_un_duplicado(tmp_path):
    carpeta = _run(
        tmp_path, filas=[_fila("e1")],
        eventos=[_finished("e1", status="TECHNICAL_ERROR"),
                 _finished("e1", retry_of="e1")],
        sesiones=[("e1", "atk_040", True)],
    )
    assert "EXECUTION_DUPLICATE_TERMINAL" not in _codes(reconcile(carpeta))


def test_una_ejecucion_despachada_sin_terminal_se_distingue_de_una_no_lanzada(tmp_path):
    carpeta = _run(
        tmp_path, filas=[_fila("e1")],
        eventos=[{"event": "DISPATCHED", "fixture_execution_id": "e1"}],
    )
    assert "EXECUTION_NON_TERMINAL" in _codes(reconcile(carpeta))


def test_una_ejecucion_fuera_del_plan_es_un_aviso_no_un_error(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1")],
                   eventos=[_finished("e1"), _finished("e999")],
                   sesiones=[("e1", "atk_040", True)])
    informe = reconcile(carpeta)
    assert "EXECUTION_UNEXPECTED" in _codes(informe)
    inesperado = next(h for h in informe["findings"] if h["code"] == "EXECUTION_UNEXPECTED")
    assert inesperado["severity"] == "warning"


def test_un_error_tecnico_cuenta_como_estado_terminal(tmp_path):
    """Un fallo registrado es evidencia; un hueco silencioso, no."""
    carpeta = _run(
        tmp_path, filas=[_fila("e1")],
        eventos=[_finished("e1", status="TECHNICAL_ERROR")],
        sesiones=[("e1", "atk_040", True)],
    )
    informe = reconcile(carpeta)
    assert informe["terminal"] == 1
    assert "EXECUTION_MISSING" not in _codes(informe)


# ── Niveles y exit codes ─────────────────────────────────────────────────────

def test_sin_plan_el_nivel_plan_falla_con_su_propio_codigo(tmp_path):
    carpeta = tmp_path / "run"
    carpeta.mkdir()
    informe = reconcile(carpeta, level="plan")
    assert "PLAN_MISSING" in _codes(informe)
    assert informe["exit_code"] == EXIT_PLAN


def test_un_plan_con_identidades_repetidas_se_rechaza(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1"), _fila("e1", repetition=2)], eventos=[])
    assert "PLAN_DUPLICATE_ID" in _codes(reconcile(carpeta, level="plan"))


def test_una_clave_natural_repetida_se_rechaza(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1"), _fila("e2")], eventos=[])
    assert "PLAN_DUPLICATE_KEY" in _codes(reconcile(carpeta, level="plan"))


def test_una_ejecucion_terminada_sin_session_file_falla_en_nivel_evidence(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1")], eventos=[_finished("e1")])
    informe = reconcile(carpeta, level="evidence")
    assert "EVIDENCE_MISSING" in _codes(informe)
    assert informe["exit_code"] == EXIT_EVIDENCE


def test_un_session_file_sin_evaluacion_falla_solo_en_nivel_evaluation(tmp_path):
    carpeta = _run(
        tmp_path, filas=[_fila("e1")], eventos=[_finished("e1")],
        sesiones=[("e1", "atk_040", False)],
    )
    assert reconcile(carpeta, level="evidence")["exit_code"] == EXIT_OK
    informe = reconcile(carpeta, level="evaluation")
    assert "EVALUATION_MISSING" in _codes(informe)
    assert informe["exit_code"] == EXIT_EVALUATION


def test_el_nivel_acota_las_comprobaciones(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1")], eventos=[])
    assert reconcile(carpeta, level="plan")["exit_code"] == EXIT_OK
    assert reconcile(carpeta, level="execution")["exit_code"] == EXIT_EXECUTION


def test_el_informe_es_determinista(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1"), _fila("e2", repetition=2)],
                   eventos=[_finished("e1")], sesiones=[("e1", "atk_040", True)])
    assert reconcile(carpeta) == reconcile(carpeta)


def test_el_checker_usa_el_plan_archivado_no_el_catalogo_actual(tmp_path):
    """Un fixture retirado del catálogo no puede convertir un run pasado en incompleto."""
    carpeta = _run(
        tmp_path, filas=[_fila("e1", fixture_id="atk_retirado")],
        eventos=[_finished("e1")], sesiones=[("e1", "atk_retirado", True)],
    )
    informe = reconcile(carpeta)
    assert informe["reconciles"] is True


def test_cada_hallazgo_sugiere_como_repararlo(tmp_path):
    carpeta = _run(tmp_path, filas=[_fila("e1")], eventos=[])
    hallazgo = next(h for h in reconcile(carpeta)["findings"] if h["code"] == "EXECUTION_MISSING")
    assert "--id atk_040" in hallazgo["repair"]
