"""El runner debe llegar a escribir sus artefactos y a despachar tráfico.

`--help` sale antes del cuerpo de `main()`, así que no prueba el pre-vuelo: una corrida
completa se cayó con `UnboundLocalError` porque el manifiesto usaba la procedencia antes
de construirla, y el fallo solo apareció con la suite real ya lanzada.

Aquí se ejecuta el runner de verdad —en el layout del contenedor y contra un backend de
mentira— y se comprueba que los cuatro artefactos quedan escritos y reconcilian entre sí.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[2]


class _BackendFalso(BaseHTTPRequestHandler):
    """Responde lo justo para que el runner complete su ciclo."""

    def _json(self, payload: dict) -> None:
        cuerpo = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):  # noqa: N802 - lo impone BaseHTTPRequestHandler
        self._json({"provider": "stub", "configured_model": "stub-model"})

    def do_POST(self):  # noqa: N802
        longitud = int(self.headers.get("Content-Length", 0))
        cuerpo = json.loads(self.rfile.read(longitud) or b"{}")
        self._json({
            "user_id": "usr_001",
            "message": cuerpo.get("message", ""),
            "response": "No puedo ayudarte con eso.",
            "model": "stub-model",
            "latency_ms": 1.0,
            "session_id": cuerpo.get("session_id") or "ses_stub",
            "tools_used": [],
            "endpoint": "proxy",
            "audit_file": None,
            "error": None,
            "block_code": None,
            "effective_posture": {
                "proxy": True, "vulnerable": False, "shadow": False,
                "input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
                "output_auditor": False, "leak_guard": False,
            },
            "execution_status": "COMPLETED",
        })

    def log_message(self, *args):  # silencia el log del servidor de prueba
        return


@pytest.fixture(scope="module")
def backend_falso():
    servidor = ThreadingHTTPServer(("127.0.0.1", 0), _BackendFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield servidor.server_address
    servidor.shutdown()


@pytest.fixture(scope="module")
def app_layout(tmp_path_factory) -> Path:
    """Árbol como lo monta el contenedor: `src` y `scripts` hermanos, sin `backend/`."""
    raiz = tmp_path_factory.mktemp("app")
    shutil.copytree(LAB / "scripts", raiz / "scripts")
    shutil.copytree(LAB / "backend" / "src", raiz / "src")
    shutil.copytree(LAB / "backend" / "config", raiz / "config")
    shutil.copytree(LAB / "backend" / "tests" / "fixtures", raiz / "tests" / "fixtures")
    (raiz / "audit" / "runs").mkdir(parents=True)
    return raiz


@pytest.fixture(scope="module")
def corrida(app_layout, backend_falso) -> tuple[Path, subprocess.CompletedProcess]:
    host, puerto = backend_falso
    resultado = subprocess.run(
        [sys.executable, "scripts/run_attack_suite.py",
         "--id", "atk_010", "--kind", "attack-prompts",
         "--endpoint", "proxy", "--proxy-profile", "baseline",
         "--repeat", "2", "--host", host, "--port", str(puerto)],
        cwd=app_layout, capture_output=True, text=True, timeout=180,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "FIXTURES_DIR": str(app_layout / "tests" / "fixtures")},
    )
    carpetas = sorted((app_layout / "audit" / "runs").iterdir())
    return (carpetas[-1] if carpetas else app_layout), resultado


def test_el_runner_completa_sin_excepciones(corrida):
    _, resultado = corrida
    assert "Traceback" not in resultado.stderr, resultado.stderr
    assert resultado.returncode == 0, resultado.stderr


def test_escribe_los_cuatro_artefactos_del_prevuelo(corrida):
    run, _ = corrida
    for artefacto in ("suite-config.json", "provenance.json",
                      "coverage-plan.json", "execution-ledger.jsonl"):
        assert (run / artefacto).is_file(), f"falta {artefacto}"


def test_el_manifiesto_incorpora_la_procedencia(corrida):
    """El orden importa: el manifiesto consume la procedencia y se escribía antes."""
    run, _ = corrida
    manifiesto = json.loads((run / "suite-config.json").read_text(encoding="utf-8"))
    assert "git_commit" in manifiesto
    assert "provenance_fingerprint" in manifiesto
    assert manifiesto["seed"]


def test_el_plan_declara_una_fila_por_ejecucion(corrida):
    run, _ = corrida
    plan = json.loads((run / "coverage-plan.json").read_text(encoding="utf-8"))
    assert len(plan["rows"]) == 2, "un fixture × un target × dos repeticiones"
    assert {fila["repetition"] for fila in plan["rows"]} == {1, 2}
    assert len({fila["fixture_execution_id"] for fila in plan["rows"]}) == 2


def test_el_ledger_registra_el_ciclo_de_cada_ejecucion(corrida):
    run, _ = corrida
    eventos = [
        json.loads(linea)
        for linea in (run / "execution-ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]
    por_tipo = {"PLANNED": 0, "DISPATCHED": 0, "FINISHED": 0}
    for evento in eventos:
        por_tipo[evento["event"]] = por_tipo.get(evento["event"], 0) + 1
    assert por_tipo == {"PLANNED": 2, "DISPATCHED": 2, "FINISHED": 2}


def test_cada_ejecucion_registra_su_postura_efectiva(corrida):
    run, _ = corrida
    ejecuciones = json.loads((run / "executions.json").read_text(encoding="utf-8"))
    assert len(ejecuciones) == 2
    for ejecucion in ejecuciones:
        assert ejecucion["posture"]["target"] == "proxy-baseline"
        assert ejecucion["posture_divergences"] == []


def test_el_checker_reconcilia_la_corrida(corrida, app_layout):
    run, _ = corrida
    resultado = subprocess.run(
        [sys.executable, "scripts/check_suite_run.py", "--run", run.name,
         "--level", "execution", "--json"],
        cwd=app_layout, capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "FIXTURES_DIR": str(app_layout / "tests" / "fixtures")},
    )
    informe = json.loads(resultado.stdout)
    assert informe["planned"] == 2
    assert informe["terminal"] == 2
    assert informe["reconciles"] is True
    assert resultado.returncode == 0


def test_el_run_folder_impreso_es_reutilizable(corrida, app_layout):
    """La ruta del log se vuelve a pasar por `--run`; tiene que resolver."""
    run, resultado = corrida
    lineas = [l for l in resultado.stdout.splitlines() if "Run Folder" in l]
    assert lineas
    impresa = lineas[-1].split(":", 1)[1].strip()
    assert (app_layout / impresa).resolve() == run.resolve()


def test_el_runner_exige_excepcion_explicita_para_arbol_sucio():
    runner = (LAB / "scripts" / "run_attack_suite.py").read_text(encoding="utf-8")
    assert '"--allow-dirty"' in runner
    assert "no agregable" in runner
