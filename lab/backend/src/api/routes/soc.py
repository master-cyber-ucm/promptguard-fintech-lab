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
def overview(endpoint: Optional[str] = None):
    """Postura del sistema: lo que la pantalla de entrada necesita en una sola llamada."""
    return {
        "totales": store.totals(endpoint=endpoint),
        "componentes": store.component_activity(endpoint=endpoint),
        "taxonomia": store.taxonomy_activity(endpoint=endpoint),
        "cobertura": _cobertura(endpoint=endpoint),
        "runs": store.list_runs(endpoint=endpoint)[:8],
        "endpoint": endpoint,
        "sin_documentar": knowledge.indice()["sin_documentar"],
    }


# Vectores documentados. Se completa en ``_cobertura`` con los que existan en las
# fixtures aunque todavía no tengan documentación, de modo que la tabla nunca omite
# una familia atacable por falta de un diseño de defensa.
_VECTORES_DOCUMENTADOS = (
    ("LLM01-prompt-injection", "directa"),
    ("LLM01-prompt-injection", "indirecta-documento"),
    ("LLM02-sensitive-information-disclosure", "cross-context-leakage"),
    ("LLM02-sensitive-information-disclosure", "pii-harvesting"),
    ("LLM06-excessive-agency", "acciones-no-autorizadas"),
    ("LLM06-excessive-agency", "confused-deputy"),
    ("LLM07-system-prompt-leakage", "filtrado-por-repeticion"),
)


def _bloqueos_por_componente(endpoint: Optional[str] = None) -> dict[tuple, dict[str, int]]:
    """Turnos bloqueados por componente y subcategoría.

    Se cuentan turnos distintos: si una implementación llegase a emitir dos eventos
    ``BLOCK`` del mismo componente en un turno, la matriz sigue representando turnos,
    no eventos.
    """
    from src.soc import store as _s
    with _s._lock:
        conn = _s._connect()
        where, valores = ("", []) if not endpoint else (" AND t.endpoint=?", [endpoint])
        filas = conn.execute(
            """SELECT t.categoria, t.subcategoria, e.componente, COUNT(DISTINCT t.id) AS n
               FROM soc_event e JOIN soc_turn t ON t.id = e.turn_id
               WHERE e.accion = 'BLOCK' AND t.categoria IS NOT NULL""" + where +
            " GROUP BY t.categoria, t.subcategoria, e.componente",
            valores,
        ).fetchall()
    out: dict[tuple, dict[str, int]] = {}
    for f in filas:
        out.setdefault((f["categoria"], f["subcategoria"]), {})[f["componente"]] = f["n"]
    return out


def _cobertura(endpoint: Optional[str] = None) -> list[dict]:
    """Matriz de resultados observados por vector.

    No atribuye una defensa por diseño ni extrapola eficacia: expone cuántos turnos
    bloqueó realmente cada componente y cuántos no quedaron bloqueados.
    """
    actividad = {
        (t["categoria"], t["subcategoria"]): t for t in store.taxonomy_activity(endpoint=endpoint)
    }
    por_comp = _bloqueos_por_componente(endpoint=endpoint)
    vectores = set(_VECTORES_DOCUMENTADOS)
    huecos_por_clave = {
        (h["categoria"], h["subcategoria"]): h
        for h in knowledge.indice()["sin_documentar"]
    }
    vectores.update(huecos_por_clave)

    filas = []
    for cat, sub in sorted(vectores):
        a = actividad.get((cat, sub), {})
        bloqueos = por_comp.get((cat, sub), {})
        turnos = a.get("turnos", 0)
        bloqueados = a.get("bloqueados", 0) or 0
        filas.append({
            "categoria": cat, "subcategoria": sub,
            "turnos": turnos,
            "bloqueados": bloqueados,
            "no_bloqueados": turnos - bloqueados,
            "bloqueos_por_componente": bloqueos,
            "documentada": (cat, sub) not in huecos_por_clave,
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
    # Para la navegación histórica pedimos una fila adicional: permite saber si hay
    # una página siguiente sin contar toda la tabla. El polling incremental mantiene
    # exactamente su límite para no saltarse un turno entre sondeos.
    es_paginacion = since is None
    filas = store.list_turns(
        since=since, before=before, limit=limit + 1 if es_paginacion else limit, componente=componente,
        accion=accion, texto=texto, endpoint=endpoint, origen=origen, run_id=run_id,
        session_id=session_id, user_id=user_id, categoria=categoria, fixture_id=fixture_id,
    )
    has_more = es_paginacion and len(filas) > limit
    return {"turnos": filas[:limit], "cursor": store.totals()["cursor"], "has_more": has_more}


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
