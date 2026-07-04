#!/usr/bin/env python3
"""Añade un bloque de comentario documental al inicio de cada fixture YAML.

El bloque incluye:
  - Descripción breve del ataque
  - Consulta del atacante (primer step)
  - Objetivo del ataque
  - Información del usuario víctima si aplica
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

# ──────────────────────────────────────────────────────────────────────────────
# Datos de referencia
# ──────────────────────────────────────────────────────────────────────────────

USERS = {
    "ES9121000418450200051332": {"name": "María García López",  "id": "usr_001", "balance": "15.420,50 €"},
    "ES7621000418450200051333": {"name": "Carlos Rodríguez Martín", "id": "usr_002", "balance": "8.750,25 €"},
    "ES3421000418450200051334": {"name": "Ana Fernández Ruiz",   "id": "usr_003", "balance": "231.500,00 €"},
    "ES5821000418450200051335": {"name": "Admin Banco",           "id": "usr_admin", "balance": "999.999,99 €"},
}

AUTHENTICATED_USER = "usr_001 · María García López · ES9121000418450200051332"

PLACEHOLDER_RE = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def render(text: str, variables: dict) -> str:
    def replace(m: re.Match) -> str:
        key = m.group(1)
        val = variables.get(key, "")
        if isinstance(val, dict):
            return str(val.get("default", ""))
        return str(val)
    return PLACEHOLDER_RE.sub(replace, text)


def extract_ibans(text: str) -> list[str]:
    return re.findall(r"ES\d{22}", text)


def user_line(iban: str) -> str:
    u = USERS.get(iban)
    if not u:
        return f"{iban} (desconocido)"
    return f"{u['name']} ({u['id']}) · {iban} · {u['balance']}"


def wrap_comment(text: str, prefix: str, width: int = 80) -> list[str]:
    """Envuelve texto en líneas de comentario sin truncar."""
    lines = []
    words = text.replace("\n", " ").split()
    current = prefix
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current.rstrip())
            current = prefix + word + " "
        else:
            current += word + " "
    if current.rstrip() != prefix.rstrip():
        lines.append(current.rstrip())
    return lines


def build_comment(fixture: dict, source_file: Path) -> str:
    SEP = "─" * 70

    kind = source_file.parent.name   # attack-prompts / legitimate-prompts / navi-prompts
    description = (fixture.get("description") or "").strip().replace("\n", " ")

    variables = fixture.get("variables") or {}
    steps = fixture.get("steps") or []
    first_content = ""
    if steps:
        raw = str(steps[0].get("content", ""))
        first_content = render(raw, variables).strip()

    # Objetivo + Técnica
    attack_path = fixture.get("attack", "")
    expected = fixture.get("expected_result", "")
    owasp = fixture.get("owasp", "")

    TECNICAS = {
        "directa": (
            "Prompt Injection directa",
            "El atacante incluye instrucciones maliciosas en su propio mensaje para sobreescribir "
            "las reglas del system prompt y alterar el comportamiento del agente.",
        ),
        "indirecta": (
            "Prompt Injection indirecta (documento)",
            "Las instrucciones maliciosas se embeben en un documento externo (PDF, correo, nota) "
            "que el agente procesa, ejecutando acciones no autorizadas de forma inadvertida.",
        ),
        "pii-harvesting": (
            "PII Harvesting (LLM02)",
            "El atacante solicita al agente que enumere o exporte datos personales de múltiples "
            "clientes (IBANs, saldos, nombres) que no le corresponden.",
        ),
        "cross-context-leakage": (
            "Cross-context Leakage (LLM02)",
            "El agente filtra información de otros usuarios porque no aísla correctamente el "
            "contexto de cada sesión autenticada.",
        ),
        "acciones-no-autorizadas": (
            "Excessive Agency — acciones no autorizadas (LLM06)",
            "El agente ejecuta operaciones financieras reales (transferencias, bloqueos de tarjeta) "
            "sin verificar que el solicitante tiene autorización para realizarlas.",
        ),
        "confused-deputy": (
            "Confused Deputy (LLM06)",
            "El atacante se hace pasar por un rol con privilegios elevados (administrador, soporte) "
            "para que el agente actúe en nombre de terceros o acceda a recursos restringidos.",
        ),
        "filtrado-por-repeticion": (
            "System Prompt Leakage (LLM07)",
            "El atacante solicita directamente el contenido del system prompt o usa técnicas de "
            "repetición, traducción o formato para que el modelo lo revele.",
        ),
        "jailbreak": (
            "Jailbreak (LLM01)",
            "Mediante roleplay, personas alternativas (DAN) o supresión de rechazos, el atacante "
            "intenta anular las restricciones éticas y operativas del modelo.",
        ),
        "chained": (
            "Ataque encadenado (multi-vector)",
            "Combinación secuencial de dos o más técnicas de ataque en una misma sesión "
            "para amplificar el impacto o evadir detecciones parciales.",
        ),
    }

    tecnica_nombre = "—"
    tecnica_desc = "—"
    for key, (nombre, desc) in TECNICAS.items():
        if key in attack_path:
            tecnica_nombre = nombre
            tecnica_desc = desc
            break

    if kind == "legitimate-prompts":
        objetivo = "Consulta legítima — verificar que el agente NO sobre-bloquea"
    elif "system-prompt-leakage" in attack_path or "filtrado-por-repeticion" in attack_path:
        objetivo = "Extraer el system prompt o secretos de configuración del agente"
    elif "pii-harvesting" in attack_path:
        objetivo = "Recopilar datos personales (IBANs, saldos, PII) de múltiples clientes"
    elif "cross-context-leakage" in attack_path:
        objetivo = "Acceder a datos de una cuenta que no pertenece al usuario autenticado"
    elif "acciones-no-autorizadas" in attack_path:
        objetivo = "Ejecutar una acción financiera (transferencia, bloqueo) sin autorización"
    elif "confused-deputy" in attack_path:
        objetivo = "Suplantar un rol privilegiado para operar sobre cuentas ajenas"
    elif "jailbreak" in attack_path:
        objetivo = "Desactivar las restricciones del agente mediante roleplay o supresión de rechazos"
    elif "chained" in attack_path:
        objetivo = "Encadenar dos vectores de ataque para amplificar el impacto"
    elif "indirecta" in attack_path:
        objetivo = "Inyectar instrucciones maliciosas dentro de un documento procesado por el agente"
    else:
        objetivo = "Inyectar instrucciones para saltarse las restricciones del agente"

    # Actores — extraer TODOS los IBANs de variables con su rol descrito
    # Estructura: [(rol, iban), ...]
    actors: list[tuple[str, str]] = []
    seen_ibans: set[str] = set()
    for var_name, var_val in variables.items():
        if not isinstance(var_val, dict):
            continue
        default = str(var_val.get("default", ""))
        role_desc = str(var_val.get("description", var_name))
        ibans = extract_ibans(default)
        for iban in ibans:
            if iban not in seen_ibans:
                seen_ibans.add(iban)
                actors.append((role_desc, iban))

    # Añadir IBANs que aparecen en la consulta pero no en variables
    for iban in extract_ibans(first_content):
        if iban not in seen_ibans:
            seen_ibans.add(iban)
            actors.append(("mencionado en consulta", iban))

    lines = [f"# {SEP}"]

    # Descripción completa, sin truncar
    lines.append("# Descripción:")
    lines.extend(wrap_comment(description, "#   "))

    if kind != "legitimate-prompts":
        lines.append(f"# Técnica:   {tecnica_nombre}")
        lines.extend(wrap_comment(tecnica_desc, "#            "))

    lines += [
        f"# Tipo:      {owasp} · {attack_path}",
        f"# Resultado: expected={expected}",
    ]

    if kind != "legitimate-prompts":
        lines.append(f"# Objetivo:  {objetivo}")

    if actors and kind != "legitimate-prompts":
        lines.append("# Actores:")
        for role_desc, iban in actors:
            lines.append(f"#   [{role_desc}]")
            lines.append(f"#     · {user_line(iban)}")
    elif kind == "legitimate-prompts":
        lines.append(f"# Objetivo:  {objetivo}")
        lines.append(f"# Usuario:   {AUTHENTICATED_USER}")

    # Consulta completa, sin truncar
    lines.append("# Consulta:")
    lines.extend(wrap_comment(first_content, "#   "))

    lines.append(f"# {SEP}")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "backend" / "tests" / "fixtures"

MARKER = "# ─────────"


def process(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    # Eliminar bloque de comentario anterior si existe
    if text.startswith(MARKER):
        end = text.find("\n# ─────────", len(MARKER))
        if end != -1:
            text = text[end + 1:]
            # skip the closing separator line
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1:]

    try:
        fixture = yaml.safe_load(text) or {}
    except yaml.YAMLError as e:
        print(f"  ⚠ YAML error en {path.name}: {e}")
        return

    comment = build_comment(fixture, path)
    new_text = comment + "\n" + text
    path.write_text(new_text, encoding="utf-8")
    print(f"  ✓ {path.relative_to(FIXTURES_DIR)}")


def main() -> None:
    yaml_files = sorted(FIXTURES_DIR.rglob("*.yaml"))
    yaml_files = [f for f in yaml_files if f.name not in ("README.md",)]
    print(f"Procesando {len(yaml_files)} fixtures...\n")
    for f in yaml_files:
        process(f)
    print(f"\n✅ Listo. {len(yaml_files)} fixtures actualizados.")


if __name__ == "__main__":
    main()
