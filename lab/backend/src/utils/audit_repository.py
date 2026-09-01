"""Audit Repository — persiste cada turn de chat como Markdown.

Escribe un fichero .md por sesión en lab/audit/sessions/.
Hace append inmediato tras cada turn, sin esperar al fin de la sesión.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from src.models.latency import classify_cohort

from .crypto import sign_payload

_AUDIT_DIR = Path(os.environ.get("AUDIT_DIR", Path(__file__).resolve().parents[3] / "audit" / "sessions"))


def _session_path(session_id: str, timestamp: datetime, directory: Path) -> Path:
    ts = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_id = session_id.replace("/", "-").replace("\\", "-")
    return directory / f"{ts}_{safe_id}.md"


def _find_session_file(session_id: str, directory: Path) -> Path | None:
    """Busca un fichero de sesión existente por session_id dentro de directory."""
    directory.mkdir(parents=True, exist_ok=True)
    safe_id = session_id.replace("/", "-").replace("\\", "-")
    matches = sorted(directory.glob(f"*_{safe_id}.md"))
    return matches[0] if matches else None


def _session_header(
    session_id: str,
    user_id: str,
    model: str,
    timestamp: datetime,
    system_prompt: str | None = None,
) -> str:
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    lines = [
        f"# Sesión `{session_id}`\n",
        f"| Campo | Valor |",
        f"|-------|-------|",
        f"| Iniciada | {ts} |",
        f"| Usuario | `{user_id}` |",
        f"| Modelo | `{model}` |\n",
        f"---\n",
    ]
    if system_prompt:
        lines += [
            f"### System Prompt\n",
            f"```",
            system_prompt.strip(),
            f"```\n",
            f"---\n",
        ]
    return "\n".join(lines) + "\n"


#: Versión del Registro de turno. v3 añade la evidencia estructurada del turno:
#: los Analysis Events tal y como los emitió cada Componente (no reconstruidos),
#: la Postura efectiva, el estado de ejecución y el `tool_call_id` nativo de cada
#: Tool Invocation. Sin ellos el Analyze Pass tenía que inferir del transcript.
TURN_RECORD_SCHEMA_VERSION = 3
TOOL_TRACE_VERSION = 2


def _format_turn(
    turn_number: int,
    timestamp: datetime,
    prompt: str,
    thinking: str | None,
    tools: list[dict],
    response: str,
    raw_response: str | None,
    defense_decisions: list[dict] | None,
    latency_ms: float,
    fixture_id: str | None = None,
    fixture_kind: str | None = None,
    fixture_expected_result: str | None = None,
    posture: dict | None = None,
    execution_status: str = "COMPLETED",
    model_invoked: bool = True,
    fixture_execution_id: str | None = None,
    error: str | None = None,
) -> str:
    ts = timestamp.strftime("%H:%M:%S")
    lines: list[str] = []

    lines.append(f"## Turno {turn_number} — {ts}\n")

    if fixture_id:
        kind_label = fixture_kind or ""
        expected = fixture_expected_result or ""
        lines.append(f"**Fixture**: `{fixture_id}` · {kind_label} · expected: `{expected}`\n")

    lines.append("\n### Prompt\n")
    lines.append(f"```\n{prompt.strip()}\n```\n")

    lines.append("\n### Razonamiento\n")
    if thinking:
        lines.append(f"{thinking.strip()}\n")
    else:
        lines.append("> ℹ️ El modelo no expone tokens de razonamiento (`ThinkingPart` no disponible)\n")

    lines.append("\n### Tools invocadas\n")
    if tools:
        for t in tools:
            tool_name = t.get("tool", "unknown")
            args = t.get("args", "")
            result = t.get("result", "")
            call_id = t.get("tool_call_id") or ""
            lines.append(f"- **`{tool_name}`**")
            if call_id:
                lines.append(f"  - id: `{call_id}`")
            if args:
                lines.append(f"  - args: `{args}`")
            if result:
                lines.append(f"  - resultado: `{result}`")
        lines.append("")
    else:
        lines.append("_Ninguna_\n")

    # Contrato versionado: evita que consumidores automáticos confundan la
    # salida interna del modelo con la respuesta que recibió el cliente, y
    # elimina la necesidad de reconstruir la traza de tools desde el Markdown
    # —correlacionar por nombre y adyacencia asociaba mal dos invocaciones de la
    # misma tool en el mismo turno.
    turn_record = {
        "schema_version": TURN_RECORD_SCHEMA_VERSION,
        "tool_trace_version": TOOL_TRACE_VERSION,
        "client_response": response,
        "model_output_raw": raw_response if raw_response is not None else response,
        "defenses": defense_decisions or [],
        "tools": tools or [],
        "posture": posture or {},
        "execution_status": execution_status,
        "model_invoked": model_invoked,
        "fixture_execution_id": fixture_execution_id,
        "turn_index": turn_number,
        "error": error,
        "latency_ms": round(latency_ms, 1),
        # Cohorte del camino recorrido (P15). Un bloqueo pre-modelo de 4 ms y una
        # respuesta servida de 16 s no pertenecen a la misma distribución.
        "latency_cohort": str(classify_cohort(
            model_invoked=model_invoked,
            execution_status=execution_status,
            output_blocked=any(
                str(d.get("action", "")).upper() in {"BLOCK", "REDACT"}
                and str(d.get("target", "")) == "respuesta"
                for d in (defense_decisions or [])
            ),
            tools_used=len(tools or []),
        )),
    }
    lines.append("\n### Registro de turno\n")
    lines.append("```json\n")
    lines.append(json.dumps(turn_record, ensure_ascii=False, sort_keys=True))
    lines.append("\n```\n")
    lines.append("\n### Respuesta entregada\n")
    lines.append(f"```\n{response.strip()}\n```\n")
    lines.append("\n### Respuesta original protegida\n")
    lines.append(f"```text\n{turn_record['model_output_raw'].strip()}\n```\n")
    lines.append("\n### Decisiones de defensa\n")
    lines.append("```json\n")
    lines.append(json.dumps(turn_record["defenses"], ensure_ascii=False, sort_keys=True))
    lines.append("\n```\n")

    lines.append("\n### Metadatos\n")
    lines.append(f"- Latencia: `{latency_ms:.0f}ms`\n")
    lines.append(f"- Cohorte de latencia: `{turn_record['latency_cohort']}`\n")
    lines.append("\n---\n\n")

    return "\n".join(lines)


def append_turn(
    *,
    session_id: str,
    user_id: str,
    model: str,
    prompt: str,
    thinking: str | None,
    tools: list[dict],
    response: str,
    latency_ms: float,
    raw_response: str | None = None,
    defense_decisions: list[dict] | None = None,
    system_prompt: str | None = None,
    fixture_id: str | None = None,
    fixture_kind: str | None = None,
    fixture_expected_result: str | None = None,
    audit_subdir: str | None = None,
    posture: dict | None = None,
    execution_status: str = "COMPLETED",
    model_invoked: bool = True,
    fixture_execution_id: str | None = None,
    error: str | None = None,
) -> Path:
    """Añade un turn al fichero de sesión. Crea el fichero si no existe.

    Si audit_subdir se provee (ruta absoluta), los ficheros se escriben ahí.
    Si no, se usa AUDIT_DIR (comportamiento anterior para sesiones manuales).

    Un turno que falló también se persiste: `execution_status` distinto de
    `COMPLETED` deja evidencia evaluable en vez de hacer desaparecer la ejecución
    del denominador.
    """
    target_dir = Path(audit_subdir) if audit_subdir else _AUDIT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    existing = _find_session_file(session_id, target_dir)
    if existing is None:
        path = _session_path(session_id, now, target_dir)
        path.write_text(
            _session_header(session_id, user_id, model, now, system_prompt),
            encoding="utf-8",
        )
        turn_number = 1
    else:
        path = existing
        content = path.read_text(encoding="utf-8")
        turn_number = content.count("\n## Turno ") + 1

    turn_md = _format_turn(
        turn_number=turn_number,
        timestamp=now,
        prompt=prompt,
        thinking=thinking,
        tools=tools,
        response=response,
        raw_response=raw_response,
        defense_decisions=defense_decisions,
        latency_ms=latency_ms,
        fixture_id=fixture_id,
        fixture_kind=fixture_kind,
        fixture_expected_result=fixture_expected_result,
        posture=posture,
        execution_status=execution_status,
        model_invoked=model_invoked,
        fixture_execution_id=fixture_execution_id,
        error=error,
    )

    with path.open("a", encoding="utf-8") as f:
        f.write(turn_md)

    return path


def sign_turn(
    path: Path,
    *,
    session_id: str,
    user_id: str,
    prompt: str,
    response: str,
    latency_ms: float,
    timestamp: datetime,
) -> str:
    """Compliance Logger: firma HMAC-SHA256 del turno recién escrito en `path`
    (requisito DORA Art. 12), añadida al Session File. Extiende este repositorio en
    vez de crear un sistema de logging en paralelo — decisión landed en el epic
    "Implementación de proxy base" — reusando `sign_payload` ya escrito en
    `utils/crypto.py`. Solo se llama para turnos servidos por `/chat/proxy`.
    """
    payload = {
        "session_id": session_id,
        "user_id": user_id,
        "prompt": prompt,
        "response": response,
        "latency_ms": round(latency_ms, 1),
        "timestamp": timestamp.isoformat(),
    }
    signature = sign_payload(payload)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"**Firma HMAC-SHA256 (Compliance Logger):** `{signature}`\n\n---\n\n")
    return signature
