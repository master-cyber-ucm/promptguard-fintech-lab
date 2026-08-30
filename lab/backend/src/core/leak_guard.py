"""Leak Guard — defensa determinista de LLM02:2025 Cross-Context Data Leakage (ataque #3 del
catálogo, `docs/defensas/LLM02-sensitive-information-disclosure/cross-context-leakage.md`).

Nace como `_confidential_leak_guard` dentro de `api/routes/chat.py` (Fase 2.7 — arreglo del
Fallo 1 de (D) detectado en la verificación manual) y se promueve a módulo propio en el saneado
de `TODOs.md §P5`: el diseño original describía este control como una extensión del Output
Auditor, pero la implementación real resuelve un problema distinto (IBAN ajeno no respaldado por
ninguna tool call, no secretos de configuración del system prompt) y merece su propio espacio,
igual que `output_auditor.py` y `pii_shield.py`.

(D) el Tool Gatekeeper solo protege la INVOCACIÓN de `consulta_saldo` / `transferencia_
nacional` / `bloquear_tarjeta` — si el LLM nunca llega a invocarlas (llama a una tool sin
relación, o ninguna) y aun así declara en texto libre el saldo o los datos de una cuenta,
(D) no tiene ninguna llamada que interceptar. Esta guardia cierra ese hueco desde el otro
extremo: escanea la respuesta final en busca de un IBAN español y, si aparece uno que no sea
la cuenta propia del usuario NI provenga de un resultado real (no denegado) de una tool call
de este mismo turno, sustituye la respuesta completa por un mensaje genérico.

Deliberadamente NO exige que además haya una cifra monetaria junto al IBAN para disparar —
cualquier IBAN ajeno no verificado se trata como dato sensible, incluida la mención de una
cuenta denegada por (D) en un mensaje de rechazo (coherente con la nota de diseño de este
mismo módulo: minimizar el detalle expuesto al cliente). Es determinista — regex + cruce
contra `tools_used` real —, no depende de que el LLM "decida" no alucinar.

Relación con los controles ya existentes (no se solapan, se complementan):

  - `output_auditor.audit_response`: cubre SECRETOS DE CONFIGURACIÓN (LLM07), no datos de
    clientes. Ejes distintos — no debe confundirse con este módulo pese al parecido de nombre
    en el diseño original.
  - `pii_shield.redact_foreign_pii`: cubre el resto de entidades — nombre de titular, saldo,
    tarjeta, DNI, teléfono, email — que este módulo no mira. Es más laxo que este módulo para
    IBANs (no exige respaldo de tool call), así que corre después: si esta guardia ya sustituyó
    la respuesta, no queda nada que tokenizar.
  - Tool Gatekeeper (`agents/tools.py`): impide que el dato ajeno ENTRE al contexto vía tool.
    Este módulo asume que el Gatekeeper puede haber sido esquivado (el modelo fabrica el dato,
    o lo arrastra de un documento adjunto) y controla la SALIDA.

Alcance declarado — lo que este módulo NO hace, a propósito:

  - No cruza IMPORTES monetarios contra el saldo de otras cuentas (§4.3 del diseño): un
    "4.230,55 €" en la respuesta no se compara contra ningún importe visto en el turno. Sigue
    siendo un hueco abierto — un IBAN ajeno se bloquea, una cifra ajena sin IBAN al lado no.
  - No valida que el `session_id` pertenezca al `user_id` autenticado en cada lectura (I3 del
    diseño): `agents/session_store.py` indexa solo por `session_id`. Este módulo cierra la fuga
    DENTRO de un turno, no una fuga entre sesiones distintas si un `session_id` se filtrara o
    colisionara.
  - No dispara una alerta dedicada al DPO: la Alerta queda en el SOC (`soc_alert`, severidad
    `CRITICAL` por mapeo de categoría) para revisión humana, pero no hay integración con un
    canal de notificación real — coherente con que el resto del pipeline tampoco la tiene.

No es una decisión de "no hacer": son huecos reales, documentados aquí y en el §5 del diseño
para que no se lean como cobertura completa.
"""

from __future__ import annotations

import re

_IBAN_PATTERN = re.compile(r"\bES\d{22}\b")

CONFIDENTIAL_LEAK_SAFE_MESSAGE = (
    "No puedo confirmar esa información en este momento. Si necesitas datos sobre otra cuenta, "
    "contacta con soporte para verificarlos."
)


def ibans_from_text(text: str) -> frozenset[str]:
    """Extrae IBANes normalizados que ya estaban presentes en un texto de entrada."""
    return frozenset(_IBAN_PATTERN.findall(text.upper()))


def confidential_leak_guard(
    response_text: str,
    tools_used: list[dict],
    own_account: str,
    user_provided_ibans: frozenset[str] = frozenset(),
) -> tuple[str, bool]:
    """Escanea `response_text` en busca de un IBAN español que no sea `own_account` ni esté
    respaldado por un resultado real (no denegado) de `tools_used` en este mismo turno. Los
    IBANes que el propio cliente ya incluyó en su mensaje también pueden repetirse: no son una
    divulgación nueva. Si aparece un IBAN distinto, sustituye la respuesta por un mensaje seguro.

    Devuelve `(texto_final, huella_detectada)`.
    """
    ibans_en_respuesta = set(_IBAN_PATTERN.findall(response_text))
    if not ibans_en_respuesta:
        return response_text, False

    ibans_verificados = {own_account.replace(" ", "").upper()}
    ibans_verificados.update(verified_ibans_from_tools(tools_used))
    ibans_verificados.update(user_provided_ibans)

    if ibans_en_respuesta - ibans_verificados:
        return CONFIDENTIAL_LEAK_SAFE_MESSAGE, True
    return response_text, False


def verified_ibans_from_tools(tools_used: list[dict]) -> frozenset[str]:
    """IBANs que una tool devolvió legítimamente en este turno (resultado no denegado).

    Mismo criterio que `confidential_leak_guard`: el IBAN destino de una transferencia que el
    propio cliente ordenó es ajeno pero legítimo. Se comparte con el PII Shield (vía
    `api/routes/chat.py`) para que no marque como fuga un dato que el usuario mismo puso en la
    operación.
    """
    verificados: set[str] = set()
    for tool in tools_used:
        resultado = tool.get("result", "")
        if resultado and '"status": "denied"' not in resultado:
            verificados.update(_IBAN_PATTERN.findall(resultado))
    return frozenset(verificados)
