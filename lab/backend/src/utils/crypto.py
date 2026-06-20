"""Utilidades criptográficas para firma de logs de auditoría.

Implementa firma HMAC-SHA256 para garantizar la integridad
de los registros del Compliance Logger (requisito DORA Art. 12).
"""

import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Optional


def get_signing_key() -> bytes:
    """Obtiene la clave de firma desde variable de entorno.

    La clave se genera automáticamente si no existe (dev/lab).
    En producción debe venir de un vault o secret manager.
    """
    key = os.environ.get("AUDIT_SIGNING_KEY", "")
    if not key:
        # Lab: clave derivada del environment
        key = "promptguard-lab-audit-key-change-in-production"
    return key.encode("utf-8")


def sign_payload(payload: dict) -> str:
    """Firma un payload JSON con HMAC-SHA256.

    Args:
        payload: Diccionario a firmar

    Returns:
        Firma hex (64 caracteres)
    """
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hmac.new(
        get_signing_key(),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(payload: dict, signature: str) -> bool:
    """Verifica la firma de un payload.

    Args:
        payload: Diccionario original
        signature: Firma a verificar

    Returns:
        True si la firma es válida
    """
    expected = sign_payload(payload)
    return hmac.compare_digest(expected, signature)


def generate_audit_id() -> str:
    """Genera un ID de auditoría único y determinístico.

    Formato: aud_<timestamp>_<hash6>
    """
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%d%H%M%S")
    random_part = os.urandom(3).hex()
    return f"aud_{timestamp}_{random_part}"


def hash_pii(value: str) -> str:
    """Hash unidireccional de un valor PII para logs.

    Permite referencia sin almacenar el valor original.

    Args:
        value: Valor PII a hashear

    Returns:
        Hash SHA256 truncado (16 caracteres)
    """
    return hashlib.sha256(
        value.encode("utf-8") + get_signing_key()
    ).hexdigest()[:16]
