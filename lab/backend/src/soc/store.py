"""Almacén SQLite del SOC — la proyección consultable de lo que pasó en cada turno.

Convive con los Session Files en Markdown, que siguen siendo la evidencia del TFM
(ver `docs/adr/0007-dos-almacenes-para-la-traza-de-un-turno.md`). Ninguno deriva del
otro: los dos se escriben en el mismo instante desde la misma estructura en memoria.

`sqlite3` es de la librería estándar — este módulo no añade ninguna dependencia.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(
    os.environ.get("SOC_DB_PATH", Path(__file__).resolve().parents[3] / "audit" / "soc.db")
)

# Una sola conexión guardada por un lock. FastAPI despacha los endpoints síncronos en un
# threadpool, así que `check_same_thread=False` es necesario y el lock es lo que mantiene
# la seguridad. A la escala de este lab (miles de filas, un usuario) no compensa un pool.
_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS soc_turn (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                      TEXT    NOT NULL,
    session_id              TEXT    NOT NULL,
    user_id                 TEXT    NOT NULL,
    endpoint                TEXT    NOT NULL,
    origen                  TEXT    NOT NULL,
    run_id                  TEXT,
    postura                 TEXT    NOT NULL,
    vulnerable              INTEGER NOT NULL DEFAULT 0,
    prompt                  TEXT    NOT NULL,
    respuesta               TEXT,
    modelo                  TEXT,
    latencia_total_ms       REAL,
    fixture_id              TEXT,
    fixture_kind            TEXT,
    fixture_expected_result TEXT,
    categoria               TEXT,
    subcategoria            TEXT,
    bloqueado               INTEGER NOT NULL DEFAULT 0,
    audit_file              TEXT
);

CREATE TABLE IF NOT EXISTS soc_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id     INTEGER NOT NULL REFERENCES soc_turn(id) ON DELETE CASCADE,
    orden       INTEGER NOT NULL,
    componente  TEXT    NOT NULL,
    objetivo    TEXT    NOT NULL,
    accion      TEXT    NOT NULL,
    confianza   REAL,
    razon       TEXT,
    regla       TEXT,
    attack_type TEXT,
    detalle     TEXT,
    latencia_ms REAL
);

CREATE TABLE IF NOT EXISTS soc_alert (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id          INTEGER NOT NULL REFERENCES soc_turn(id) ON DELETE CASCADE,
    event_id         INTEGER NOT NULL REFERENCES soc_event(id) ON DELETE CASCADE,
    ts               TEXT    NOT NULL,
    severidad        TEXT    NOT NULL,
    severidad_origen TEXT    NOT NULL,
    estado           TEXT    NOT NULL DEFAULT 'nueva',
    nota             TEXT,
    ts_actualizada   TEXT,
    UNIQUE(event_id)
);

CREATE INDEX IF NOT EXISTS ix_turn_ts        ON soc_turn(ts);
CREATE INDEX IF NOT EXISTS ix_turn_session   ON soc_turn(session_id);
CREATE INDEX IF NOT EXISTS ix_turn_run       ON soc_turn(run_id);
CREATE INDEX IF NOT EXISTS ix_turn_cat       ON soc_turn(categoria, subcategoria);
CREATE INDEX IF NOT EXISTS ix_turn_fixture   ON soc_turn(fixture_id);
CREATE INDEX IF NOT EXISTS ix_event_turn     ON soc_event(turn_id, orden);
CREATE INDEX IF NOT EXISTS ix_event_comp     ON soc_event(componente, accion);
CREATE INDEX IF NOT EXISTS ix_alert_estado   ON soc_alert(estado);
"""


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA foreign_keys=ON")
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def reset_for_tests(path: Optional[Path] = None) -> None:
    """Cierra la conexión y reapunta la base. Solo para tests."""
    global _conn, DB_PATH
    if _conn is not None:
        _conn.close()
        _conn = None
    if path is not None:
        DB_PATH = path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --- Escritura -------------------------------------------------------------------

