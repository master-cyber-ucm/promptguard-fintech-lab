"""Tests del SOC: almacén, collector, base de conocimiento y endpoints.

Cubren sobre todo las dos propiedades que el SOC promete y que son fáciles de romper
sin darse cuenta: que se registran también las decisiones ALLOW, y que un fallo del SOC
jamás se propaga al chat.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.soc import knowledge, store
from src.soc.collector import SocCollector, add_safe, run_id_desde_audit_subdir


@pytest.fixture(autouse=True)
def base_limpia(tmp_path):
    store.reset_for_tests(tmp_path / "soc.db")
    yield
    store.reset_for_tests()


def _turno(**extra):
    base = dict(session_id="ses_1", user_id="usr_001", endpoint="proxy",
                origen="interactivo", postura="proxy=True", prompt="hola")
    base.update(extra)
    return base


# --- Almacén ---------------------------------------------------------------------

def test_un_turno_sin_eventos_se_guarda_igual():
    """Modo vulnerable: cero componentes evaluaron. Es un hallazgo, no un turno perdido."""
    tid = store.record_turn(turno=_turno(vulnerable=True), eventos=[])
    t = store.get_turn(tid)
    assert t["eventos"] == []
    assert t["vulnerable"] is True
    assert t["bloqueado"] is False


def test_los_eventos_allow_se_persisten():
    tid = store.record_turn(turno=_turno(), eventos=[
        {"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"},
        {"componente": "output_auditor", "objetivo": "respuesta", "accion": "ALLOW"},
    ])
    acciones = [e["accion"] for e in store.get_turn(tid)["eventos"]]
    assert acciones == ["ALLOW", "ALLOW"], "un ALLOW también es información"


def test_el_turno_queda_marcado_como_bloqueado_si_algun_evento_bloquea():
    tid = store.record_turn(turno=_turno(), eventos=[
        {"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"},
        {"componente": "tool_gatekeeper", "objetivo": "tool", "accion": "BLOCK"},
    ])
    assert store.get_turn(tid)["bloqueado"] is True


def test_el_orden_temporal_de_los_eventos_se_conserva():
    tid = store.record_turn(turno=_turno(), eventos=[
        {"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"},
        {"componente": "tool_gatekeeper", "objetivo": "tool", "accion": "BLOCK"},
        {"componente": "output_auditor", "objetivo": "respuesta", "accion": "ALLOW"},
    ])
    assert [e["componente"] for e in store.get_turn(tid)["eventos"]] == [
        "input_sanitizer", "tool_gatekeeper", "output_auditor"
    ]


def test_las_alertas_solo_nacen_de_block_y_suspicious():
    tid = store.record_turn(turno=_turno(), eventos=[
        {"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"},
        {"componente": "tool_gatekeeper", "objetivo": "tool", "accion": "BLOCK"},
        {"componente": "pii_shield", "objetivo": "respuesta", "accion": "SUSPICIOUS"},
    ])
    store.raise_alerts(tid, "CRITICAL", "fixture")
    alertas = store.get_turn(tid)["alertas"]
    assert len(alertas) == 2
    assert {a["severidad_origen"] for a in alertas} == {"fixture"}
    assert {a["estado"] for a in alertas} == {"nueva"}


def test_el_cursor_permite_pedir_solo_lo_nuevo():
    primero = store.record_turn(turno=_turno(), eventos=[])
    segundo = store.record_turn(turno=_turno(session_id="ses_2"), eventos=[])
    nuevos = store.list_turns(since=primero)
    assert [t["id"] for t in nuevos] == [segundo]


def test_filtrar_por_componente_no_duplica_turnos():
    store.record_turn(turno=_turno(), eventos=[
        {"componente": "pii_shield", "objetivo": "prompt", "accion": "ALLOW"},
        {"componente": "pii_shield", "objetivo": "respuesta", "accion": "ALLOW"},
    ])
    assert len(store.list_turns(componente="pii_shield")) == 1


def test_relacionados_encuentra_sesiones_del_mismo_fixture():
    store.record_turn(turno=_turno(session_id="ses_a", fixture_id="atk_010"), eventos=[])
    store.record_turn(turno=_turno(session_id="ses_b", fixture_id="atk_010"), eventos=[])
    r = store.related_sessions("ses_a")
    assert [s["session_id"] for s in r["mismo_fixture"]] == ["ses_b"]


def test_borrar_una_corrida_arrastra_sus_eventos():
    tid = store.record_turn(turno=_turno(run_id="run_x"), eventos=[
        {"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"},
    ])
    assert store.delete_run("run_x") == 1
    assert store.get_turn(tid) is None


# --- Collector -------------------------------------------------------------------

def test_el_collector_deduce_origen_y_run_de_la_ruta_de_auditoria():
    c = SocCollector(session_id="s", user_id="u", endpoint="proxy",
                     audit_subdir="/app/audit/runs/20260809_1042_qwen/proxy")
    assert c.run_id == "20260809_1042_qwen"
    assert c.origen == "suite"


def test_sin_audit_subdir_el_origen_es_interactivo():
    c = SocCollector(session_id="s", user_id="u", endpoint="proxy")
    assert c.run_id is None
    assert c.origen == "interactivo"


def test_run_id_tolera_rutas_que_no_son_de_corrida():
    assert run_id_desde_audit_subdir(None) is None
    assert run_id_desde_audit_subdir("/tmp/manual/proxy") == "manual"


def test_el_collector_resuelve_la_taxonomia_desde_el_fixture():
    c = SocCollector(session_id="s", user_id="usr_001", endpoint="proxy", fixture_id="atk_010")
    c.add(componente="tool_gatekeeper", objetivo="tool", accion="BLOCK")
    t = store.get_turn(c.flush(prompt="p"))
    assert t["categoria"] == "LLM06-excessive-agency"
    assert t["subcategoria"] == "confused-deputy"


def test_un_fallo_al_volcar_no_propaga_la_excepcion(monkeypatch):
    """La promesa de que el SOC no tumba el chat, verificada y no asumida."""
    def explota(**_):
        raise RuntimeError("disco lleno")
    monkeypatch.setattr(store, "record_turn", explota)

    c = SocCollector(session_id="s", user_id="u", endpoint="proxy")
    c.add(componente="input_sanitizer", objetivo="prompt", accion="ALLOW")
    assert c.flush(prompt="p") is None   # devuelve None, no lanza


def test_add_safe_traga_los_errores_del_collector():
    class Roto:
        def add(self, **_):
            raise RuntimeError("boom")
    add_safe(Roto(), componente="x", objetivo="prompt", accion="ALLOW")
    add_safe(None, componente="x", objetivo="prompt", accion="ALLOW")


def test_el_collector_solo_vuelca_una_vez():
    c = SocCollector(session_id="s", user_id="u", endpoint="proxy")
    assert c.flush(prompt="p") is not None
    assert c.flush(prompt="p") is None


# --- Base de conocimiento --------------------------------------------------------

def test_la_taxonomia_de_fixtures_y_documentos_coincide():
    idx = knowledge.indice()
    assert idx["disponible"], "no se encontró docs/ — revisa el montaje del contenedor"
    for cat in ("LLM01-prompt-injection", "LLM02-sensitive-information-disclosure",
                "LLM06-excessive-agency", "LLM07-system-prompt-leakage"):
        assert cat in idx["taxonomia"]


def test_las_subcategorias_sin_documentacion_se_declaran():
    """El hueco de _extensiones se enseña, no se esconde."""
    huecos = {h["subcategoria"] for h in knowledge.indice()["sin_documentar"]}
    assert {"jailbreak", "chained", "ingenieria-social", "ofuscacion"} <= huecos


def test_cada_subcategoria_documentada_tiene_playbook_y_defensa():
    d = knowledge.documentos_de("LLM02-sensitive-information-disclosure", "pii-harvesting")
    assert d["disponible"]
    assert d["playbook"] is not None
    assert d["defensa"] is not None
    assert len(d["ataque"]) >= 7


def test_una_taxonomia_inexistente_no_revienta():
    d = knowledge.documentos_de("_extensiones", "jailbreak")
    assert d["disponible"] is False
    assert d["playbook"] is None


def test_la_severidad_declara_su_procedencia():
    _, origen = knowledge.severidad_de("atk_010", "LLM06-excessive-agency", None)
    assert origen == "fixture"
    sev, origen = knowledge.severidad_de(None, "LLM06-excessive-agency", None)
    assert (sev, origen) == ("CRITICAL", "mapa-categoria")
    sev, origen = knowledge.severidad_de(None, None, None)
    assert origen == "por-defecto"


# --- API -------------------------------------------------------------------------

@pytest.fixture
def cliente():
    return TestClient(app)


def test_overview_responde_con_la_base_vacia(cliente):
    r = cliente.get("/api/v1/soc/overview")
    assert r.status_code == 200
    d = r.json()
    assert d["totales"]["turnos"] == 0
    assert len(d["cobertura"]) >= 7


def test_la_matriz_de_bloqueos_incluye_prompt_injection_directa(cliente):
    """La matriz incluye todos los vectores, incluso sin actividad todavía."""
    filas = cliente.get("/api/v1/soc/overview").json()["cobertura"]
    directa = next(f for f in filas if f["subcategoria"] == "directa")
    assert directa["turnos"] == 0
    assert directa["no_bloqueados"] == 0
    assert directa["bloqueos_por_componente"] == {}


def test_la_matriz_cuenta_turnos_por_componente_y_sin_bloqueo(cliente):
    categoria = "LLM01-prompt-injection"
    subcategoria = "directa"
    store.record_turn(
        turno=_turno(categoria=categoria, subcategoria=subcategoria),
        eventos=[{"componente": "input_sanitizer", "objetivo": "prompt", "accion": "BLOCK"}],
    )
    store.record_turn(
        turno=_turno(session_id="ses_2", categoria=categoria, subcategoria=subcategoria),
        eventos=[{"componente": "output_auditor", "objetivo": "respuesta", "accion": "BLOCK"}],
    )
    store.record_turn(
        turno=_turno(session_id="ses_3", categoria=categoria, subcategoria=subcategoria),
        eventos=[{"componente": "input_sanitizer", "objetivo": "prompt", "accion": "ALLOW"}],
    )

    filas = cliente.get("/api/v1/soc/overview").json()["cobertura"]
    directa = next(f for f in filas if f["categoria"] == categoria and f["subcategoria"] == subcategoria)
    assert directa["turnos"] == 3
    assert directa["bloqueos_por_componente"] == {"input_sanitizer": 1, "output_auditor": 1}
    assert directa["no_bloqueados"] == 1


def test_overview_filtra_agregados_y_matriz_por_endpoint(cliente):
    categoria, subcategoria = "LLM01-prompt-injection", "directa"
    store.record_turn(
        turno=_turno(endpoint="proxy", categoria=categoria, subcategoria=subcategoria),
        eventos=[{"componente": "input_sanitizer", "objetivo": "prompt", "accion": "BLOCK"}],
    )
    store.record_turn(
        turno=_turno(endpoint="simple-prompt", categoria=categoria, subcategoria=subcategoria),
        eventos=[{"componente": "output_auditor", "objetivo": "respuesta", "accion": "BLOCK"}],
    )

    data = cliente.get("/api/v1/soc/overview?endpoint=proxy").json()
    directa = next(f for f in data["cobertura"] if f["subcategoria"] == subcategoria)
    assert data["totales"]["turnos"] == 1
    assert data["totales"]["eventos"] == 1
    assert directa["turnos"] == 1
    assert directa["bloqueos_por_componente"] == {"input_sanitizer": 1}


def test_turno_inexistente_devuelve_404(cliente):
    assert cliente.get("/api/v1/soc/turns/9999").status_code == 404


def test_el_detalle_de_un_turno_trae_su_conocimiento(cliente):
    # Vía el collector, que es quien resuelve la taxonomía desde el fixture — el store
    # solo guarda lo que le den.
    c = SocCollector(session_id="ses_1", user_id="usr_001", endpoint="proxy", fixture_id="atk_010")
    c.add(componente="tool_gatekeeper", objetivo="tool", accion="BLOCK")
    tid = c.flush(prompt="dame el saldo de una cuenta ajena")
    d = cliente.get(f"/api/v1/soc/turns/{tid}").json()
    assert d["conocimiento"]["disponible"] is True
    assert d["conocimiento"]["playbook"]["playbook"] is True


def test_actualizar_una_alerta_cambia_su_estado(cliente):
    tid = store.record_turn(turno=_turno(), eventos=[
        {"componente": "tool_gatekeeper", "objetivo": "tool", "accion": "BLOCK"},
    ])
    store.raise_alerts(tid, "HIGH", "mapa-categoria")
    alert_id = cliente.get("/api/v1/soc/alerts").json()["alertas"][0]["id"]
    assert cliente.patch(f"/api/v1/soc/alerts/{alert_id}",
                         json={"estado": "revisada", "nota": "falso positivo"}).status_code == 200
    assert cliente.get("/api/v1/soc/alerts").json()["alertas"][0]["estado"] == "revisada"


def test_un_estado_de_alerta_invalido_se_rechaza(cliente):
    assert cliente.patch("/api/v1/soc/alerts/1", json={"estado": "inventado"}).status_code == 422


def test_documento_inexistente_devuelve_404(cliente):
    assert cliente.get("/api/v1/soc/kb/doc", params={"clave": "no/existe"}).status_code == 404


def test_se_puede_leer_un_playbook_completo(cliente):
    clave = "ataques/LLM02-sensitive-information-disclosure/pii-harvesting/07-playbook-incident-response"
    d = cliente.get("/api/v1/soc/kb/doc", params={"clave": clave}).json()
    assert "Contención" in d["contenido"] or "Contencion" in d["contenido"]
    assert d["playbook"] is True


def test_comparar_dos_corridas_devuelve_los_dos_lados(cliente):
    store.record_turn(turno=_turno(run_id="run_a"), eventos=[
        {"componente": "tool_gatekeeper", "objetivo": "tool", "accion": "BLOCK"}])
    store.record_turn(turno=_turno(run_id="run_b", vulnerable=True), eventos=[])
    d = cliente.get("/api/v1/soc/runs/compare", params={"a": "run_a", "b": "run_b"}).json()
    assert d["a"]["bloqueados"] == 1
    assert d["b"]["vulnerables"] == 1
    assert d["b"]["componentes"] == []
