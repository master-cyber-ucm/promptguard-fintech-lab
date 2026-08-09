"""API de lectura del SOC.

Todo lo que hay aquí es de lectura salvo dos cosas: actualizar el estado de una alerta
(el único juicio del sistema, y es humano y trazable) y borrar una corrida. El SOC no
decide nada sobre el tráfico.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.soc import knowledge, store

router = APIRouter(prefix="/soc", tags=["soc"])


class AlertUpdateBody(BaseModel):
    estado: Optional[str] = Field(default=None, pattern="^(nueva|revisada|descartada)$")
    nota: Optional[str] = None


@router.get("/overview")
def overview():
    """Postura del sistema: lo que la pantalla de entrada necesita en una sola llamada."""
    return {
        "totales": store.totals(),
        "componentes": store.component_activity(),
        "taxonomia": store.taxonomy_activity(),
        "cobertura": _cobertura(),
        "runs": store.list_runs()[:8],
        "sin_documentar": knowledge.indice()["sin_documentar"],
    }


# Qué componente defiende cada vector, y si esa defensa está realmente implementada.
# Es una tabla declarada a mano porque la relación vector→componente es una decisión de
# diseño (está en docs/defensas/README.md), no algo derivable del código.
_DEFENSA_POR_SUBCATEGORIA = {
    ("LLM01-prompt-injection", "directa"): ("input_sanitizer", False),
    ("LLM01-prompt-injection", "indirecta-documento"): ("document_sanitizer", True),
    ("LLM02-sensitive-information-disclosure", "cross-context-leakage"): ("leak_guard", True),
    ("LLM02-sensitive-information-disclosure", "pii-harvesting"): ("pii_shield", True),
    ("LLM06-excessive-agency", "acciones-no-autorizadas"): ("tool_gatekeeper", True),
    ("LLM06-excessive-agency", "confused-deputy"): ("tool_gatekeeper", True),
    ("LLM07-system-prompt-leakage", "filtrado-por-repeticion"): ("output_auditor", True),
}


def _bloqueos_por_componente() -> dict[tuple, dict[str, int]]:
    """Qué componente bloqueó de verdad en cada subcategoría.

    Necesario para no dejar una lectura falsa: un vector marcado "sin defensa" puede
    acumular bloqueos porque OTRA capa lo cazó. Sin decir cuál, la tabla parece
    contradecirse.
    """
    from src.soc import store as _s
    with _s._lock:
        conn = _s._connect()
        filas = conn.execute(
            """SELECT t.categoria, t.subcategoria, e.componente, COUNT(DISTINCT t.id) AS n
               FROM soc_event e JOIN soc_turn t ON t.id = e.turn_id
               WHERE e.accion = 'BLOCK' AND t.categoria IS NOT NULL
               GROUP BY t.categoria, t.subcategoria, e.componente"""
        ).fetchall()
    out: dict[tuple, dict[str, int]] = {}
    for f in filas:
        out.setdefault((f["categoria"], f["subcategoria"]), {})[f["componente"]] = f["n"]
    return out


def _cobertura() -> list[dict]:
    """Mapa de cobertura: qué vectores tienen defensa real y cuáles están descubiertos.

    `implementada=False` en Prompt Injection Directa no es un error del panel: el Input
    Sanitizer sigue siendo un esqueleto que devuelve ALLOW siempre. El SOC lo enseña.
    """
    actividad = {
        (t["categoria"], t["subcategoria"]): t for t in store.taxonomy_activity()
    }
    por_comp = _bloqueos_por_componente()
    filas = []
    for (cat, sub), (componente, implementada) in _DEFENSA_POR_SUBCATEGORIA.items():
        a = actividad.get((cat, sub), {})
        bloqueos = por_comp.get((cat, sub), {})
        filas.append({
            "categoria": cat,
            "subcategoria": sub,
            "componente": componente,
            "implementada": implementada,
            "turnos": a.get("turnos", 0),
            "bloqueados": a.get("bloqueados", 0) or 0,
            # Quién bloqueó realmente, y si fue el componente asignado a este vector
            "bloqueos_por_componente": bloqueos,
            "bloqueado_por_su_componente": bloqueos.get(componente, 0),
            "documentada": True,
        })
    for hueco in knowledge.indice()["sin_documentar"]:
        clave = (hueco["categoria"], hueco["subcategoria"])
        a = actividad.get(clave, {})
        filas.append({
            "categoria": hueco["categoria"],
            "subcategoria": hueco["subcategoria"],
            "componente": None,
            "implementada": False,
            "turnos": a.get("turnos", 0),
            "bloqueados": a.get("bloqueados", 0) or 0,
            "bloqueos_por_componente": por_comp.get(clave, {}),
            "bloqueado_por_su_componente": 0,
            "documentada": False,
        })
    return filas


@router.get("/turns")
def turns(
    since: Optional[int] = None,
    before: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=500),
    endpoint: Optional[str] = None,
    origen: Optional[str] = None,
    run_id: Optional[str] = None,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    categoria: Optional[str] = None,
    fixture_id: Optional[str] = None,
    componente: Optional[str] = None,
    accion: Optional[str] = None,
    texto: Optional[str] = None,
):
    """Stream de turnos. `since` es el cursor del polling incremental del frontend."""
    filas = store.list_turns(
        since=since, before=before, limit=limit, componente=componente,
        accion=accion, texto=texto, endpoint=endpoint, origen=origen, run_id=run_id,
        session_id=session_id, user_id=user_id, categoria=categoria, fixture_id=fixture_id,
    )
    return {"turnos": filas, "cursor": store.totals()["cursor"]}


@router.get("/turns/{turn_id}")
def turn(turn_id: int):
    t = store.get_turn(turn_id)
    if t is None:
        raise HTTPException(status_code=404, detail=f"Turno {turn_id} no encontrado")
    t["conocimiento"] = knowledge.documentos_de(t["categoria"], t["subcategoria"])
    return t


@router.get("/sessions/{session_id}")
def session(session_id: str):
    turnos = store.get_session(session_id)
    if not turnos:
        raise HTTPException(status_code=404, detail=f"Sesión {session_id} no encontrada")
    primero = turnos[0]
    return {
        "session_id": session_id,
        "turnos": turnos,
        "relacionados": store.related_sessions(session_id),
        "conocimiento": knowledge.documentos_de(primero["categoria"], primero["subcategoria"]),
    }


@router.get("/runs")
def runs():
    return {"runs": store.list_runs()}


@router.get("/runs/compare")
def compare_runs(a: str, b: str):
    """Compara dos corridas componente a componente.

    No dictamina cuál es mejor: pone las dos columnas al lado y deja la lectura a quien
    mira. Es la vista que responde a la pregunta 'qué cambia al activar las defensas'.
    """
    def _lado(run_id: str) -> dict:
        return {
            "run_id": run_id,
            "componentes": store.component_activity(run_id=run_id),
            "turnos": store.list_turns(run_id=run_id, limit=500),
        }

    lado_a, lado_b = _lado(a), _lado(b)
    for lado in (lado_a, lado_b):
        turnos = lado.pop("turnos")
        lado["total_turnos"] = len(turnos)
        lado["bloqueados"] = sum(1 for t in turnos if t["bloqueado"])
        lado["vulnerables"] = sum(1 for t in turnos if t["vulnerable"])
        lado["por_taxonomia"] = _agrupar(turnos)
    return {"a": lado_a, "b": lado_b}


def _agrupar(turnos: list[dict]) -> list[dict]:
    grupos: dict[tuple, dict] = {}
    for t in turnos:
        clave = (t["categoria"], t["subcategoria"])
        g = grupos.setdefault(clave, {
            "categoria": t["categoria"], "subcategoria": t["subcategoria"],
            "turnos": 0, "bloqueados": 0,
        })
        g["turnos"] += 1
        g["bloqueados"] += 1 if t["bloqueado"] else 0
    return sorted(grupos.values(), key=lambda g: (g["categoria"] or "", g["subcategoria"] or ""))


@router.delete("/runs/{run_id}")
def delete_run(run_id: str):
    return {"borrados": store.delete_run(run_id)}


@router.get("/alerts")
def alerts(estado: Optional[str] = None, limit: int = Query(default=100, ge=1, le=500)):
    return {"alertas": store.list_alerts(estado=estado, limit=limit)}


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, body: AlertUpdateBody):
    if not store.update_alert(alert_id, estado=body.estado, nota=body.nota):
        raise HTTPException(status_code=404, detail=f"Alerta {alert_id} no encontrada")
    return {"ok": True}


@router.get("/kb")
def kb_index():
    return knowledge.indice()


@router.get("/kb/for")
def kb_for(categoria: Optional[str] = None, subcategoria: Optional[str] = None):
    return knowledge.documentos_de(categoria, subcategoria)


@router.get("/kb/doc")
def kb_doc(clave: str):
    doc = knowledge.documento(clave)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Documento '{clave}' no encontrado")
    return doc