def record_turn(*, turno: dict[str, Any], eventos: list[dict[str, Any]]) -> int:
    """Persiste un turno con todos sus Analysis Events en una sola transacción.

    Devuelve el `id` del turno, que es también el cursor que consume el polling del
    frontend. Los eventos se guardan **todos**, incluidos los de acción ALLOW: un
    componente que deja pasar es información, no silencio.
    """
    bloqueado = any(e.get("accion") == "BLOCK" for e in eventos)
    with _lock:
        conn = _connect()
        cur = conn.execute(
            """
            INSERT INTO soc_turn (
                ts, session_id, user_id, endpoint, origen, run_id, postura, vulnerable,
                prompt, respuesta, modelo, latencia_total_ms,
                fixture_id, fixture_kind, fixture_expected_result,
                categoria, subcategoria, bloqueado, audit_file
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                turno.get("ts") or _now(),
                turno["session_id"],
                turno["user_id"],
                turno["endpoint"],
                turno.get("origen", "interactivo"),
                turno.get("run_id"),
                turno.get("postura", ""),
                1 if turno.get("vulnerable") else 0,
                turno.get("prompt", ""),
                turno.get("respuesta"),
                turno.get("modelo"),
                turno.get("latencia_total_ms"),
                turno.get("fixture_id"),
                turno.get("fixture_kind"),
                turno.get("fixture_expected_result"),
                turno.get("categoria"),
                turno.get("subcategoria"),
                1 if bloqueado else 0,
                turno.get("audit_file"),
            ),
        )
        turn_id = int(cur.lastrowid)

        for orden, ev in enumerate(eventos):
            detalle = ev.get("detalle")
            conn.execute(
                """
                INSERT INTO soc_event (
                    turn_id, orden, componente, objetivo, accion,
                    confianza, razon, regla, attack_type, detalle, latencia_ms
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    turn_id, orden,
                    ev["componente"], ev["objetivo"], ev["accion"],
                    ev.get("confianza"), ev.get("razon"), ev.get("regla"),
                    ev.get("attack_type"),
                    json.dumps(detalle, ensure_ascii=False) if detalle else None,
                    ev.get("latencia_ms"),
                ),
            )
        conn.commit()
    return turn_id


def raise_alerts(turn_id: int, severidad: str, severidad_origen: str) -> int:
    """Materializa una alerta por cada evento BLOCK o SUSPICIOUS del turno.

    La severidad se **declara**, no se calcula: `severidad_origen` dice de dónde salió
    (`fixture`, `mapa-categoria` o `por-defecto`) para que el panel no presente como
    objetiva una puntuación que no lo es.
    """
    with _lock:
        conn = _connect()
        filas = conn.execute(
            "SELECT id FROM soc_event WHERE turn_id=? AND accion IN ('BLOCK','SUSPICIOUS')",
            (turn_id,),
        ).fetchall()
        creadas = 0
        for fila in filas:
            conn.execute(
                """
                INSERT OR IGNORE INTO soc_alert (turn_id, event_id, ts, severidad, severidad_origen)
                VALUES (?,?,?,?,?)
                """,
                (turn_id, fila["id"], _now(), severidad, severidad_origen),
            )
            creadas += 1
        conn.commit()
    return creadas


def update_alert(alert_id: int, *, estado: Optional[str] = None, nota: Optional[str] = None) -> bool:
    campos, valores = [], []
    if estado is not None:
        campos.append("estado=?")
        valores.append(estado)
    if nota is not None:
        campos.append("nota=?")
        valores.append(nota)
    if not campos:
        return False
    campos.append("ts_actualizada=?")
    valores.extend([_now(), alert_id])
    with _lock:
        conn = _connect()
        cur = conn.execute(f"UPDATE soc_alert SET {', '.join(campos)} WHERE id=?", valores)
        conn.commit()
    return cur.rowcount > 0


def delete_run(run_id: str) -> int:
    with _lock:
        conn = _connect()
        cur = conn.execute("DELETE FROM soc_turn WHERE run_id=?", (run_id,))
        conn.commit()
    return cur.rowcount


# --- Lectura ---------------------------------------------------------------------

