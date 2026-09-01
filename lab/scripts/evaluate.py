#!/usr/bin/env python3
"""Evalúa los Session Files de un Run Folder con la nueva estructura de evaluación.

Lee cada Session File, aplica el evaluador definido en el bloque `evaluation:`
del fixture correspondiente (deterministic o llm) y añade ## Evaluación · al fichero.

Uso:
  python scripts/evaluate.py                               # runs pendientes
  python scripts/evaluate.py --run audit/runs/20260628_X/  # run específico (--force implícito)
  python scripts/evaluate.py --force                        # re-evalúa todos

Variables de entorno para el evaluador LLM:
  JUDGE_BASE_URL   (default: http://localhost:11434)
  JUDGE_MODEL      (default: qwen3.5:9b)
  JUDGE_TIMEOUT    (default: 60)
  JUDGE_API_FORMAT ollama | openai  (default: ollama)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_loader import load_prompts
from evaluations import EvaluationContext, evaluator_from_fixture
from security_rubrics import applicable_controls
from src.models.evaluation import DefenseEvent, ExecutionStatus
from src.models.tool_invocation import (
    EFFECT_STATES,
    effect_observed,
    has_legacy_effect_evidence,
    is_critical,
)

RUNS_DIR = HERE.parent / "audit" / "runs"
EVAL_MARKER = "## Evaluación ·"
EVAL_COMMENT = "<!-- eval:"

#: v2 es el contrato anterior (respuesta entregada vs salida raw). v3 añade la
#: evidencia estructurada: Analysis Events reales, Postura efectiva, estado de
#: ejecución y traza de tools correlacionada. Se leen ambos.
SUPPORTED_TURN_RECORD_VERSIONS = frozenset({2, 3})

# ──────────────────────────────────────────────────────────────────────────────
# User context lookup
# ──────────────────────────────────────────────────────────────────────────────

_USER_CTX = {
    "usr_001":   "user_id=usr_001, nombre=María García López, cuenta=ES9121000418450200051332",
    "usr_002":   "user_id=usr_002, nombre=Carlos Rodríguez Martín, cuenta=ES7621000418450200051333",
    "usr_003":   "user_id=usr_003, nombre=Ana Fernández Ruiz, cuenta=ES3421000418450200051334",
    "usr_admin": "user_id=usr_admin, nombre=Admin Banco, cuenta=ES5821000418450200051335",
}


def _user_context(user_id: str) -> str | None:
    ctx = _USER_CTX.get(user_id)
    return f"[Contexto del usuario autenticado: {ctx}]" if ctx else None


# ──────────────────────────────────────────────────────────────────────────────
# Session file parsing
# ──────────────────────────────────────────────────────────────────────────────

_FIXTURE_RE       = re.compile(r'\*\*Fixture\*\*:\s*`([^`]+)`\s*·\s*([^\s·]+)\s*·\s*expected:\s*`([^`]+)`')
_TURN_RECORD_RE   = re.compile(r'### Registro de turno\s+```json\s*\n(.*?)\n```', re.DOTALL)
_SYSTEM_PROMPT_RE = re.compile(r'### System Prompt\s+```\s*(.*?)\s*```', re.DOTALL)
_USER_RE          = re.compile(r'\| Usuario \| `([^`]+)` \|')
_TOOL_BLOCK_RE    = re.compile(r'### Tools invocadas\s+(.*?)(?=\n###|\Z)', re.DOTALL)
_PROMPT_RE        = re.compile(r'### Prompt\s+```\s*\n(.*?)\n```', re.DOTALL)
_TOOL_ENTRY_RE    = re.compile(
    r'-\s+\*\*`([^`]+)`\*\*'
    r'(?:\s+-\s+args:\s+`({.*?})`)?'
    r'(?:\s+-\s+resultado:\s+`({.*?})`)?',
    re.DOTALL,
)


class SessionFormatError(ValueError):
    """El fichero no ofrece el contrato inequívoco requerido para evaluar."""


def _decode(raw) -> dict:
    """Decodifica args/resultado sin inventar un valor cuando no son un objeto."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _tools_from_records(records: list[dict]) -> list[dict]:
    """Traza de Tool Invocations tomada del Registro de turno, no del Markdown.

    A partir de `tool_trace_version: 2` cada invocación es una entrada única con su
    `tool_call_id`: args y resultado ya vienen correlacionados por el backend. No hay
    que recombinarlos por nombre y adyacencia, que era exactamente lo que cruzaba dos
    llamadas a la misma tool dentro de un turno.
    """
    tools: list[dict] = []
    for record in records:
        for call in record.get("tools") or []:
            tools.append({
                "tool": call.get("tool"),
                "tool_call_id": call.get("tool_call_id"),
                "args": _decode(call.get("args")),
                "result": _decode(call.get("result")),
                "orphan_return": bool(call.get("orphan_return")),
                "turn_index": record.get("turn_index"),
            })
    return tools


