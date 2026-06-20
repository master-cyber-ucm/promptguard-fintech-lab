"""Utilidades para validación y tokenización de IBANs.

Soporta IBANs españoles (ES + 22 dígitos) con validación checksum.
"""

import re
from typing import Optional


# Pattern: 2 letras + 22 dígitos (España)
IBAN_PATTERN = re.compile(r'\bES\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b')
IBAN_CLEAN_PATTERN = re.compile(r'\bES\d{22}\b')


def validate_iban(iban: str) -> bool:
    """Valida un IBAN español usando checksum.

    Args:
        iban: IBAN con o sin espacios (ES + 22 dígitos)

    Returns:
        True si el IBAN es válido

    Example:
        >>> validate_iban("ES9121000418450200051332")
        True
        >>> validate_iban("ES0000000000000000000000")
        False
    """
    iban_clean = iban.replace(" ", "").upper()
    if not re.match(r'^ES\d{22}$', iban_clean):
        return False

    # Mover los 4 primeros caracteres al final y reemplazar letras por números
    # E=14, S=28
    rearranged = iban_clean[4:] + "1428" + iban_clean[2:4]
    try:
        checksum = int(rearranged) % 97
        return checksum == 1
    except ValueError:
        return False


def tokenize_iban(iban: str, token_prefix: str = "IBAN") -> str:
    """Tokeniza un IBAN para redacción PII.

    Args:
        iban: IBAN original
        token_prefix: Prefijo del token

    Returns:
        IBAN tokenizado (ej: [IBAN-****1332])
    """
    iban_clean = iban.replace(" ", "").upper()
    last_four = iban_clean[-4:]
    return f"[{token_prefix}-****{last_four}]"


def extract_ibans(text: str) -> list[dict]:
    """Extrae todos los IBANs de un texto.

    Returns:
        Lista de dicts con keys: value, start, end
    """
    results = []
    for match in IBAN_PATTERN.finditer(text):
        iban = match.group().replace(" ", "")
        if validate_iban(iban):
            results.append({
                "value": iban,
                "value_original": match.group(),
                "start": match.start(),
                "end": match.end(),
            })
    return results


def redact_ibans(text: str, token_prefix: str = "IBAN") -> tuple[str, list[dict]]:
    """Redacta todos los IBANs válidos en un texto.

    Returns:
        Tupla (texto_redactado, lista de entidades encontradas)
    """
    entities = []
    offset = 0
    result = text

    for match in IBAN_PATTERN.finditer(text):
        iban = match.group().replace(" ", "")
        if validate_iban(iban):
            token = tokenize_iban(iban, token_prefix)
            original = match.group()
            start = match.start() + offset
            end = start + len(original)
            result = result[:start] + token + result[end:]
            offset += len(token) - len(original)
            entities.append({
                "type": "IBAN",
                "value_original": original,
                "value_tokenized": token,
                "position_start": start,
                "position_end": start + len(token),
            })

    return result, entities


if __name__ == "__main__":
    # Test rápido
    test_text = "Mi IBAN es ES91 2100 0418 4502 0005 1332 y el otro es ES76 2100 0418 4502 0005 1333"
    print(f"Original: {test_text}")
    redacted, entities = redact_ibans(test_text)
    print(f"Redacted: {redacted}")
    print(f"Entities: {entities}")
