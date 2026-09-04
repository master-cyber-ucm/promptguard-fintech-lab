"""Dimensiones tipadas de un fixture: población, categoría, familia y procedencia.

P11: las tablas por familia usaban `attack_type` cuando existía y caían a la categoría
OWASP cuando faltaba, de modo que en la misma columna convivían mecanismos de ataque
(`CHAINED_ATTACK`) con buckets genéricos (`LLM06`). El lector no podía saber si estaba
comparando categorías o mecanismos.

Peor: `security_breaches_observed` se derivaba de TODAS las disposiciones. En
`simple-prompt` aparecían 74 brechas cuando solo 69 eran ataques; cinco venían de una
petición legítima mal evaluada.

Cuatro dimensiones independientes, ninguna usada como fallback de otra:

    traffic_kind    ATTACK | LEGITIMATE      población estadística
    owasp_category  LLM01 | LLM02 | …        clasificación externa
    attack_family   familia local cerrada    mecanismo del ataque
    source_suite    CORE | NAVI              procedencia del caso
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class TrafficKind(_Str):
    """Población estadística. Un ataque y una petición legítima no se suman."""

    ATTACK = "ATTACK"
    LEGITIMATE = "LEGITIMATE"


class SourceSuite(_Str):
    """De qué corpus viene el caso. NAVI no es una familia de ataque: es un origen."""

    CORE = "CORE"
    #: Ataques ingenuos/obvios. Miden el suelo, no una técnica distinta.
    NAVI = "NAVI"


class AttackFamily(_Str):
    """Mecanismo del ataque. Catálogo cerrado y versionado."""

    DIRECT_INJECTION = "DIRECT_INJECTION"
    INDIRECT_INJECTION = "INDIRECT_INJECTION"
    CROSS_CONTEXT_LEAKAGE = "CROSS_CONTEXT_LEAKAGE"
    PII_HARVESTING = "PII_HARVESTING"
    EXCESSIVE_AGENCY = "EXCESSIVE_AGENCY"
    CONFUSED_DEPUTY = "CONFUSED_DEPUTY"
    SYSTEM_PROMPT_LEAKAGE = "SYSTEM_PROMPT_LEAKAGE"
    JAILBREAK = "JAILBREAK"
    OBFUSCATION = "OBFUSCATION"
    CHAINED_ATTACK = "CHAINED_ATTACK"
    SOCIAL_ENGINEERING = "SOCIAL_ENGINEERING"
    #: Solo para tráfico legítimo: no tiene mecanismo de ataque.
    NOT_APPLICABLE = "NOT_APPLICABLE"


TAXONOMY_VERSION = 2

#: Subcategoría del árbol de fixtures → familia. Es un mapping DECLARADO, no una
#: derivación de la ruta: mover un directorio no puede reclasificar un ataque.
_FAMILY_BY_ATTACK_PATH: dict[str, AttackFamily] = {
    "LLM01-prompt-injection/directa": AttackFamily.DIRECT_INJECTION,
    "LLM01-prompt-injection/indirecta-documento": AttackFamily.INDIRECT_INJECTION,
    "LLM02-sensitive-information-disclosure/cross-context-leakage": AttackFamily.CROSS_CONTEXT_LEAKAGE,
    "LLM02-sensitive-information-disclosure/pii-harvesting": AttackFamily.PII_HARVESTING,
    "LLM06-excessive-agency/acciones-no-autorizadas": AttackFamily.EXCESSIVE_AGENCY,
    "LLM06-excessive-agency/confused-deputy": AttackFamily.CONFUSED_DEPUTY,
    "LLM07-system-prompt-leakage/filtrado-por-repeticion": AttackFamily.SYSTEM_PROMPT_LEAKAGE,
    "_extensiones/jailbreak": AttackFamily.JAILBREAK,
    "_extensiones/ofuscacion": AttackFamily.OBFUSCATION,
    "_extensiones/chained": AttackFamily.CHAINED_ATTACK,
    "_extensiones/ingenieria-social": AttackFamily.SOCIAL_ENGINEERING,
}

#: Alias históricos de `attack_type`. Se conservan para leer runs antiguos sin
#: reescribirlos: cambiar un mapping no puede alterar un artefacto ya publicado.
_FAMILY_ALIASES: dict[str, AttackFamily] = {
    "PROMPT_INJECTION": AttackFamily.DIRECT_INJECTION,
    "INDIRECT_INJECTION": AttackFamily.INDIRECT_INJECTION,
    "CROSS_CONTEXT_LEAKAGE": AttackFamily.CROSS_CONTEXT_LEAKAGE,
    "PII_HARVESTING": AttackFamily.PII_HARVESTING,
    "EXCESSIVE_AGENCY": AttackFamily.EXCESSIVE_AGENCY,
    "CONFUSED_DEPUTY": AttackFamily.CONFUSED_DEPUTY,
    "SYSTEM_PROMPT_LEAKAGE": AttackFamily.SYSTEM_PROMPT_LEAKAGE,
    "JAILBREAK": AttackFamily.JAILBREAK,
    "OBFUSCATION": AttackFamily.OBFUSCATION,
    "CHAINED_ATTACK": AttackFamily.CHAINED_ATTACK,
    "SOCIAL_ENGINEERING": AttackFamily.SOCIAL_ENGINEERING,
}


class TaxonomyError(ValueError):
    """Un fixture no puede clasificarse sin recurrir a un fallback ambiguo."""


@dataclass(frozen=True)
class FixtureTaxonomy:
    traffic_kind: TrafficKind
    owasp_category: str
    attack_family: AttackFamily
    source_suite: SourceSuite
    severity: str
    schema_version: int = TAXONOMY_VERSION

    def to_dict(self) -> dict:
        return {
            "taxonomy_version": self.schema_version,
            "traffic_kind": str(self.traffic_kind),
            "owasp_category": self.owasp_category,
            "attack_family": str(self.attack_family),
            "source_suite": str(self.source_suite),
            "severity": self.severity,
        }


def classify(fixture: dict, *, strict: bool = False) -> FixtureTaxonomy:
    """Clasifica un fixture en las cuatro dimensiones, sin fallbacks entre ellas.

    `strict=True` exige que un fixture adversarial tenga familia declarada o mapeable.
    Es lo que usa el linter: caer al bucket OWASP silenciosamente fue el origen de la
    tabla que mezclaba categorías con mecanismos.
    """
    kind = str(fixture.get("kind") or "").strip()
    traffic = (
        TrafficKind.LEGITIMATE if kind == "legitimate-prompts" else TrafficKind.ATTACK
    )
    source = SourceSuite.NAVI if kind == "navi-prompts" else SourceSuite.CORE
    owasp = str(fixture.get("category") or "").strip() or "SIN_CATEGORIA"

    if traffic == TrafficKind.LEGITIMATE:
        familia = AttackFamily.NOT_APPLICABLE
    else:
        familia = _resolve_family(fixture)
        if familia is None:
            if strict:
                raise TaxonomyError(
                    f"{fixture.get('id')}: fixture adversarial sin familia declarada "
                    f"ni mapping para attack={fixture.get('attack')!r}"
                )
            # Nunca se cae a la categoría OWASP: eso es lo que mezclaba dimensiones.
            familia = AttackFamily.NOT_APPLICABLE

    return FixtureTaxonomy(
        traffic_kind=traffic,
        owasp_category=owasp,
        attack_family=familia,
        source_suite=source,
        severity=str(fixture.get("severity") or "UNKNOWN").upper(),
    )


def _resolve_family(fixture: dict) -> AttackFamily | None:
    declarada = str(fixture.get("attack_family") or "").upper()
    if declarada in {member.value for member in AttackFamily}:
        return AttackFamily(declarada)
    ruta = str(fixture.get("attack") or "")
    if ruta in _FAMILY_BY_ATTACK_PATH:
        return _FAMILY_BY_ATTACK_PATH[ruta]
    alias = str(fixture.get("attack_type") or "").upper()
    return _FAMILY_ALIASES.get(alias)


def reconcile_populations(taxonomies: list[FixtureTaxonomy]) -> dict:
    """Comprueba que las poblaciones sean disjuntas y sumen el total.

    Ninguna ejecución pertenece a dos clases primarias, y las brechas adversariales no
    pueden exceder el número de ataques evaluados.
    """
    ataques = sum(1 for t in taxonomies if t.traffic_kind == TrafficKind.ATTACK)
    legitimos = sum(1 for t in taxonomies if t.traffic_kind == TrafficKind.LEGITIMATE)
    navi = sum(1 for t in taxonomies if t.source_suite == SourceSuite.NAVI)
    por_familia: dict[str, int] = {}
    for taxonomia in taxonomies:
        if taxonomia.traffic_kind != TrafficKind.ATTACK:
            continue
        clave = str(taxonomia.attack_family)
        por_familia[clave] = por_familia.get(clave, 0) + 1
    return {
        "total": len(taxonomies),
        "attack": ataques,
        "legitimate": legitimos,
        # NAVI es una procedencia, no una tercera población: sus casos ya están
        # contados dentro de `attack`.
        "navi": navi,
        "by_family": por_familia,
        "populations_disjoint": ataques + legitimos == len(taxonomies),
        "families_sum_attacks": sum(por_familia.values()) == ataques,
    }
