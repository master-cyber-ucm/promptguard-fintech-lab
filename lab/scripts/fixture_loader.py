"""Helpers for loading PromptGuard test fixtures."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable

import yaml


HERE = Path(__file__).resolve().parent
FIXTURES_DIR = Path(
    os.environ.get("FIXTURES_DIR", str(HERE.parent / "backend" / "tests" / "fixtures"))
)

ATTACK_TYPE_BY_ATTACK = {
    "LLM01-prompt-injection/directa": "DIRECT_INJECTION",
    "LLM01-prompt-injection/indirecta-documento": "INDIRECT_INJECTION",
    "LLM02-sensitive-information-disclosure/cross-context-leakage": "CROSS_CONTEXT_LEAKAGE",
    "LLM02-sensitive-information-disclosure/pii-harvesting": "PII_HARVESTING",
    "LLM06-excessive-agency/acciones-no-autorizadas": "EXCESSIVE_AGENCY",
    "LLM06-excessive-agency/confused-deputy": "CONFUSED_DEPUTY",
    "LLM07-system-prompt-leakage/filtrado-por-repeticion": "SYSTEM_LEAK",
    "_extensiones/jailbreak": "JAILBREAK",
    "_extensiones/chained": "CHAINED_ATTACK",
}

PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def _load_yaml(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def _render_text(text: str, variables: dict[str, object]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = variables.get(key, "")
        if isinstance(value, dict):
            if "default" in value:
                return str(value["default"])
            return str(value)
        return str(value)

    return PLACEHOLDER_RE.sub(replace, text)


def _render_value(value, variables: dict[str, object]):
    if isinstance(value, str):
        return _render_text(value, variables)
    if isinstance(value, list):
        return [_render_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {key: _render_value(item, variables) for key, item in value.items()}
    return value


def normalize_prompt(data: dict, source_file: Path | None = None) -> dict:
    prompt = dict(data)

    if "steps" not in prompt and "payload" in prompt:
        prompt["type"] = prompt.get("type", "single")
        prompt["steps"] = [
            {
                "step": 1,
                "role": "user",
                "content": prompt["payload"],
            }
        ]

    variables = prompt.get("variables", {})
    rendered_steps = []
    for step in prompt.get("steps", []):
        rendered_step = dict(step)
        rendered_step["content"] = _render_value(rendered_step.get("content", ""), variables)
        rendered_steps.append(rendered_step)

    prompt["rendered_steps"] = rendered_steps
    prompt["kind"] = source_file.parent.name if source_file else None
    prompt["source_file"] = str(source_file) if source_file else None
    attack = prompt.get("attack", "")
    prompt["attack_type"] = prompt.get("attack_type") or ATTACK_TYPE_BY_ATTACK.get(attack, "")
    return prompt


def iter_prompt_files(root: Path = FIXTURES_DIR, kind: str | None = None) -> Iterable[Path]:
    for path in root.rglob("*.yaml"):
        if path.name == "README.md":
            continue
        if kind and kind not in path.parts:
            continue
        yield path


def load_prompts(
    *,
    root: Path = FIXTURES_DIR,
    kind: str | None = "attack-prompts",
    attack_type: str | None = None,
    prompt_id: str | None = None,
) -> list[dict]:
    prompts: list[dict] = []
    seen_ids: set[str] = set()

    yaml_files = sorted(iter_prompt_files(root=root, kind=kind))
    for path in yaml_files:
        prompt = normalize_prompt(_load_yaml(path), source_file=path)
        if prompt_id and prompt.get("id") != prompt_id:
            continue
        if attack_type and prompt.get("attack_type") != attack_type.upper():
            continue
        prompt_key = str(prompt.get("id", ""))
        if prompt_key in seen_ids:
            continue
        seen_ids.add(prompt_key)
        prompts.append(prompt)

    return prompts


def first_user_message(prompt: dict) -> str:
    steps = prompt.get("rendered_steps") or prompt.get("steps") or []
    if not steps:
        return ""
    first = steps[0]
    return str(first.get("content", ""))


def conversation_message(prompt: dict, upto_step: int | None = None) -> str:
    steps = prompt.get("rendered_steps") or prompt.get("steps") or []
    if upto_step is not None:
        steps = steps[:upto_step]
    transcript: list[str] = []
    for step in steps:
        role = step.get("role", "user")
        content = str(step.get("content", ""))
        if role == "assistant":
            transcript.append(f"Asistente: {content}")
        else:
            transcript.append(f"Usuario: {content}")
    return "\n".join(transcript)
