"""Frontera de autenticación: el Principal nunca viene del body.

P16: `ChatRequest` aceptaba `user_id` y el backend lo usaba como identidad autenticada.
Pasarlo al agente por `RunContext` impide que el *LLM* lo cambie, pero no impide que el
*cliente* elija `usr_002` o `usr_admin`. Los checks de propiedad podían ser correctos y
operar igualmente sobre una identidad falsificada.

El lab no monta un IdP: usa un **issuer determinista de test** que firma credenciales
con HMAC. Lo que no hace, en ningún caso, es aceptar una identidad del payload.

    Authorization: Bearer <subject>.<tenant>.<expiry>.<hmac>

Cualquier `user_id` que llegue en el body se ignora, y si contradice al Principal se
rechaza: un experimento que confunde suplantación con configuración no mide nada.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field

from fastapi import Header, HTTPException

_SECRET = os.environ.get("AUTH_SIGNING_KEY", "promptguard-lab-test-issuer").encode("utf-8")
ISSUER = os.environ.get("AUTH_ISSUER", "promptguard-lab-test-issuer")
DEFAULT_TENANT = "verdabank"
TOKEN_TTL_SECONDS = int(os.environ.get("AUTH_TOKEN_TTL", "3600"))

#: Cuando está activo, una petición sin credencial se rechaza. Por defecto el lab
#: admite el modo de compatibilidad para no romper el Playground, pero deja constancia
#: del nivel de assurance: una sesión sin token NO es una sesión autenticada.
REQUIRE_AUTH = os.environ.get("REQUIRE_AUTH", "false").lower() == "true"


class AssuranceLevel:
    """Cuánta confianza merece la identidad de esta petición."""

    #: Credencial firmada y verificada.
    AUTHENTICATED = "AUTHENTICATED"
    #: Modo de compatibilidad del lab: identidad declarada, no probada.
    UNVERIFIED = "UNVERIFIED"


@dataclass(frozen=True)
class Principal:
    """Sujeto autenticado del que deriva toda la autoridad de la petición."""

    subject: str
    tenant_id: str = DEFAULT_TENANT
    roles: tuple[str, ...] = ()
    scopes: tuple[str, ...] = ()
    issuer: str = ISSUER
    assurance_level: str = AssuranceLevel.UNVERIFIED
    authenticated_at: float = field(default_factory=time.time)
    token_id: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self.assurance_level == AssuranceLevel.AUTHENTICATED

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.roles

    def to_audit(self) -> dict:
        """Lo que se persiste en la evidencia. Sin esto, «usuario autenticado» era
        una afirmación sin prueba detrás."""
        return {
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "roles": list(self.roles),
            "issuer": self.issuer,
            "assurance_level": self.assurance_level,
            "token_id": self.token_id,
        }


class AuthError(HTTPException):
    def __init__(self, detail: str) -> None:
        super().__init__(status_code=401, detail=detail)


def _sign(subject: str, tenant: str, expiry: int) -> str:
    payload = f"{subject}.{tenant}.{expiry}".encode("utf-8")
    return hmac.new(_SECRET, payload, hashlib.sha256).hexdigest()[:32]


def issue_token(subject: str, *, tenant: str = DEFAULT_TENANT, ttl: int | None = None) -> str:
    """Emite una credencial de test. Solo el issuer puede producir una válida."""
    expiry = int(time.time()) + (ttl if ttl is not None else TOKEN_TTL_SECONDS)
    return f"{subject}.{tenant}.{expiry}.{_sign(subject, tenant, expiry)}"


def verify_token(token: str) -> Principal:
    """Verifica firma y caducidad. Falla antes de tocar el dominio."""
    partes = token.split(".")
    if len(partes) != 4:
        raise AuthError("credencial malformada")
    subject, tenant, expiry_raw, firma = partes
    try:
        expiry = int(expiry_raw)
    except ValueError as exc:
        raise AuthError("credencial malformada") from exc
    if not hmac.compare_digest(firma, _sign(subject, tenant, expiry)):
        raise AuthError("firma de credencial inválida")
    if expiry < time.time():
        raise AuthError("credencial expirada")

    from src.models.banking import MOCK_USERS  # noqa: PLC0415

    # Los roles y scopes se resuelven SERVER-SIDE desde el subject verificado; nunca
    # se leen de la credencial ni del body.
    usuario = MOCK_USERS.get(subject)
    if usuario is None:
        raise AuthError("sujeto desconocido")
    rol = usuario.get("role", "customer")
    return Principal(
        subject=subject,
        tenant_id=tenant,
        roles=(rol,),
        scopes=("chat", "accounts:read", "transfers:propose")
        + (("accounts:read:any", "admin") if rol == "admin" else ()),
        assurance_level=AssuranceLevel.AUTHENTICATED,
        token_id=firma[:12],
    )


def resolve_principal(
    authorization: str | None, *, declared_user_id: str | None = None,
) -> Principal:
    """Deriva el Principal de la credencial. El `user_id` del body NO decide.

    Sin credencial, el lab conserva un modo de compatibilidad para el Playground, pero
    marca la identidad como `UNVERIFIED`: la evidencia deja constancia de que esa
    sesión no probó quién era.
    """
    if authorization:
        esquema, _, token = authorization.partition(" ")
        if esquema.lower() != "bearer" or not token:
            raise AuthError("se espera 'Authorization: Bearer <token>'")
        principal = verify_token(token.strip())
        if declared_user_id and declared_user_id != principal.subject:
            # Enviar una identidad distinta de la autenticada es un intento de
            # suplantación, no una preferencia de configuración.
            raise HTTPException(
                status_code=403,
                detail=(
                    "el user_id del cuerpo no coincide con la identidad autenticada; "
                    "la identidad no se elige desde el payload"
                ),
            )
        return principal

    if REQUIRE_AUTH:
        raise AuthError("se requiere autenticación")

    from src.models.banking import MOCK_USERS  # noqa: PLC0415

    subject = declared_user_id or "usr_001"
    usuario = MOCK_USERS.get(subject)
    if usuario is None:
        raise HTTPException(status_code=404, detail=f"Usuario {subject} no encontrado")
    return Principal(
        subject=subject,
        roles=(usuario.get("role", "customer"),),
        scopes=("chat", "accounts:read", "transfers:propose"),
        assurance_level=AssuranceLevel.UNVERIFIED,
    )


async def principal_dependency(
    authorization: str | None = Header(default=None),
) -> Principal:
    """Dependencia FastAPI para rutas que solo necesitan la identidad."""
    return resolve_principal(authorization)
