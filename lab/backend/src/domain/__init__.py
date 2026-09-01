"""Servicios de dominio bancario.

Separados de `agents/tools.py` a propósito (P03): la capa de conversación *pide* una
operación; el dominio es quien la consuma y quien emite el Effect Receipt que lo
acredita. Un `status=completed` escrito por el wrapper es una afirmación sobre sí mismo.
"""
