from scripts.report import _model_provenance

def test_etiqueta_de_defensa_no_sobrescribe_el_modelo_solicitado():
    result = _model_provenance({"requested_model": "qwen2.5:3b"}, {"proxy": [{"model": "proxy-input_sanitizer"}]})
    assert result["requested_model"] == "qwen2.5:3b" and result["effective_models_by_endpoint"]["proxy"] == []

def test_discrepancia_se_declara():
    result = _model_provenance({"requested_model": "qwen2.5:3b"}, {"proxy": [{"model": "llama3.1:8b"}]})
    assert result["instrumentation_errors"][0]["effective_model"] == "llama3.1:8b"
