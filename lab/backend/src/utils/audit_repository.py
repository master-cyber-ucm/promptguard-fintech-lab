"""Audit Repository — persiste cada turn de chat como Markdown.

Escribe un fichero .md por sesión en lab/audit/sessions/.
Hace append inmediato tras cada turn, sin esperar al fin de la sesión.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

_AUDIT_DIR = Path(os.environ.get("AUDIT_DIR", Path(__file__).resolve().parents[3] / "audit" / "sessions"))


def _session_path(session_id: str, timestamp: datetime) -> Path:
    ts = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_id = session_id.replace("/", "-").replace("\\", "-")
    return _AUDIT_DIR / f"{ts}_{safe_id}.md"


def _find_session_file(session_id: str) -> Path | None:
    """Busca un fichero de sesión existente por session_id (cualquier timestamp)."""
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = session_id.replace("/", "-").replace("\\", "-")
    matches = sorted(_AUDIT_DIR.glob(f"*_{safe_id}.md"))
    return matches[0] if matches else None


def _session_header(session_id: str, user_id: str, model: str, timestamp: datetime) -> str:
    ts = timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        f"# Sesión `{session_id}`\n\n"
        f"| Campo | Valor |\n"
        f"|-------|-------|\n"
        f"| Iniciada | {ts} |\n"
        f"| Usuario | `{user_id}` |\n"
        f"| Modelo | `{model}` |\n\n"
        f"---\n\n"
    )


def _format_turn(
    turn_number: int,
    timestamp: datetime,
    prompt: str,
    thinking: str | None,
    tools: list[dict],
    response: str,
    latency_ms: float,
    fixture_id: str | None = None,
    fixture_kind: str | None = None,
    fixture_expected_result: str | None = None,
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
            lines.append(f"- **`{tool_name}`**")
            if args:
                lines.append(f"  - args: `{args}`")
            if result:
                lines.append(f"  - resultado: `{result}`")
        lines.append("")
    else:
        lines.append("_Ninguna_\n")

    lines.append("\n### Respuesta\n")
    lines.append(f"```\n{response.strip()}\n```\n")

    lines.append("\n### Metadatos\n")
    lines.append(f"- Latencia: `{latency_ms:.0f}ms`\n")
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
    fixture_id: str | None = None,
    fixture_kind: str | None = None,
    fixture_expected_result: str | None = None,
) -> Path:
    """Añade un turn al fichero de sesión. Crea el fichero si no existe."""
    _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)

    existing = _find_session_file(session_id)
    if existing is None:
        path = _session_path(session_id, now)
        path.write_text(_session_header(session_id, user_id, model, now), encoding="utf-8")
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
        latency_ms=latency_ms,
        fixture_id=fixture_id,
        fixture_kind=fixture_kind,
        fixture_expected_result=fixture_expected_result,
    )

    with path.open("a", encoding="utf-8") as f:
        f.write(turn_md)

    return path
