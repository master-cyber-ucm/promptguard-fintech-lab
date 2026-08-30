"""Tests de la guardia de salida `core/leak_guard.py` (Fase 2.7) — arreglo del Fallo 1 de (D)
detectado en la verificación manual: (D) el Tool Gatekeeper solo protege la INVOCACIÓN de las
tools sensibles; si el LLM nunca llega a invocarlas y aun así declara en texto libre el
saldo/datos de una cuenta, (D) no tiene nada que interceptar. `confidential_leak_guard` cierra
ese hueco desde el otro extremo: escanea la respuesta final en busca de IBANs no respaldados por
una tool call real.
"""

from __future__ import annotations

from src.core.leak_guard import confidential_leak_guard, ibans_from_text, verified_ibans_from_tools

OWN_ACCOUNT = "ES9121000418450200051332"
OTHER_ACCOUNT = "ES3421000418450200051334"


def test_sin_iban_en_la_respuesta_no_cambia_nada():
    texto = "Hola María, tu nómina ha sido recibida correctamente. ¿En qué más puedo ayudarte?"
    resultado, bloqueado = confidential_leak_guard(texto, [], OWN_ACCOUNT)
    assert bloqueado is False
    assert resultado == texto


def test_mencionar_la_cuenta_propia_no_dispara_la_guardia():
    texto = f"El saldo de tu cuenta {OWN_ACCOUNT} es de 15.420,50 €."
    resultado, bloqueado = confidential_leak_guard(texto, [], OWN_ACCOUNT)
    assert bloqueado is False
    assert resultado == texto


def test_iban_ajeno_alucinado_sin_tool_call_real_es_bloqueado():
    """El caso real detectado: el LLM invoca `consulta_producto` (sin relación) y luego inventa
    un saldo para la cuenta objetivo — no hay ninguna tool call que respalde ese IBAN."""
    tools_used = [
        {"tool": "consulta_producto", "args": "{}"},
        {"tool": "consulta_producto", "result": '{"cuenta_corriente": {"name": "..."}}'},
    ]
    texto = f"El saldo de tu cuenta corriente {OTHER_ACCOUNT} es de €0,00."
    resultado, bloqueado = confidential_leak_guard(texto, tools_used, OWN_ACCOUNT)
    assert bloqueado is True
    assert OTHER_ACCOUNT not in resultado


def test_iban_ajeno_aportado_por_el_cliente_puede_repetirse():
    texto = f"Revisa el IBAN del destinatario: {OTHER_ACCOUNT}."
    resultado, bloqueado = confidential_leak_guard(
        texto,
        [],
        OWN_ACCOUNT,
        ibans_from_text(f"Quiero transferir dinero a {OTHER_ACCOUNT}"),
    )

    assert bloqueado is False
    assert resultado == texto


def test_iban_ajeno_respaldado_por_tool_call_real_no_se_bloquea():
    """Si (C) falla y el LLM sí consulta la cuenta ajena de verdad (status: ok), la guardia no
    debe interferir — esa es responsabilidad de (A)/(B)/(C)/(D), no de esta guardia. La guardia
    solo cierra el hueco de datos FABRICADOS sin ninguna consulta real detrás."""
    tools_used = [
        {"tool": "consulta_saldo", "args": f'{{"account_id":"{OTHER_ACCOUNT}"}}'},
        {
            "tool": "consulta_saldo",
            "result": (
                f'{{"status": "ok", "account_id": "{OTHER_ACCOUNT}", "owner": "Ana Fernández Ruiz", '
                f'"balance": "231,500.00 €"}}'
            ),
        },
    ]
    texto = f"El saldo de la cuenta {OTHER_ACCOUNT} es 231,500.00 €."
    resultado, bloqueado = confidential_leak_guard(texto, tools_used, OWN_ACCOUNT)
    assert bloqueado is False
    assert resultado == texto


def test_iban_denegado_por_el_gatekeeper_y_luego_citado_en_el_texto_se_bloquea():
    """Aunque (D) deniegue correctamente, si el texto final repite el IBAN denegado (p. ej. en el
    propio mensaje de rechazo), la guardia lo sustituye también — minimiza el detalle expuesto al
    cliente, coherente con la nota de diseño de reducir información sensible en las respuestas."""
    tools_used = [
        {"tool": "consulta_saldo", "args": f'{{"account_id":"{OTHER_ACCOUNT}"}}'},
        {
            "tool": "consulta_saldo",
            "result": (
                f'{{"status": "denied", "reason": "El usuario autenticado no es titular de esta '
                f'cuenta.", "account_id_solicitado": "{OTHER_ACCOUNT}"}}'
            ),
        },
    ]
    texto = f"Lo sentimos, pero no eres titular de la cuenta {OTHER_ACCOUNT}."
    resultado, bloqueado = confidential_leak_guard(texto, tools_used, OWN_ACCOUNT)
    assert bloqueado is True
    assert OTHER_ACCOUNT not in resultado


def test_iban_de_tercero_en_transferencia_completada_no_se_bloquea():
    """El destino de una transferencia (`to_account`) es legítimamente de un tercero — su
    resultado no tiene `status: denied`, así que la guardia lo trata como verificado."""
    tools_used = [
        {
            "tool": "transferencia_nacional",
            "result": (
                f'{{"status": "completed", "from": "{OWN_ACCOUNT}", "to": "{OTHER_ACCOUNT}", '
                f'"amount": "50.00 €"}}'
            ),
        },
    ]
    texto = f"Transferencia realizada correctamente a la cuenta {OTHER_ACCOUNT}."
    resultado, bloqueado = confidential_leak_guard(texto, tools_used, OWN_ACCOUNT)
    assert bloqueado is False
    assert resultado == texto


# ──────────────────────────────────────────────────────────────────────────────
# verified_ibans_from_tools — usada también por el PII Shield (ver api/routes/chat.py) para no
# marcar como fuga un dato que el propio usuario puso en la operación.
# ──────────────────────────────────────────────────────────────────────────────

def test_verified_ibans_from_tools_ignora_resultados_denegados():
    tools_used = [
        {"tool": "consulta_saldo", "result": f'{{"status": "denied", "account_id_solicitado": "{OTHER_ACCOUNT}"}}'},
    ]
    assert verified_ibans_from_tools(tools_used) == frozenset()


def test_verified_ibans_from_tools_recoge_ibanes_de_resultados_reales():
    tools_used = [
        {"tool": "consulta_saldo", "result": f'{{"status": "ok", "account_id": "{OTHER_ACCOUNT}"}}'},
        {"tool": "consulta_saldo", "args": f'{{"account_id":"{OTHER_ACCOUNT}"}}'},  # sin "result": ignorado
    ]
    assert verified_ibans_from_tools(tools_used) == frozenset({OTHER_ACCOUNT})
