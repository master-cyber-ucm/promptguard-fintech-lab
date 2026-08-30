from src.core.client_messages import client_message_for

def test_no_expone_reglas_internas_en_el_mensaje_cliente():
    message = client_message_for("input_sanitizer")
    assert "BLOCKED_BY" not in message and "regex" not in message.lower()
