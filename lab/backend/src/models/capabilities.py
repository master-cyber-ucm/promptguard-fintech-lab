"""Aplicabilidad por capacidades, no por nombre de ruta.

P10: el manifiesto declaraba 111 fixtures cargados, pero el routing de los cinco
targets no aceptaba la modalidad documental. Once fixtures —seis ataques de inyección
indirecta y cinco legítimos sobre documentos benignos— no produjeron ni una petición,
ni una sesión, ni un error. El run terminó «completo» y cualquier conclusión sobre
inyección indirecta ignoraba justo esos casos.

Un fixture declara qué **necesita**; un target declara qué **soporta**. La aplicabilidad
es la intersección, así que renombrar una ruta no cambia nada y retirar una capacidad
sí. «No se ejecutó» nunca es una exclusión: es un agujero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class _Str(str, Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class Modality(_Str):
    """Canal por el que entra el caso de prueba."""

    CHAT = "chat"
    DOCUMENT = "document"


class Capability(_Str):
    """Capacidad efectiva de un target."""

    CHAT = "chat"
    DOCUMENT_UPLOAD = "document_upload"
    TOOLS_READ = "tools_read"
    TOOLS_WRITE = "tools_write"
    CONTEXT_INJECTION = "context_injection"
    MULTI_TURN = "multi_turn"
    PROXY_PIPELINE = "proxy_pipeline"


class Applicability(_Str):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EXCLUDED = "EXCLUDED"


class ReasonCode(_Str):
    """Vocabulario cerrado. Sin él, «no se ejecutó» se disfraza de decisión."""

    UNSUPPORTED_MODALITY = "unsupported_modality"
    CAPABILITY_ABSENT = "capability_absent"
    OUT_OF_SCOPE_VERSIONED = "out_of_scope_versioned"


@dataclass(frozen=True)
class FixtureCapabilities:
    modality: Modality = Modality.CHAT
    required: tuple[Capability, ...] = ()
    forbidden: tuple[Capability, ...] = ()

    @classmethod
    def of(cls, fixture: dict) -> "FixtureCapabilities":
        """Deriva las capacidades que un fixture necesita de su propia declaración.

        Se admite la forma explícita (`capabilities:` en el YAML) y, para los fixtures
        que aún no la declaran, una derivación conservadora de su forma: un fixture con
        `document:` necesita subida de documentos; uno multi-step, memoria entre turnos.
        """
        declarado = fixture.get("capabilities") or {}
        modality = Modality(
            str(declarado.get("modality", "document" if fixture.get("document") else "chat"))
        )
        required = set(_capabilities(declarado.get("required") or []))
        if modality == Modality.DOCUMENT:
            required.add(Capability.DOCUMENT_UPLOAD)
        else:
            required.add(Capability.CHAT)
        if len(fixture.get("steps") or fixture.get("rendered_steps") or []) > 1:
            required.add(Capability.MULTI_TURN)
        return cls(
            modality=modality,
            required=tuple(sorted(required, key=str)),
            forbidden=tuple(_capabilities(declarado.get("forbidden") or [])),
        )


def _capabilities(valores) -> list[Capability]:
    validos = {member.value for member in Capability}
    return [Capability(v) for v in valores if v in validos]


@dataclass(frozen=True)
class TargetCapabilities:
    name: str
    supported: tuple[Capability, ...] = ()
    #: Modalidades que este target ATIENDE. Un canal documental no atiende chat suelto
    #: aunque técnicamente sepa hablar: la comparación sería entre canales distintos.
    modalities: tuple[Modality, ...] = (Modality.CHAT,)
    effective_catalog_hash: str | None = None

    def supports(self, capability: Capability) -> bool:
        return capability in self.supported

    def serves(self, modality: Modality) -> bool:
        return modality in self.modalities


#: Capacidades efectivas de cada target del lab. Es lo que el planner interseca.
TARGET_CAPABILITIES: dict[str, TargetCapabilities] = {
    "simple-prompt": TargetCapabilities("simple-prompt", (
        Capability.CHAT, Capability.TOOLS_READ, Capability.TOOLS_WRITE, Capability.MULTI_TURN,
    )),
    "complex-prompt": TargetCapabilities("complex-prompt", (
        Capability.CHAT, Capability.TOOLS_READ, Capability.TOOLS_WRITE, Capability.MULTI_TURN,
    )),
    "complex-with-context": TargetCapabilities("complex-with-context", (
        Capability.CHAT, Capability.TOOLS_READ, Capability.TOOLS_WRITE,
        Capability.CONTEXT_INJECTION, Capability.MULTI_TURN,
    )),
    "complex-with-document": TargetCapabilities("complex-with-document", (
        Capability.CHAT, Capability.DOCUMENT_UPLOAD, Capability.TOOLS_READ,
        Capability.TOOLS_WRITE, Capability.CONTEXT_INJECTION, Capability.MULTI_TURN,
    ), modalities=(Modality.DOCUMENT,)),
    "proxy": TargetCapabilities("proxy", (
        Capability.CHAT, Capability.TOOLS_READ, Capability.TOOLS_WRITE,
        Capability.CONTEXT_INJECTION, Capability.MULTI_TURN, Capability.PROXY_PIPELINE,
    )),
}


def capabilities_of_target(target: str) -> TargetCapabilities:
    """Capacidades de un target, incluidos los perfiles del proxy (`proxy-full`…)."""
    if target in TARGET_CAPABILITIES:
        return TARGET_CAPABILITIES[target]
    if target.startswith("proxy-document"):
        base = TARGET_CAPABILITIES["proxy"]
        return TargetCapabilities(
            target, (*base.supported, Capability.DOCUMENT_UPLOAD),
            modalities=(Modality.DOCUMENT,),
        )
    if target.startswith("proxy-"):
        return TargetCapabilities(target, TARGET_CAPABILITIES["proxy"].supported)
    return TargetCapabilities(target, ())


@dataclass
class ApplicabilityDecision:
    target: str
    applicability: Applicability
    reason_code: ReasonCode | None = None
    detail: str | None = None
    #: Solo para EXCLUDED: quién lo decidió y hasta cuándo.
    owner: str | None = None
    expires: str | None = None
    issue: str | None = None

    @property
    def in_population(self) -> bool:
        """Solo lo aplicable entra en el denominador del Plan de cobertura."""
        return self.applicability == Applicability.APPLICABLE

    def to_dict(self) -> dict:
        return {
            "target": self.target,
            "applicability": str(self.applicability),
            "reason_code": str(self.reason_code) if self.reason_code else None,
            "detail": self.detail,
            "owner": self.owner,
            "expires": self.expires,
            "issue": self.issue,
        }


def decide(fixture: dict, target: str) -> ApplicabilityDecision:
    """Decide la aplicabilidad de un fixture en un target por capacidades.

    Una exclusión declarada en el fixture (`excluded_from:`) exige código de razón,
    responsable y, si es temporal, issue: sin eso no es una decisión, es un olvido.
    """
    exclusion = (fixture.get("excluded_from") or {}).get(target)
    if exclusion:
        return ApplicabilityDecision(
            target=target,
            applicability=Applicability.EXCLUDED,
            reason_code=ReasonCode.OUT_OF_SCOPE_VERSIONED,
            detail=exclusion.get("reason"),
            owner=exclusion.get("owner"),
            expires=exclusion.get("expires"),
            issue=exclusion.get("issue"),
        )

    necesita = FixtureCapabilities.of(fixture)
    tiene = capabilities_of_target(target)

    if not tiene.serves(necesita.modality):
        return ApplicabilityDecision(
            target, Applicability.NOT_APPLICABLE, ReasonCode.UNSUPPORTED_MODALITY,
            detail=f"{target} no atiende la modalidad {necesita.modality}",
        )
    faltan = [cap for cap in necesita.required if not tiene.supports(cap)]
    if faltan:
        return ApplicabilityDecision(
            target, Applicability.NOT_APPLICABLE, ReasonCode.CAPABILITY_ABSENT,
            detail=f"faltan capacidades: {', '.join(str(c) for c in faltan)}",
        )
    prohibidas = [cap for cap in necesita.forbidden if tiene.supports(cap)]
    if prohibidas:
        return ApplicabilityDecision(
            target, Applicability.NOT_APPLICABLE, ReasonCode.CAPABILITY_ABSENT,
            detail=f"capacidades incompatibles presentes: {', '.join(str(c) for c in prohibidas)}",
        )
    return ApplicabilityDecision(target, Applicability.APPLICABLE)


@dataclass
class CoverageAudit:
    """Fixtures sin ningún target aplicable en la matriz de un run."""

    orphans: list[str] = field(default_factory=list)
    by_fixture: dict[str, list[dict]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"orphans": self.orphans, "by_fixture": self.by_fixture}


def audit_coverage(fixtures: list[dict], targets: list[str]) -> CoverageAudit:
    """Detecta cobertura cero: un fixture cargado que ningún target puede ejecutar.

    Es exactamente lo que ocurrió con los once fixtures documentales: `fixture_count`
    los contaba y la matriz no los alcanzaba, así que ni siquiera generaban un hueco
    que reclamar.
    """
    auditoria = CoverageAudit()
    for fixture in fixtures:
        decisiones = [decide(fixture, target) for target in targets]
        auditoria.by_fixture[fixture["id"]] = [d.to_dict() for d in decisiones]
        if not any(d.in_population for d in decisiones):
            auditoria.orphans.append(fixture["id"])
    auditoria.orphans.sort()
    return auditoria