def _fila_turno(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["vulnerable"] = bool(d["vulnerable"])
    d["bloqueado"] = bool(d["bloqueado"])
    return d


def _fila_evento(r: sqlite3.Row) -> dict:
    d = dict(r)
    if d.get("detalle"):
        try:
            d["detalle"] = json.loads(d["detalle"])
        except json.JSONDecodeError:
            pass
    return d


_FILTROS = {
    "endpoint": "t.endpoint=?",
    "origen": "t.origen=?",
    "run_id": "t.run_id=?",
    "session_id": "t.session_id=?",
    "user_id": "t.user_id=?",
    "categoria": "t.categoria=?",
    "fixture_id": "t.fixture_id=?",
}


def list_turns(
    *,
    since: Optional[int] = None,
    before: Optional[int] = None,
    limit: int = 50,
    componente: Optional[str] = None,
    accion: Optional[str] = None,
    texto: Optional[str] = None,
    **filtros,
) -> list[dict]:
    """Turnos ordenados de más reciente a más antiguo, con sus eventos incrustados.

    `since` devuelve lo posterior a un cursor (polling incremental) y `before` pagina
    hacia atrás. Los filtros por componente o acción se resuelven con EXISTS para no
    duplicar turnos cuando varios eventos casan.
    """
    condiciones, valores = [], []
    for clave, sql in _FILTROS.items():
        valor = filtros.get(clave)
        if valor:
            condiciones.append(sql)
            valores.append(valor)
    if since is not None:
        condiciones.append("t.id > ?")
        valores.append(since)
    if before is not None:
        condiciones.append("t.id < ?")
        valores.append(before)
    if componente or accion:
        sub, subval = ["e.turn_id = t.id"], []
        if componente:
            sub.append("e.componente=?")
            subval.append(componente)
        if accion:
            sub.append("e.accion=?")
            subval.append(accion)
        condiciones.append(f"EXISTS (SELECT 1 FROM soc_event e WHERE {' AND '.join(sub)})")
        valores.extend(subval)
    if texto:
        condiciones.append("(t.prompt LIKE ? OR t.respuesta LIKE ?)")
        valores.extend([f"%{texto}%", f"%{texto}%"])

    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    with _lock:
        conn = _connect()
        filas = conn.execute(
            f"SELECT t.* FROM soc_turn t {where} ORDER BY t.id DESC LIMIT ?",
            (*valores, limit),
        ).fetchall()
        turnos = [_fila_turno(f) for f in filas]
        if turnos:
            ids = [t["id"] for t in turnos]
            marcas = ",".join("?" * len(ids))
            eventos = conn.execute(
                f"SELECT * FROM soc_event WHERE turn_id IN ({marcas}) ORDER BY turn_id, orden",
                ids,
            ).fetchall()
            por_turno: dict[int, list] = {i: [] for i in ids}
            for e in eventos:
                por_turno[e["turn_id"]].append(_fila_evento(e))
            for t in turnos:
                t["eventos"] = por_turno[t["id"]]
    return turnos


def get_turn(turn_id: int) -> Optional[dict]:
    with _lock:
        conn = _connect()
        fila = conn.execute("SELECT * FROM soc_turn WHERE id=?", (turn_id,)).fetchone()
        if fila is None:
            return None
        turno = _fila_turno(fila)
        turno["eventos"] = [
            _fila_evento(e)
            for e in conn.execute(
                "SELECT * FROM soc_event WHERE turn_id=? ORDER BY orden", (turn_id,)
            )
        ]
        turno["alertas"] = [
            dict(a)
            for a in conn.execute("SELECT * FROM soc_alert WHERE turn_id=?", (turn_id,))
        ]
    return turno


def get_session(session_id: str) -> list[dict]:
    """Todos los turnos de una sesión en orden cronológico ascendente."""
    with _lock:
        conn = _connect()
        filas = conn.execute(
            "SELECT * FROM soc_turn WHERE session_id=? ORDER BY id ASC", (session_id,)
        ).fetchall()
        turnos = [_fila_turno(f) for f in filas]
        for t in turnos:
            t["eventos"] = [
                _fila_evento(e)
                for e in conn.execute(
                    "SELECT * FROM soc_event WHERE turn_id=? ORDER BY orden", (t["id"],)
                )
            ]
    return turnos


def related_sessions(session_id: str, limit: int = 12) -> dict[str, list[dict]]:
    """Con qué se relaciona una sesión: mismo usuario, mismo fixture, misma taxonomía.

    No es una correlación estadística ni una inferencia: son coincidencias exactas
    sobre campos ya capturados. El SOC no infiere parecidos, los enumera.
    """
    with _lock:
        conn = _connect()
        base = conn.execute(
            """SELECT user_id, fixture_id, categoria, subcategoria
               FROM soc_turn WHERE session_id=? LIMIT 1""",
            (session_id,),
        ).fetchone()
        if base is None:
            return {"mismo_usuario": [], "mismo_fixture": [], "misma_taxonomia": []}

        def _buscar(sql: str, args: tuple) -> list[dict]:
            return [
                dict(r)
                for r in conn.execute(
                    f"""SELECT session_id, MIN(ts) AS ts, COUNT(*) AS turnos,
                               SUM(bloqueado) AS bloqueados, fixture_id, endpoint
                        FROM soc_turn
                        WHERE session_id != ? AND {sql}
                        GROUP BY session_id ORDER BY ts DESC LIMIT ?""",
                    (session_id, *args, limit),
                )
            ]

        resultado = {
            "mismo_usuario": _buscar("user_id=?", (base["user_id"],)),
            "mismo_fixture": (
                _buscar("fixture_id=?", (base["fixture_id"],)) if base["fixture_id"] else []
            ),
            "misma_taxonomia": (
                _buscar(
                    "categoria=? AND subcategoria=? AND (fixture_id IS NULL OR fixture_id != ?)",
                    (base["categoria"], base["subcategoria"], base["fixture_id"] or ""),
                )
                if base["categoria"] else []
            ),
        }
    return resultado


def component_activity(**filtros) -> list[dict]:
    """Actividad por componente: recuento por acción y latencia mediana."""
    condiciones, valores = [], []
    for clave, sql in _FILTROS.items():
        if filtros.get(clave):
            condiciones.append(sql)
            valores.append(filtros[clave])
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    with _lock:
        conn = _connect()
        filas = conn.execute(
            f"""SELECT e.componente, e.accion, COUNT(*) AS n, AVG(e.latencia_ms) AS lat_media
                FROM soc_event e JOIN soc_turn t ON t.id = e.turn_id
                {where}
                GROUP BY e.componente, e.accion""",
            valores,
        ).fetchall()

    por_componente: dict[str, dict] = {}
    for f in filas:
        comp = por_componente.setdefault(
            f["componente"],
            {"componente": f["componente"], "ALLOW": 0, "SUSPICIOUS": 0, "BLOCK": 0,
             "total": 0, "latencia_media_ms": None, "_lat_suma": 0.0, "_lat_n": 0},
        )
        comp[f["accion"]] = f["n"]
        comp["total"] += f["n"]
        if f["lat_media"] is not None:
            comp["_lat_suma"] += f["lat_media"] * f["n"]
            comp["_lat_n"] += f["n"]

    # `latencia_media_ms` se queda en None cuando NINGÚN evento traía medición, y el panel
    # lo pinta como "—". Devolver 0.0 haría pasar "no se midió" por "tardó cero", que son
    # cosas distintas y la segunda es mentira.
    for comp in por_componente.values():
        n = comp.pop("_lat_n")
        suma = comp.pop("_lat_suma")
        comp["latencia_media_ms"] = round(suma / n, 3) if n else None
    return list(por_componente.values())


def taxonomy_activity() -> list[dict]:
    with _lock:
        conn = _connect()
        filas = conn.execute(
            """SELECT categoria, subcategoria, COUNT(*) AS turnos, SUM(bloqueado) AS bloqueados
               FROM soc_turn WHERE categoria IS NOT NULL
               GROUP BY categoria, subcategoria ORDER BY categoria, subcategoria"""
        ).fetchall()
    return [dict(f) for f in filas]


def list_runs() -> list[dict]:
    with _lock:
        conn = _connect()
        filas = conn.execute(
            """SELECT run_id, origen, MIN(ts) AS inicio, MAX(ts) AS fin,
                      COUNT(*) AS turnos, SUM(bloqueado) AS bloqueados,
                      SUM(vulnerable) AS vulnerables,
                      COUNT(DISTINCT session_id) AS sesiones
               FROM soc_turn WHERE run_id IS NOT NULL
               GROUP BY run_id ORDER BY inicio DESC"""
        ).fetchall()
    return [dict(f) for f in filas]


def list_alerts(estado: Optional[str] = None, limit: int = 100) -> list[dict]:
    where, valores = ("WHERE a.estado=?", [estado]) if estado else ("", [])
    with _lock:
        conn = _connect()
        filas = conn.execute(
            f"""SELECT a.*, e.componente, e.accion, e.razon, e.regla,
                       t.session_id, t.endpoint, t.fixture_id, t.categoria, t.subcategoria,
                       substr(t.prompt, 1, 240) AS prompt_extracto
                FROM soc_alert a
                JOIN soc_event e ON e.id = a.event_id
                JOIN soc_turn  t ON t.id = a.turn_id
                {where} ORDER BY a.id DESC LIMIT ?""",
            (*valores, limit),
        ).fetchall()
    return [dict(f) for f in filas]


def totals() -> dict:
    with _lock:
        conn = _connect()
        t = conn.execute(
            """SELECT COUNT(*) AS turnos, SUM(bloqueado) AS bloqueados,
                      SUM(vulnerable) AS vulnerables, AVG(latencia_total_ms) AS lat_media,
                      COUNT(DISTINCT session_id) AS sesiones, MAX(id) AS cursor
               FROM soc_turn"""
        ).fetchone()
        eventos = conn.execute("SELECT COUNT(*) AS n FROM soc_event").fetchone()["n"]
        alertas = conn.execute(
            "SELECT estado, COUNT(*) AS n FROM soc_alert GROUP BY estado"
        ).fetchall()
    return {
        "turnos": t["turnos"] or 0,
        "bloqueados": t["bloqueados"] or 0,
        "vulnerables": t["vulnerables"] or 0,
        "sesiones": t["sesiones"] or 0,
        "eventos": eventos,
        "latencia_media_ms": round(t["lat_media"], 1) if t["lat_media"] else 0.0,
        "cursor": t["cursor"] or 0,
        "alertas": {a["estado"]: a["n"] for a in alertas},
    }
