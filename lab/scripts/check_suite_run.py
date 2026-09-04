#!/usr/bin/env python3
"""Reconcilia un Run Folder contra su Plan de cobertura sellado.

P09: el checker anterior construía un conjunto de pares `(fixture, endpoint)`. Un solo
Session File satisfacía la combinación aunque el manifiesto pidiera cinco repeticiones,
así que una campaña con 2.293 de 2.305 ejecuciones se declaraba completa —
`atk_040`/`complex-prompt` conservaba 2 de 5 y nadie lo veía.

Ahora la unidad es la **Fixture Execution**, identificada por `fixture_execution_id` y
con clave natural `(run, fixture, target, repetición)`. Cada identidad planificada debe
tener exactamente un estado terminal en el ledger, aunque ese estado sea un error
técnico: un fallo registrado es evidencia; un hueco silencioso, no.

Niveles (`--level`), acumulativos:

    plan        el plan existe, está sellado y es coherente
    execution   cada identidad planificada tiene un terminal único
    evidence    cada ejecución terminada dejó su Session File
    evaluation  cada Session File tiene evaluación

Uso:
  python scripts/check_suite_run.py --run 20260827_133926_qwen2.5-3b
  python scripts/check_suite_run.py --run X --level execution --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab_paths import ensure_src_importable  # noqa: E402

ensure_src_importable()

RUNS_DIR = HERE.parent / "audit" / "runs"
FIXTURE_RE = re.compile(r"\*\*Fixture\*\*:\s*`([^`]+)`")
EXEC_ID_RE = re.compile(r'"fixture_execution_id":\s*"([^"]+)"')
EVAL_MARKER = "<!-- eval:"

LEVELS = ("plan", "execution", "evidence", "evaluation")

#: Exit codes estables: CI necesita distinguir qué gate falló, no solo que algo falló.
EXIT_OK = 0
EXIT_PLAN = 2
EXIT_EXECUTION = 3
EXIT_EVIDENCE = 4
EXIT_EVALUATION = 5

_EXIT_BY_LEVEL = {
    "plan": EXIT_PLAN,
    "execution": EXIT_EXECUTION,
    "evidence": EXIT_EVIDENCE,
    "evaluation": EXIT_EVALUATION,
}


@dataclass
class Finding:
    code: str
    severity: str
    level: str
    message: str
    fixture_execution_id: str | None = None
    artifacts: list[str] = field(default_factory=list)
    repair: str | None = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "severity": self.severity,
            "level": self.level,
            "message": self.message,
            "fixture_execution_id": self.fixture_execution_id,
            "artifacts": self.artifacts,
            "repair": self.repair,
        }


def _run_folder(name: str) -> Path:
    candidate = Path(name)
    if candidate.name != name or name in {".", ".."}:
        raise ValueError("--run debe ser solo el nombre de un Run Folder")
    return RUNS_DIR / name


def load_plan(folder: Path) -> dict | None:
    try:
        return json.loads((folder / "coverage-plan.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_ledger(folder: Path) -> list[dict]:
    try:
        texto = (folder / "execution-ledger.jsonl").read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    eventos = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            eventos.append(json.loads(linea))
        except json.JSONDecodeError:
            continue
    return eventos


def session_files(folder: Path) -> dict[str, list[Path]]:
    """Session Files indexados por `fixture_execution_id`.

    Se correlaciona por identidad, no por nombre de fichero ni por carpeta: dos
    repeticiones del mismo fixture producen ficheros distintos y hay que poder decir
    cuál corresponde a cuál.
    """
    por_id: dict[str, list[Path]] = {}
    for path in sorted(folder.rglob("*.md")):
        if path.name == "run.md":
            continue
        texto = path.read_text(encoding="utf-8", errors="replace")
        for exec_id in set(EXEC_ID_RE.findall(texto)):
            por_id.setdefault(exec_id, []).append(path)
    return por_id


# ── Niveles ──────────────────────────────────────────────────────────────────

def check_plan(folder: Path, plan: dict | None) -> list[Finding]:
    if plan is None:
        return [Finding(
            code="PLAN_MISSING", severity="error", level="plan",
            message=(
                "no hay coverage-plan.json: sin plan sellado el denominador se "
                "reconstruye contando ficheros y lo que falló desaparece"
            ),
            repair="vuelve a lanzar la suite con la versión actual del runner",
        )]
    filas = plan.get("rows") or []
    hallazgos: list[Finding] = []
    if not filas:
        hallazgos.append(Finding(
            code="PLAN_EMPTY", severity="error", level="plan",
            message="el plan no contiene ninguna ejecución planificada",
        ))
    identidades = Counter(fila["fixture_execution_id"] for fila in filas)
    for exec_id, veces in identidades.items():
        if veces > 1:
            hallazgos.append(Finding(
                code="PLAN_DUPLICATE_ID", severity="error", level="plan",
                message=f"el plan repite el identificador {exec_id} {veces} veces",
                fixture_execution_id=exec_id,
            ))
    claves = Counter(
        (fila["fixture_id"], fila["target"], fila["repetition"]) for fila in filas
    )
    for clave, veces in claves.items():
        if veces > 1:
            hallazgos.append(Finding(
                code="PLAN_DUPLICATE_KEY", severity="error", level="plan",
                message=f"clave natural repetida en el plan: {clave} ({veces} veces)",
            ))
    return hallazgos


def check_execution(plan: dict, ledger: list[dict]) -> list[Finding]:
    """Cada identidad planificada, exactamente un estado terminal."""
    hallazgos: list[Finding] = []
    filas = {fila["fixture_execution_id"]: fila for fila in (plan.get("rows") or [])}

    terminales: dict[str, list[dict]] = {}
    despachadas: set[str] = set()
    for evento in ledger:
        exec_id = evento.get("fixture_execution_id")
        if evento.get("event") == "DISPATCHED":
            despachadas.add(exec_id)
        elif evento.get("event") == "FINISHED":
            terminales.setdefault(exec_id, []).append(evento)

    for exec_id, fila in filas.items():
        eventos = terminales.get(exec_id, [])
        etiqueta = f"{fila['fixture_id']} · {fila['target']} · rep {fila['repetition']}"
        if not eventos:
            codigo = "EXECUTION_NON_TERMINAL" if exec_id in despachadas else "EXECUTION_MISSING"
            hallazgos.append(Finding(
                code=codigo, severity="error", level="execution",
                message=(
                    f"{etiqueta}: se despachó y no llegó a un estado terminal"
                    if codigo == "EXECUTION_NON_TERMINAL"
                    else f"{etiqueta}: nunca se ejecutó"
                ),
                fixture_execution_id=exec_id,
                repair=f"--id {fila['fixture_id']} --endpoint {fila['target']}",
            ))
        elif len(eventos) > 1:
            # Un reintento declarado comparte identidad; dos terminales sin declararlo
            # significan que la misma ejecución se contó dos veces.
            reintentos = [e for e in eventos if e.get("retry_of")]
            if len(eventos) - len(reintentos) > 1:
                hallazgos.append(Finding(
                    code="EXECUTION_DUPLICATE_TERMINAL", severity="error", level="execution",
                    message=f"{etiqueta}: {len(eventos)} estados terminales sin reintento declarado",
                    fixture_execution_id=exec_id,
                ))

    for exec_id in terminales:
        if exec_id not in filas:
            hallazgos.append(Finding(
                code="EXECUTION_UNEXPECTED", severity="warning", level="execution",
                message=f"el ledger registra {exec_id}, que no está en el plan",
                fixture_execution_id=exec_id,
            ))
    return hallazgos


def check_evidence(plan: dict, ledger: list[dict], archivos: dict[str, list[Path]]) -> list[Finding]:
    hallazgos: list[Finding] = []
    filas = {fila["fixture_execution_id"]: fila for fila in (plan.get("rows") or [])}
    for evento in ledger:
        if evento.get("event") != "FINISHED":
            continue
        exec_id = evento.get("fixture_execution_id")
        fila = filas.get(exec_id)
        if fila is None:
            continue
        etiqueta = f"{fila['fixture_id']} · {fila['target']} · rep {fila['repetition']}"
        if not archivos.get(exec_id):
            hallazgos.append(Finding(
                code="EVIDENCE_MISSING", severity="error", level="evidence",
                message=(
                    f"{etiqueta}: terminó con estado "
                    f"{evento.get('execution_status', '?')} y no dejó Session File"
                ),
                fixture_execution_id=exec_id,
            ))
    return hallazgos


def check_evaluation(archivos: dict[str, list[Path]]) -> list[Finding]:
    hallazgos: list[Finding] = []
    for exec_id, paths in archivos.items():
        for path in paths:
            if EVAL_MARKER not in path.read_text(encoding="utf-8", errors="replace"):
                hallazgos.append(Finding(
                    code="EVALUATION_MISSING", severity="error", level="evaluation",
                    message=f"{path.name} no tiene sección de evaluación legible por máquina",
                    fixture_execution_id=exec_id,
                    artifacts=[path.name],
                    repair="python scripts/evaluate.py --run <run>",
                ))
    return hallazgos


def reconcile(folder: Path, *, level: str = "evaluation") -> dict:
    plan = load_plan(folder)
    ledger = load_ledger(folder)
    hallazgos = check_plan(folder, plan)

    niveles_pedidos = LEVELS[: LEVELS.index(level) + 1]
    archivos = session_files(folder)
    if plan is not None:
        if "execution" in niveles_pedidos:
            hallazgos += check_execution(plan, ledger)
        if "evidence" in niveles_pedidos:
            hallazgos += check_evidence(plan, ledger, archivos)
    if "evaluation" in niveles_pedidos:
        hallazgos += check_evaluation(archivos)

    planificadas = len((plan or {}).get("rows") or [])
    terminales = len({
        evento["fixture_execution_id"] for evento in ledger if evento.get("event") == "FINISHED"
    })
    errores = [h for h in hallazgos if h.severity == "error"]
    peor_nivel = next(
        (nivel for nivel in LEVELS if any(h.level == nivel for h in errores)), None
    )
    return {
        "run": folder.name,
        "level": level,
        "planned": planificadas,
        "terminal": terminales,
        "with_evidence": len(archivos),
        "reconciles": bool(plan) and planificadas == terminales and not errores,
        "findings": [h.to_dict() for h in hallazgos],
        "exit_code": _EXIT_BY_LEVEL[peor_nivel] if peor_nivel else EXIT_OK,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcilia una Suite Run con su plan")
    parser.add_argument("--run", required=True, metavar="RUN_FOLDER")
    parser.add_argument("--level", choices=LEVELS, default="evaluation",
                        help="Nivel de validación (acumulativo). Default: %(default)s")
    parser.add_argument("--json", action="store_true", help="Salida machine-readable")
    parser.add_argument(
        "--exploratory", action="store_true",
        help=(
            "Devuelve 0 aunque haya hallazgos. El run queda marcado como exploratorio: "
            "sirve para diagnosticar, nunca para publicar resultados oficiales."
        ),
    )
    args = parser.parse_args()

    try:
        folder = _run_folder(args.run)
    except ValueError as error:
        parser.error(str(error))
    if not folder.is_dir():
        parser.error(f"Run Folder no encontrado: {folder}")

    informe = reconcile(folder, level=args.level)

    if args.json:
        print(json.dumps(informe, indent=2, ensure_ascii=False))
    else:
        print(f"Run Folder    : {folder.name}")
        print(f"Nivel         : {informe['level']}")
        print(f"Planificadas  : {informe['planned']}")
        print(f"Con terminal  : {informe['terminal']}")
        print(f"Con evidencia : {informe['with_evidence']}")
        errores = [h for h in informe["findings"] if h["severity"] == "error"]
        avisos = [h for h in informe["findings"] if h["severity"] != "error"]
        if errores:
            print(f"\nHALLAZGOS ({len(errores)}):")
            for hallazgo in errores[:50]:
                print(f"  [{hallazgo['code']}] {hallazgo['message']}")
                if hallazgo.get("repair"):
                    print(f"      reparar: {hallazgo['repair']}")
            if len(errores) > 50:
                print(f"  … y {len(errores) - 50} más (usa --json)")
        else:
            print("\nRECONCILIA: cada ejecución planificada tiene un estado terminal único.")
        for aviso in avisos[:20]:
            print(f"  aviso [{aviso['code']}] {aviso['message']}")

    if args.exploratory and informe["exit_code"] != EXIT_OK:
        print("\n⚠ modo exploratorio: hay hallazgos, el run NO puede publicarse como oficial.")
        return EXIT_OK
    return informe["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
