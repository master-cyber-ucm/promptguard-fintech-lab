"""Mensajes estables y seguros para bloqueos de defensas."""
_MESSAGES = {
    "input_sanitizer": "No hemos podido procesar esta solicitud por motivos de seguridad.",
    "pii_shield": "No hemos podido procesar esta solicitud por motivos de privacidad.",
    "rate_limiter": "Has realizado demasiadas solicitudes. Inténtalo de nuevo en unos instantes.",
    "budget_guard": "No podemos completar la solicitud en este momento. Inténtalo más tarde.",
    "document_sanitizer": "No hemos podido procesar el documento adjunto por motivos de seguridad.",
}
def client_message_for(component: str) -> str:
    return _MESSAGES.get(component, "No hemos podido procesar esta solicitud. Inténtalo de nuevo.")
