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


def sanitize_document_text(text: str) -> PromptDecision:
    """Aplica TODAS las reglas Capa 1 (regex) al texto extraído de un documento.

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

    return best or PromptDecision(action="ALLOW", confidence=1.0, layer=1)
