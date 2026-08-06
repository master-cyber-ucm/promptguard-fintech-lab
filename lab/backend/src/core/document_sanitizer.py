"""Sanitización del texto extraído de documentos — Fase 2 (Defensa), ataque #7.

Capa BASE de la defensa (ver henri-tfm/02-defensa/README.md para el análisis completo de por qué
es la capa fundamental y no la detección estructural de técnicas de ocultación): analiza el TEXTO
YA EXTRAÍDO, agnóstico a qué técnica se usó para ocultarlo dentro del documento (color de fuente,
atributo `hidden` de Word, fila oculta de Excel, o cualquier técnica futura no catalogada). Si el
contenido extraído contiene lenguaje de instrucción malicioso, esta capa lo detecta
independientemente del vehículo de ocultación.

Reutiliza `config/rules/injection_signatures.yaml` — reglas ya escritas por el equipo para el
Input Sanitizer compartido (Capa 1, regex), nunca antes conectadas a ningún código. Se corrigió
un bug de sintaxis YAML preexistente en esa carga (comilla sin escapar en `refusal_suppression`)
y se añadieron 3 reglas nuevas específicas de este vector (`indirect_doc_*`), validadas contra
los payloads reales de la Fase 1.

Devuelve un `PromptDecision` (mismo modelo que usará el resto del pipeline de seguridad del
proyecto), no un booleano ad-hoc, para que esta capa sea reutilizable por otros vectores.

Detección de ofuscación a nivel de carácter (Fase 2.9.8): el motor de mutación
(`henri-tfm/01-ataque/payloads/tecnicas_ofuscacion.py`) demostró que las reglas de lenguaje de
arriba se evaden por completo insertando caracteres Unicode invisibles o sustituyendo letras por
homoglifos cirílicos dentro de las mismas palabras clave — el texto sigue diciendo lo mismo para
un LLM, pero deja de coincidir con ningún regex de palabra literal. `_detect_invisible_chars` y
`_detect_mixed_script_word` no buscan QUÉ dice el texto (eso ya lo hacen las reglas YAML) sino
CÓMO está construido a nivel de carácter — ningún documento financiero legítimo en español tiene
motivo para contener caracteres de ancho cero ni palabras que mezclen alfabeto latino y cirílico.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from ..models.interaction import PromptDecision

RULES_PATH = Path(__file__).parent.parent.parent / "config" / "rules" / "injection_signatures.yaml"


@lru_cache(maxsize=1)
def _rules() -> list[dict]:
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    return data["rules"]


_SEVERITY_ORDER = {"ALLOW": 0, "SUSPICIOUS": 1, "BLOCK": 2}

# Caracteres de ancho cero — invisibles al renderizar (con una fuente que los soporte), sin
# ningún uso legítimo esperable en un documento financiero en español. Ver hallazgo del motor de
# mutación: con una fuente TrueType real (no la Helvetica estándar) sobreviven intactos al ciclo
# generación→extracción de un PDF.
_INVISIBLE_CHARS = frozenset({
    "​",  # ZERO WIDTH SPACE
    "‌",  # ZERO WIDTH NON-JOINER
    "‍",  # ZERO WIDTH JOINER
    "﻿",  # ZERO WIDTH NO-BREAK SPACE / BOM
})
# Bloque "Unicode Tags" — también invisible, documentado como vector de prompt injection activo
# (ver henri-tfm/02-defensa/README.md §"Análisis de viabilidad de (A)"). No se ha probado en un
# payload real todavía (el motor de mutación cubre zero_width/homoglyph), pero detectarlo no
# cuesta nada adicional y cierra el vector antes de que alguien lo explote.
_INVISIBLE_TAGS_RANGE = (0xE0000, 0xE007F)

_CYRILLIC_RANGE = ("Ѐ", "ӿ")
_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _detect_invisible_chars(text: str) -> str | None:
    for ch in text:
        if ch in _INVISIBLE_CHARS:
            return "unicode_invisible_char"
        cp = ord(ch)
        if _INVISIBLE_TAGS_RANGE[0] <= cp <= _INVISIBLE_TAGS_RANGE[1]:
            return "unicode_tags_block"
    return None


def _detect_mixed_script_word(text: str) -> str | None:
    """Una palabra que mezcla letras latinas y cirílicas es la firma de una sustitución por
    homoglifos (a→а, e→е, o→о...) — un texto legítimo en español no mezcla alfabetos dentro de
    una misma palabra."""
    for word in _WORD_RE.findall(text):
        has_latin = any("a" <= c.lower() <= "z" for c in word)
        has_cyrillic = any(_CYRILLIC_RANGE[0] <= c <= _CYRILLIC_RANGE[1] for c in word)
        if has_latin and has_cyrillic:
            return "homoglyph_mixed_script"
    return None


def sanitize_document_text(text: str) -> PromptDecision:
    """Aplica TODAS las reglas Capa 1 (regex) al texto extraído de un documento, más la
    detección de ofuscación a nivel de carácter (ver docstring del módulo).

    Un documento puede matchear varias reglas a la vez (p. ej. una regla laxa preexistente
    como `account_manipulation` y una más específica y severa de este vector). Se evalúan
    todas y se devuelve la de **acción más estricta** (BLOCK > SUSPICIOUS > ALLOW) — el orden
    de definición en el YAML no debe determinar el resultado.
    """
    best: PromptDecision | None = None
    for rule in _rules():
        if not re.search(rule["pattern"], text):
            continue
        candidate = PromptDecision(
            action=rule["action"],
            confidence=1.0,
            layer=1,
            reason=rule["description"],
            attack_type=rule["name"],
            matched_rule=rule["name"],
        )
        if best is None or _SEVERITY_ORDER[candidate.action] > _SEVERITY_ORDER[best.action]:
            best = candidate

    obfuscation = _detect_invisible_chars(text) or _detect_mixed_script_word(text)
    if obfuscation is not None:
        candidate = PromptDecision(
            action="BLOCK",
            confidence=1.0,
            layer=1,
            reason=(
                "Carácter(es) de ofuscación de texto detectado(s) (Unicode invisible u "
                "homoglifo) — sin uso legítimo esperable en un documento financiero"
            ),
            attack_type="character_obfuscation",
            matched_rule=obfuscation,
        )
        if best is None or _SEVERITY_ORDER[candidate.action] > _SEVERITY_ORDER[best.action]:
            best = candidate

    return best or PromptDecision(action="ALLOW", confidence=1.0, layer=1)
