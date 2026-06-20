"""Utilidades para detección y tokenización de números de tarjeta.

Soporta Visa, Mastercard, American Express y tarjetas de débito
españolas con validación Luhn.
"""

import re
from typing import Optional


# Patrones de tarjetas por tipo
CARD_PATTERNS = {
    "VISA": re.compile(r'\b4\d{12}(\d{3})?\b'),
    "MASTERCARD": re.compile(r'\b(?:5[1-5]\d{2}|2[2-7]\d{2})\d{12}\b'),
    "AMEX": re.compile(r'\b3[47]\d{13}\b'),
    # Tarjeta genérica 16 dígitos (fallback)
    "GENERIC_16": re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b'),
}


def luhn_checksum(card_number: str) -> bool:
    """Valida un número de tarjeta usando el algoritmo de Luhn.

    Args:
        card_number: Número de tarjeta como string (solo dígitos)

    Returns:
        True si pasa la validación Luhn

    Example:
        >>> luhn_checksum("4532015112830366")  # Visa test
        True
    """
    digits = [int(d) for d in card_number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]

    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))

    return total % 10 == 0


def detect_card_type(number: str) -> Optional[str]:
    """Detecta el tipo de tarjeta a partir del número.

    Args:
        number: Número de tarjeta (solo dígitos)

    Returns:
        Tipo de tarjeta o None
    """
    if re.match(r'^4', number):
        return "VISA"
    elif re.match(r'^5[1-5]', number) or re.match(r'^2[2-7]', number):
        return "MASTERCARD"
    elif re.match(r'^3[47]', number):
        return "AMEX"
    return "UNKNOWN"


def tokenize_card(card_number: str) -> str:
    """Tokeniza un número de tarjeta para redacción PII.

    Args:
        card_number: Número de tarjeta

    Returns:
        Tarjeta tokenizada (ej: [CARD-****0366])
    """
    digits = re.sub(r'\D', '', card_number)
    last_four = digits[-4:]
    card_type = detect_card_type(digits)
    return f"[{card_type}-****{last_four}]"


def extract_cards(text: str) -> list[dict]:
    """Extrae números de tarjeta de un texto.

    Returns:
        Lista de dicts con keys: value, card_type, start, end
    """
    results = []
    seen = set()

    for card_type, pattern in CARD_PATTERNS.items():
        for match in pattern.finditer(text):
            digits = re.sub(r'\D', '', match.group())
            if len(digits) >= 13 and digits not in seen:
                if luhn_checksum(digits):
                    seen.add(digits)
                    results.append({
                        "value": digits,
                        "value_original": match.group(),
                        "card_type": detect_card_type(digits),
                        "start": match.start(),
                        "end": match.end(),
                    })

    return sorted(results, key=lambda x: x["start"])


def redact_cards(text: str) -> tuple[str, list[dict]]:
    """Redacta todos los números de tarjeta en un texto.

    Returns:
        Tupla (texto_redactado, lista de entidades encontradas)
    """
    entities = []
    cards = extract_cards(text)

    # Redactar de atrás hacia adelante para no alterar posiciones
    result = text
    for card in reversed(cards):
        token = tokenize_card(card["value"])
        result = result[:card["start"]] + token + result[card["end"]:]
        entities.insert(0, {
            "type": "CREDIT_CARD",
            "value_original": card["value_original"],
            "value_tokenized": token,
            "position_start": card["start"],
            "position_end": card["start"] + len(token),
        })

    return result, entities


if __name__ == "__main__":
    test_text = "Mi visa es 4532 0151 1283 0366 y mi Mastercard es 5500 0000 0000 0004"
    print(f"Original: {test_text}")
    redacted, entities = redact_cards(test_text)
    print(f"Redacted: {redacted}")
    print(f"Entities: {entities}")
