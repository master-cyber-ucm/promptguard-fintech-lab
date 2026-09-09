"""Escritura de nuevos fixtures autorizados desde el Playground.

Toma un Fixture Draft (metadatos + steps + bloque de evaluación configurados en
el formulario de autoría) y lo persiste como YAML en el árbol de fixtures. El
bind-mount `./backend/tests:/app/tests` hace que el fichero aparezca directamente
en el repositorio del host.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.utils.fixture_loader import FIXTURES_DIR

_ALLOWED_KINDS = {"attack-prompts", "legitimate-prompts", "navi-prompts"}
_ALLOWED_SEVERITY = {"CRITICAL", "HIGH", "LOW"}
_ALLOWED_EXPECTED = {"BLOCK", "ALLOW", "REFUSE"}
_ALLOWED_EVENT_TYPES = {
    "response_contains", "tool_attempted",
    "tool_denied", "tool_pending_confirmation", "tool_completed_with", "tool_result_matches",
}
_ALLOWED_JUDGE_SYSTEMS = {"neutral", "security"}

# Sólo nombres de segmento seguros: letras, números, guion y guion bajo.
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9_-]+$")
# id canónico: prefijo conocido + número (p.ej. atk_035).
_ID_RE = re.compile(r"^(atk|leg|navi)_[0-9]{3,}$")


class FixtureWriteError(ValueError):
    """Error de validación al crear un fixture (mensaje apto para el cliente)."""


def _resolve_category_dir(category: str) -> str:
    """Mapea el código de categoría (LLM01) al directorio real (LLM01-prompt-injection).

    `_extensiones` es literal. Para el resto se busca el directorio de primer nivel
    cuyo nombre empieza por el código; si no existe todavía (categoría vacía) se exige
    que el código sea uno de los conocidos y se construye la ruta tal cual.
    """
    if category == "_extensiones":
        return "_extensiones"
    if not _SAFE_SEGMENT.match(category):
        raise FixtureWriteError(f"Categoría inválida: {category!r}")
    for child in sorted(FIXTURES_DIR.iterdir()):
        if child.is_dir() and child.name.split("-")[0] == category:
            return child.name
    # Categoría sin carpeta previa: aceptamos el código como nombre de carpeta.
    return category


def _existing_ids() -> set[str]:
    ids: set[str] = set()
    for path in FIXTURES_DIR.rglob("*.yaml"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("id:"):
                ids.add(line.split(":", 1)[1].strip())
                break
    return ids


def _build_evaluation(ev: dict) -> dict:
    method = (ev.get("method") or "deterministic").lower()

    if method == "deterministic":
        events_out: list[dict] = []
        for raw in ev.get("events", []):
            etype = raw.get("type")
            if etype not in _ALLOWED_EVENT_TYPES:
                raise FixtureWriteError(f"Tipo de evento no soportado: {etype!r}")
            if etype == "response_contains":
                value = (raw.get("value") or "").strip()
                if not value:
                    raise FixtureWriteError("response_contains requiere 'value'")
                events_out.append({"type": "response_contains", "value": value})
            elif etype in {"tool_attempted", "tool_denied", "tool_pending_confirmation"}:
                tool = (raw.get("tool") or "").strip()
                if not tool:
                    raise FixtureWriteError(f"{etype} requiere 'tool'")
                entry = {"type": etype, "tool": tool}
                if raw.get("args"):
                    entry["args"] = raw["args"]
                events_out.append(entry)
            else:  # tool_completed_with | tool_result_matches
                tool = (raw.get("tool") or "").strip()
                if not tool:
                    raise FixtureWriteError(f"{etype} requiere 'tool'")
                entry = {"type": etype, "tool": tool}
                if raw.get("args"):
                    entry["args"] = raw["args"]
                if raw.get("result"):
                    entry["result"] = raw["result"]
                if raw.get("statuses"):
                    entry["statuses"] = raw["statuses"]
                events_out.append(entry)
        if not events_out:
            raise FixtureWriteError("La evaluación determinista necesita al menos un evento")
        return {"method": "deterministic", "events": events_out}

    if method in {"hybrid", "hybrid_attack"}:
        question = (ev.get("question") or "").strip()
        if not question:
            raise FixtureWriteError("La evaluación por juez necesita una 'question'")
        system = (ev.get("system") or "neutral").strip().lower()
        if system not in _ALLOWED_JUDGE_SYSTEMS:
            raise FixtureWriteError(f"system del juez inválido: {system!r}")
        return {
            "method": method,
            "fallback": {
                "when": "always" if method == "hybrid" else "no_breach_observed",
                "rubric": question,
                "judge": {"system": system, "include": ["prompt", "response", "tools", "user_context"]},
            },
        }

    raise FixtureWriteError(f"Método de evaluación desconocido: {method!r}")


def build_fixture_dict(draft: dict) -> tuple[dict, Path]:
    """Valida el draft y devuelve (dict del fixture, ruta destino).

    No escribe nada — separar construcción de escritura facilita el test.
    """
    category = (draft.get("category") or "").strip()
    subcategory = (draft.get("subcategory") or "").strip()
    kind = (draft.get("kind") or "").strip()
    fid = (draft.get("id") or "").strip()
    name = (draft.get("name") or "").strip()
    severity = (draft.get("severity") or "HIGH").strip().upper()
    expected = (draft.get("expected_result") or "").strip().upper()
    description = (draft.get("description") or "").strip()
    steps = draft.get("steps") or []
    evaluation = draft.get("evaluation") or {}

    if kind not in _ALLOWED_KINDS:
        raise FixtureWriteError(f"kind inválido: {kind!r}")
    if severity not in _ALLOWED_SEVERITY:
        raise FixtureWriteError(f"severity inválido: {severity!r}")
    if expected not in _ALLOWED_EXPECTED:
        raise FixtureWriteError(f"expected_result inválido: {expected!r}")
    if not _ID_RE.match(fid):
        raise FixtureWriteError(f"id inválido: {fid!r} (esperado p.ej. atk_035)")
    if not _SAFE_SEGMENT.match(name):
        raise FixtureWriteError(f"name inválido: {name!r} (solo [A-Za-z0-9_-])")
    if not _SAFE_SEGMENT.match(subcategory):
        raise FixtureWriteError(f"subcategory inválida: {subcategory!r} (solo [A-Za-z0-9_-])")
    if not steps:
        raise FixtureWriteError("El fixture necesita al menos un step")

    normalized_steps = []
    for idx, step in enumerate(steps, start=1):
        content = str(step.get("content") or "").strip()
        if not content:
            raise FixtureWriteError(f"El step {idx} está vacío")
        normalized_steps.append({"step": idx, "role": "user", "content": content})

    if fid in _existing_ids():
        raise FixtureWriteError(f"El id {fid} ya existe")

    category_dir = _resolve_category_dir(category)
    attack = f"{category_dir}/{subcategory}"
    fixture_type = "single" if len(normalized_steps) == 1 else "multi-step"

    fixture = {
        "id": fid,
        "name": name,
        "attack": attack,
        "category": category,
        "owasp": f"{category}:2025" if category.startswith("LLM") else "",
        "atlas": "",
        "severity": severity,
        "expected_result": expected,
        "description": description or name,
        "variant": {"level": "advanced", "language": "es", "target_model": "any"},
        "evaluation": _build_evaluation(evaluation),
        "variables": {},
        "type": fixture_type,
        "steps": normalized_steps,
    }

    dest = FIXTURES_DIR / category_dir / subcategory / kind / f"{fid}_{name}.yaml"
    # Defensa en profundidad: la ruta resuelta debe quedar dentro del árbol de fixtures.
    if FIXTURES_DIR.resolve() not in dest.resolve().parents:
        raise FixtureWriteError("Ruta destino fuera del árbol de fixtures")

    return fixture, dest


def write_fixture(draft: dict) -> Path:
    fixture, dest = build_fixture_dict(draft)
    if dest.exists():
        raise FixtureWriteError(f"Ya existe un fichero en {dest.name}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        yaml.safe_dump(fixture, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    return dest