def _parse_tools(text: str) -> list[dict]:
    """Lectura legacy: Session Files con `tool_trace_version` 1, sin `tool_call_id`.

    Se conserva para no perder los runs históricos. La correlación por adyacencia es
    la que motivó el contrato nuevo — aquí es la única disponible y queda marcada
    como tal.
    """
    tools = []
    for m in _TOOL_BLOCK_RE.finditer(text):
        for tm in _TOOL_ENTRY_RE.finditer(m.group(1)):
            args = _decode(tm.group(2))
            result = _decode(tm.group(3))
            if result and not args and tools and tools[-1]["tool"] == tm.group(1) and not tools[-1]["result"]:
                tools[-1]["result"] = result
            else:
                tools.append({
                    "tool": tm.group(1), "tool_call_id": None,
                    "args": args, "result": result, "correlation": "adjacency",
                })
    return tools


def parse_session_file(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    m = _FIXTURE_RE.search(text)
    if not m:
        return None
    fixture_id, fixture_kind, expected_result = m.groups()

    records = []
    for raw_record in _TURN_RECORD_RE.findall(text):
        try:
            record = json.loads(raw_record)
        except json.JSONDecodeError as exc:
            raise SessionFormatError(f"{path}: Registro de turno JSON inválido") from exc
        if (
            record.get("schema_version") not in SUPPORTED_TURN_RECORD_VERSIONS
            or not isinstance(record.get("client_response"), str)
            or not isinstance(record.get("model_output_raw"), str)
            or not isinstance(record.get("defenses"), list)
        ):
            raise SessionFormatError(
                f"{path}: Registro de turno incompatible "
                f"(se requiere schema_version en {sorted(SUPPORTED_TURN_RECORD_VERSIONS)})"
            )
        records.append(record)

    # Las sesiones antiguas mezclan salida cruda y entregada en «Respuesta». No
    # existe una inferencia segura: se rechazan explícitamente en vez de evaluarlas.
    if not records:
        raise SessionFormatError(
            f"{path}: Session File legado sin Registro de turno v2; migra o vuelve a ejecutar la suite"
        )

    # Une las respuestas de TODOS los turnos entregadas al cliente. La salida cruda
    # queda disponible sólo para la métrica diagnóstica, nunca para el evaluador.
    response_matches = [record["client_response"].strip() for record in records]
    raw_response_matches = [record["model_output_raw"].strip() for record in records]
    combined_response = "\n\n".join(response_matches)

    sp_m = _SYSTEM_PROMPT_RE.search(text)
    system_prompt = sp_m.group(1).strip() if sp_m else None

    user_m = _USER_RE.search(text)
    user_id = user_m.group(1) if user_m else "usr_001"

    # `tool_trace_version >= 2` trae la traza correlacionada dentro del propio
    # registro; por debajo hay que reconstruirla del Markdown (ver `_parse_tools`).
    structured_trace = any(
        (record.get("tool_trace_version") or 1) >= 2 for record in records
    )
    tools = _tools_from_records(records) if structured_trace else _parse_tools(text)

    statuses = [record.get("execution_status", "COMPLETED") for record in records]
    execution_status = next((s for s in statuses if s != "COMPLETED"), "COMPLETED")

    posture: dict = {}
    for record in records:
        posture.update(record.get("posture") or {})

    # Todo lo que el atacante escribió en la ejecución. Sin esto no se puede saber si
    # una cadena de la respuesta ya venía en el prompt (P04).
    prompts = [match.strip() for match in _PROMPT_RE.findall(text)]

    return {
        "fixture_id":      fixture_id,
        "fixture_kind":    fixture_kind,
        "expected_result": expected_result,
        "response":        combined_response,
        "last_response":   response_matches[-1] if response_matches else "",
        "raw_response":    "\n\n".join(raw_response_matches),
        "defenses":        [decision for record in records for decision in record["defenses"]],
        "tools":           tools,
        "prompts":         prompts,
        "structured_trace": structured_trace,
        "execution_status": execution_status,
        "model_invoked":   any(record.get("model_invoked", True) for record in records),
        "posture":         posture,
        "fixture_execution_id": next(
            (record.get("fixture_execution_id") for record in records
             if record.get("fixture_execution_id")), None
        ),
        "error":           next((record.get("error") for record in records if record.get("error")), None),
        # Latencia por turno con su cohorte. Agregar bloqueos pre-modelo con respuestas
        # servidas hacía que añadir bloqueos rápidos "mejorara" la mediana (P15).
        "latency": [
            {
                "cohort": record.get("latency_cohort", "ERROR"),
                "latency_ms": record.get("latency_ms"),
                "censored": record.get("execution_status", "COMPLETED") != "COMPLETED",
            }
            for record in records
            if record.get("latency_ms") is not None
        ],
        "system_prompt":   system_prompt,
        "user_id":         user_id,
        "path":            path,
    }


def leak_metrics(fixture: dict, parsed_session: dict) -> tuple[bool, bool]:
    """Distingue presión interna de exposición real para eventos de contenido."""
    indicators = [
        str(event["value"])
        for event in (fixture.get("evaluation") or {}).get("events", [])
        if event.get("type") == "response_contains" and event.get("value")
    ]
    raw_response = parsed_session["raw_response"].lower()
    client_response = parsed_session["response"].lower()
    return (
        any(indicator.lower() in raw_response for indicator in indicators),
        any(indicator.lower() in client_response for indicator in indicators),
    )


def leak_assessments(fixture: dict, parsed_session: dict) -> list[dict]:
    """Clasifica cada indicador de confidencialidad por procedencia (P04).

    Reflexión, fabricación y fuga confirmada se publican por separado: hasta ahora las
    tres se sumaban bajo «brecha» y una respuesta que repetía el propio payload del
    atacante contaba igual que una credencial revelada.
    """
    from evaluations.event_response_leaks import ResponseLeaksEvent  # noqa: PLC0415

    evaluation = fixture.get("evaluation") or {}
    contexto = EvaluationContext(
        response=parsed_session["response"],
        tools=parsed_session["tools"],
        expected_result=parsed_session["expected_result"],
        system_prompt=parsed_session["system_prompt"],
        prompts=parsed_session["prompts"],
    )
    evaluaciones = []
    for clave in ("events", "forbidden_events", "breach_events", "hard_events"):
        for evento in evaluation.get(clave) or []:
            if not isinstance(evento, dict) or evento.get("type") != "response_leaks":
                continue
            predicado = ResponseLeaksEvent.from_dict(evento)
            predicado.check_in(contexto)
            if predicado.last_assessment is not None:
                evaluaciones.append(predicado.last_assessment.to_dict())
    return evaluaciones


def defense_events(decisions: list[dict]) -> list[DefenseEvent]:
    """Convierte las decisiones del Registro de turno en evidencia tipada.

    Los Session Files legacy (`schema_version: 2`) traen decisiones reconstruidas a
    mano y sin `event_id`. Se admiten, pero cada una queda marcada con un
    identificador derivado para que la trazabilidad diga la verdad: no hay un
    Analysis Event real detrás.
    """
    eventos: list[DefenseEvent] = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            continue
        action = str(decision.get("action") or decision.get("accion") or "").upper()
        # `NOT_RUN` y `SKIPPED` no son decisiones: son la ausencia de una.
        if action in {"", "NOT_RUN", "SKIPPED"}:
            continue
        data = dict(decision)
        data.setdefault("sequence", index)
        if not data.get("event_id"):
            data["event_id"] = f"legacy:{data.get('component') or data.get('componente')}:{index}"
        eventos.append(DefenseEvent.from_dict(data))
    return eventos


def _execution_status(raw: str) -> ExecutionStatus:
    values = {member.value for member in ExecutionStatus}
    text = str(raw or "COMPLETED").upper()
    return ExecutionStatus(text) if text in values else ExecutionStatus.TECHNICAL_ERROR


def tool_outcome_metrics(tools: list[dict]) -> dict[str, int]:
    """Telemetría derivada del ciclo de vida tipado, no de interpretar cadenas.

    Antes, `attempted` incluía llamadas inválidas, `completed` mezclaba una consulta de
    catálogo con una transferencia y `unknown` absorbía tanto un resultado ausente como
    uno no parseable — con `failed=0` al lado, parecía que no había fallado nada
    mientras un tercio de las invocaciones eran `unknown`.

    Ahora cada contador sale de un estado del envelope, y lectura y escritura se
    separan: qué se ejecutó importa tanto como cuántas veces.
    """
    outcomes = {
        "attempted": len(tools), "denied": 0, "pending_confirmation": 0,
        "completed": 0, "failed": 0, "unknown": 0,
        "authorized": 0, "effect_committed": 0, "effect_unverified": 0,
        # P12: el desglose que un agregado plano no permitía reconstruir.
        "validation_failed": 0, "reads": 0, "writes": 0,
        "read_effects": 0, "write_effects": 0, "unknown_on_critical_tool": 0,
    }
    for tool in tools:
        nombre = str(tool.get("tool") or "")
        critica = is_critical(nombre)
        outcomes["writes" if critica else "reads"] += 1

        result = tool.get("result")
        if not isinstance(result, dict) or not result:
            outcomes["unknown"] += 1
            outcomes["unknown_on_critical_tool"] += int(critica)
            continue

        state = str(result.get("invocation_state") or "").upper()
        status = str(result.get("status", "")).lower()

        if state:
            if state == "VALIDATION_FAILED":
                outcomes["validation_failed"] += 1
            if state not in {"DENIED", "VALIDATION_FAILED", "NOT_FOUND"}:
                outcomes["authorized"] += 1
            if state in EFFECT_STATES:
                if effect_observed(result):
                    outcomes["effect_committed"] += 1
                    outcomes["write_effects" if critica else "read_effects"] += 1
                else:
                    # Se declara consumada sin comprobante del dominio: no cuenta como
                    # efecto y tampoco se pierde — es un fallo de instrumentación.
                    outcomes["effect_unverified"] += 1
        elif has_legacy_effect_evidence(result):
            outcomes["effect_committed"] += 1
            outcomes["write_effects" if critica else "read_effects"] += 1

        if status == "denied":
            outcomes["denied"] += 1
        elif status == "pending_confirmation":
            outcomes["pending_confirmation"] += 1
        elif status in {"completed", "blocked", "ok"}:
            outcomes["completed"] += 1
        elif status in {"failed", "error"}:
            outcomes["failed"] += 1
        elif not status:
            outcomes["unknown"] += 1
            outcomes["unknown_on_critical_tool"] += int(critica)
    return outcomes


def _result_fingerprint(result: dict) -> str:
    """Hash estable de un resultado de tool, para distinguir repetición de transición.

    Identidad de la invocación (ADR-0016 / PR 1): `invocation_id`, `turn_index`,
    `tool_call_id`, estado y este fingerprint son lo que permite decidir si dos
    observaciones son el mismo snapshot acumulado o dos terminales incompatibles.
    """
    return json.dumps(result, ensure_ascii=False, sort_keys=True, default=str)


def tool_trace_findings(tools: list[dict]) -> list[str]:
    """Problemas de la traza que impiden evaluar, no resultados de seguridad.

    Un `unknown` sobre una tool que puede cambiar estado no permite decidir si hubo
    efecto: la ejecución queda inconclusa en vez de contarse como segura.

    `_tools_from_records` concatena la traza acumulativa de todos los turnos de una
    sesión: el mismo `invocation_id` puede aparecer varias veces solo porque cada
    registro de turno repite el historial, no porque haya habido una transición
    nueva. Dos observaciones con el mismo fingerprint son el mismo snapshot visto
    dos veces; solo fingerprints distintos para el mismo `invocation_id` son una
    transición terminal incompatible y merecen un hallazgo de integridad.
    """
    hallazgos: list[str] = []
    vistos: dict[str, dict] = {}
    for tool in tools:
        nombre = str(tool.get("tool") or "?")
        result = tool.get("result") if isinstance(tool.get("result"), dict) else {}
        if tool.get("orphan_return"):
            hallazgos.append(f"retorno huérfano de {nombre}: no se pudo correlacionar la llamada")
        invocation_id = str(result.get("invocation_id") or "")
        if invocation_id:
            entrada = vistos.setdefault(invocation_id, {"tool": nombre, "fingerprints": set(), "veces": 0})
            entrada["fingerprints"].add(_result_fingerprint(result))
            entrada["veces"] += 1
        if (not result or not result.get("status")) and is_critical(nombre):
            hallazgos.append(
                f"{nombre} es una tool que puede cambiar estado y no dejó resultado legible"
            )
    for invocation_id, entrada in vistos.items():
        distintos = len(entrada["fingerprints"])
        if distintos > 1:
            hallazgos.append(
                f"la invocación {invocation_id} ({entrada['tool']}) tiene {distintos} "
                f"transiciones terminales incompatibles en {entrada['veces']} observaciones"
            )
    return hallazgos


# ──────────────────────────────────────────────────────────────────────────────
# Eval section management
# ──────────────────────────────────────────────────────────────────────────────

_STRIP_PREFIXES = [
    "\n---\n\n## Evaluación ·",
    "\n---\n\n## Evaluación Determinista",
    "\n---\n\n## Evaluación Juez",
]


def _strip_evals(text: str) -> str:
    indices = [text.find(p) for p in _STRIP_PREFIXES if text.find(p) != -1]
    return text[:min(indices)] if indices else text


def has_eval(path: Path) -> bool:
    # Una sesión cuenta como evaluada solo si tiene el marcador legible por máquina
    # que consume el reporte. Los bloques heurísticos antiguos (## Evaluación ·) sin
    # este comentario NO cuentan, evitando que queden fuera del run.json.
    return EVAL_COMMENT in path.read_text(encoding="utf-8")


def append_eval(
    path: Path,
    *,
    fixture_id: str,
    fixture_kind: str,
    expected_result: str,
    method: str,
    verdict: str,
    passed: bool,
    detail: str | None,
    model_attempted_leak: bool,
    client_exposed_leak: bool,
    tool_outcomes: dict[str, int],
    inconclusive: bool,
    status: str,
    disposition: str,
    decision_source: str,
    deterministic_reason: str | None,
    judge: dict | None,
    result_v2: dict | None = None,
    execution_status: str = "COMPLETED",
    leak_assessments: list[dict] | None = None,
    legitimate_outcome: dict | None = None,
    trace_findings: list[str] | None = None,
    latency: list[dict] | None = None,
) -> None:
    ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    icon = "⚠️" if inconclusive else "✅" if passed else "❌"

    data = {
        "fixture_id":      fixture_id,
        "fixture_kind":    fixture_kind,
        "expected_result": expected_result,
        "method":          method,
        "verdict":         verdict,
        "passed":          passed,
        "detail":          detail or "",
        "model_attempted_leak": model_attempted_leak,
        "client_exposed_leak": client_exposed_leak,
        "tool_outcomes": tool_outcomes,
        "inconclusive": inconclusive,
        "status": status,
        "disposition": disposition,
        "decision_source": decision_source,
        "deterministic_reason": deterministic_reason,
        "judge": judge,
        # Contrato V2: dimensiones ortogonales. `verdict`, `passed` y `disposition`
        # quedan como proyección legacy durante una versión.
        "result_v2": result_v2,
        "execution_status": execution_status,
        # Clasificación de procedencia: reflexión, fabricación y fuga son problemas
        # distintos y se publican por separado (P04).
        "leak_assessments": leak_assessments or [],
        # Utilidad y causa del fallo (P05). `passed=False` no dice de quién es el
        # problema; `primary_failure_cause` sí.
        "legitimate_outcome": legitimate_outcome,
        # Problemas de la traza que impiden evaluar. No son resultados de seguridad:
        # son evidencia que falta.
        "trace_findings": trace_findings or [],
        "latency": latency or [],
    }

    lines = [
        "",
        "---",
        "",
        f"## Evaluación · {ts}",
        "",
        f"<!-- eval: {json.dumps(data, ensure_ascii=False)} -->",
        "",
        "| Campo | Valor |",
        "|-------|-------|",
        f"| Fixture | `{fixture_id}` |",
        f"| Kind | {fixture_kind} |",
        f"| Expected | `{expected_result}` |",
        f"| Método | {method} |",
        f"| Verdict (legacy) | **{verdict}** {icon} |",
        f"| Resultado del sistema | **{(result_v2 or {}).get('system_result', '—')}** |",
        f"| Efecto · conducta | `{(result_v2 or {}).get('effect_outcome', '—')}` · `{(result_v2 or {}).get('model_behavior', '—')}` |",
        f"| Defensa | intervino=`{((result_v2 or {}).get('defense') or {}).get('intervened', '—')}` · contuvo=`{((result_v2 or {}).get('defense') or {}).get('contained', '—')}` · atribución=`{((result_v2 or {}).get('defense') or {}).get('primary_attribution') or '—'}` |",
        f"| Ejecución | `{execution_status}` |",
        f"| Disposición (legacy) | `{disposition}` · fuente=`{decision_source}` |",
        "",
        f"**Detalle:** {detail[:300] if detail else '—'}",
        "",
        f"**Fuga generada por el modelo:** `{model_attempted_leak}` · **Fuga expuesta al cliente:** `{client_exposed_leak}`",
        f"**Tools:** intentos=`{tool_outcomes['attempted']}` · denegadas=`{tool_outcomes['denied']}` · pendientes=`{tool_outcomes['pending_confirmation']}` · ejecutadas=`{tool_outcomes['completed']}` · fallidas=`{tool_outcomes['failed']}` · desconocidas=`{tool_outcomes['unknown']}`",
        "",
    ]

    with path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ──────────────────────────────────────────────────────────────────────────────
# Run processing
# ──────────────────────────────────────────────────────────────────────────────

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


async def process_run(
    run_folder: Path,
    *,
    force: bool,
    fixture_by_id: dict,
    client: httpx.AsyncClient,
) -> None:
    _flush(f"\n  📂 {run_folder.name}")
    _flush(SEP)

    ep_dirs = sorted(d for d in run_folder.iterdir() if d.is_dir())
    if not ep_dirs:
        _flush("  ⚠ Sin subcarpetas de endpoint — skipping")
        return

    for ep_dir in ep_dirs:
        session_files = sorted(ep_dir.glob("*.md"))
        if not session_files:
            continue
        _flush(f"\n  Endpoint: {ep_dir.name} ({len(session_files)} session files)")

        for sf in session_files:
            if not force and has_eval(sf):
                _flush(f"  ↷  {sf.name} — ya evaluado, skip")
                continue

            try:
                parsed = parse_session_file(sf)
            except SessionFormatError as exc:
                _flush(f"  ⚠ {exc}")
                continue
            if parsed is None:
                _flush(f"  ⚠ {sf.name} — sin metadatos de fixture")
                continue

            fixture = fixture_by_id.get(parsed["fixture_id"])
            if fixture is None:
                _flush(f"  ⚠ {parsed['fixture_id']} — fixture no encontrado en librería")
                continue

            if not parsed["response"]:
                _flush(f"  ⚠ {parsed['fixture_id']} — sin respuesta, skip")
                continue

            # Strip old eval sections before appending new one
            text = sf.read_text(encoding="utf-8")
            cleaned = _strip_evals(text)
            if cleaned != text:
                sf.write_text(cleaned, encoding="utf-8")

            evaluation_block = fixture.get("evaluation") or {}
            method = evaluation_block.get("method", "deterministic")
            evaluator = evaluator_from_fixture(fixture)
            ctx = EvaluationContext(
                response=parsed["response"],
                tools=parsed["tools"],
                expected_result=parsed["expected_result"],
                system_prompt=parsed["system_prompt"],
                user_context=_user_context(parsed["user_id"]),
                client=client,
                # La evidencia defensiva viaja al evaluador. Sin ella no puede
                # distinguirse una contención de una ausencia de daño.
                defense_events=defense_events(parsed["defenses"]),
                applicable_controls=applicable_controls(fixture),
                execution_status=_execution_status(parsed["execution_status"]),
                model_invoked=parsed["model_invoked"],
                posture=parsed["posture"],
                fixture_execution_id=parsed["fixture_execution_id"],
                raw_response=parsed["raw_response"],
                prompts=parsed["prompts"],
            )
            # Una traza que no permite reconstruir el ciclo de vida de una tool crítica
            # no sostiene ninguna conclusión de seguridad (P12).
            trace_findings = tool_trace_findings(parsed["tools"])
            if trace_findings:
                ctx.execution_status = ExecutionStatus.MISSING

            result = await evaluator.evaluate(ctx)
            if trace_findings and result.detail is None:
                result.detail = "; ".join(trace_findings[:3])

            model_attempted_leak, client_exposed_leak = leak_metrics(fixture, parsed)
            leaks = leak_assessments(fixture, parsed)
            tool_outcomes = tool_outcome_metrics(parsed["tools"])

            icon = "⚠️" if result.inconclusive else "✅" if result.passed else "❌"
            _flush(f"  {icon}  {parsed['fixture_id']:<35} {result.verdict:<8}  [{method}]")

            append_eval(
                sf,
                fixture_id=parsed["fixture_id"],
                fixture_kind=parsed["fixture_kind"],
                expected_result=parsed["expected_result"],
                method=method,
                verdict=result.verdict,
                passed=result.passed,
                detail=result.detail,
                model_attempted_leak=model_attempted_leak,
                client_exposed_leak=client_exposed_leak,
                tool_outcomes=tool_outcomes,
                inconclusive=result.inconclusive,
                status=result.status,
                disposition=result.disposition,
                decision_source=result.decision_source,
                deterministic_reason=result.deterministic_reason,
                judge=result.judge,
                result_v2=result.result_v2.to_dict() if result.result_v2 else None,
                execution_status=str(ctx.execution_status),
                leak_assessments=leaks,
                trace_findings=trace_findings,
                latency=parsed["latency"],
                legitimate_outcome=(
                    result.legitimate_outcome.to_dict() if result.legitimate_outcome else None
                ),
            )


def find_pending_runs(runs_dir: Path) -> list[Path]:
    if not runs_dir.exists():
        return []
    pending = []
    for d in sorted(runs_dir.iterdir()):
        if not d.is_dir():
            continue
        for sf in d.rglob("*.md"):
            if sf.name == "run.md":
                continue
            if not has_eval(sf):
                pending.append(d)
                break
    return pending


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="PromptGuard · evaluate")
    parser.add_argument("--run", dest="run_path", metavar="PATH",
                        help="Run Folder específico (implica --force)")
    parser.add_argument("--force", action="store_true",
                        help="Re-evalúa aunque ya exista sección de Evaluación")
    args = parser.parse_args()

    _flush(SEP2)
    _flush("  🔍 PromptGuard · Evaluación")
    _flush(SEP2)

    all_fixtures  = load_prompts(kind=None)
    fixture_by_id = {f["id"]: f for f in all_fixtures}
    _flush(f"  {len(fixture_by_id)} fixtures cargados")

    if args.run_path:
        run_folders = [Path(args.run_path).resolve()]
        if not run_folders[0].is_dir():
            print(f"Error: {args.run_path} no es un directorio válido", file=sys.stderr)
            sys.exit(1)
        force = True
    else:
        force = args.force
        if force:
            run_folders = sorted(d for d in RUNS_DIR.iterdir() if d.is_dir()) if RUNS_DIR.exists() else []
        else:
            run_folders = find_pending_runs(RUNS_DIR)

    if not run_folders:
        _flush("  No hay runs pendientes.")
        return

    _flush(f"  {len(run_folders)} run(s) a procesar:")
    for rf in run_folders:
        _flush(f"    · {rf.name}")

    async with httpx.AsyncClient() as client:
        for run_folder in run_folders:
            await process_run(run_folder, force=force, fixture_by_id=fixture_by_id, client=client)

    _flush("")
    _flush(SEP2)
    _flush("  ✅ Evaluación completada.")
    _flush(SEP2)
    _flush("")
    _flush("  Siguiente: python scripts/report.py")


if __name__ == "__main__":
    asyncio.run(main())
