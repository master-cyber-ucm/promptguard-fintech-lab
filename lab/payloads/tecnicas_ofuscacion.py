"""Catálogo de técnicas de ofuscación de texto CONOCIDAS — Fase 2.9 (red teaming automatizado).

Cierra parcialmente la limitación documentada en CAPITULO.md §5 ("no cubre la generación de
variantes nuevas"): las variantes de técnicas YA IDENTIFICADAS por un humano (ver
docs/evidencias/README.md §"Análisis de viabilidad de (A)") sí se generan aquí de forma
programática, en vez de escribir cada payload a mano. Lo que sigue siendo trabajo manual, por
naturaleza, es identificar la PRIMERA instancia de una técnica nunca vista — ninguna herramienta
de red teaming automatizado (Garak incluido) hace eso tampoco: todas ejecutan un catálogo de
técnicas conocidas de forma sistemática, no inventan categorías nuevas.

Cada función recibe una palabra y devuelve una variante ofuscada que:
  1. Es indistinguible (o casi) de la original para un lector humano.
  2. Ya NO coincide con el patrón literal que buscan las reglas de
     lab/backend/config/rules/injection_signatures.yaml (\\s, \\b, la palabra exacta).

Añadir una técnica nueva a este catálogo = una función más en TECHNIQUES. El motor de mutación
(generar_pdf_mutado.py + evidencia/motor_mutacion/) no necesita cambios.
"""

from __future__ import annotations

ZWS = "​"  # ZERO WIDTH SPACE — invisible al renderizar con una fuente TrueType real
                # (ver hallazgo en generar_pdf_unicode.py: con Helvetica estándar se corrompe).

# Homoglifos Cirílico → Latino visualmente idénticos en la mayoría de fuentes sans-serif.
_HOMOGLYPHS: dict[str, str] = {
    "a": "а",  # U+0430 CYRILLIC SMALL LETTER A
    "e": "е",  # U+0435 CYRILLIC SMALL LETTER IE
    "o": "о",  # U+043E CYRILLIC SMALL LETTER O
    "p": "р",  # U+0440 CYRILLIC SMALL LETTER ER
    "c": "с",  # U+0441 CYRILLIC SMALL LETTER ES
    "y": "у",  # U+0443 CYRILLIC SMALL LETTER U
    "x": "х",  # U+0445 CYRILLIC SMALL LETTER HA
    "i": "і",  # U+0456 CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
}


def zero_width(word: str) -> str:
    """Inserta ZWS entre cada letra. Rompe cualquier regex que use \\s o límites de palabra
    para encontrar la palabra literal, sin alterar su apariencia (con fuente TrueType real)."""
    return ZWS.join(list(word))


def homoglyph(word: str) -> str:
    """Sustituye cada letra sustituible por su homoglifo cirílico. La palabra ya no es la misma
    secuencia de puntos de código (aunque se vea casi idéntica), así que tampoco coincide con
    ningún patrón que busque la palabra Latina literal."""
    return "".join(_HOMOGLYPHS.get(ch.lower(), ch) for ch in word)


TECHNIQUES: dict[str, callable] = {
    "zero_width": zero_width,
    "homoglyph": homoglyph,
}
