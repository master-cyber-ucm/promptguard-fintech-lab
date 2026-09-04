#!/usr/bin/env python3
"""Ejecuta la suite completa de fixtures contra los endpoints de Clara.

Envía los fixtures al backend y persiste los Session Files en el Run Folder.
No calcula Verdicts ni invoca al juez — eso es responsabilidad del Analyze Pass.

  lab/audit/runs/{timestamp}_{model}/
  ├── simple-prompt/               ← Session Files de este endpoint
  ├── complex-prompt/
  ├── complex-with-context/
  ├── proxy-document-baseline/     ← fixtures `type: document-upload`, sin defensas
  ├── proxy-document-full/         ← mismos fixtures, pipeline documental completo
  └── (run.md y run.json los genera `evaluate.py` + `report.py` después)

Fixtures `type: document-upload` (campo `document: <archivo>` apuntando a
henri-tfm/01-ataque/payloads/) se envían SIEMPRE a `proxy-document-baseline`/
`proxy-document-full` vía multipart contra `/chat/proxy` (PR7/ADR-0018: el
documento es un campo opcional de los 4 endpoints existentes, no una ruta
propia — `/chat/complex-with-document` queda deprecado). Un fixture documental
solo es aplicable a esos dos targets (P10 en `capabilities.py`): compararlo
contra un chat sin documentos mediría la diferencia entre canales, no la
eficacia de la defensa. `--document-profile document-baseline` apaga las
capas del canal (Document Sanitizer, detector estructural) y el resto del
pipeline (`proxy_profile=baseline`); `document-full` las activa todas.

Uso:
  python run_attack_suite.py                           # todos los endpoints y kinds
  python run_attack_suite.py --endpoint simple-prompt  # solo un endpoint
  python run_attack_suite.py --endpoint proxy --document-profile document-baseline \
      --document-profile document-full                  # solo el canal documental
  python run_attack_suite.py --kind attack-prompts     # solo ataques
  python run_attack_suite.py --type INDIRECT_INJECTION
  python run_attack_suite.py --id atk_035
  python run_attack_suite.py --id atk_001_admin --id leg_024 --endpoint complex-with-context --endpoint proxy
  python run_attack_suite.py --repeat 5                # 5 repeticiones por fixture
  python run_attack_suite.py --proxy-profile baseline --proxy-profile gatekeeper \\
      --proxy-profile output --proxy-profile full --repeat 5
  python run_attack_suite.py --user usr_002
  python run_attack_suite.py --seed 42            # otro orden de bloques, reproducible

Diseño de ejecución: la matriz completa se calcula antes de enviar nada y se recorre en
bloques (fixture, repetición) con las posturas intercaladas en orden derivado de
`--seed`. Ejecutar un target entero y luego el siguiente confundiría la deriva temporal
del proveedor con la eficacia de esa postura.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import random
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab_paths import display_path, ensure_src_importable  # noqa: E402

ensure_src_importable()
from fixture_loader import load_prompts
from src.api.auth import issue_token
from src.models.posture import TargetPosture
from src.models.capabilities import audit_coverage, decide
from src.models.coverage import CoverageGates
from evaluations.semantic_judge import judge_bundle
from execution_errors import ExecutionError, from_backend, from_exception
import provenance

RUNS_DIR = HERE.parent / "audit" / "runs"
# henri-tfm/ vive fuera de lab/ — HERE = lab/scripts, .parent.parent = raíz del repo.
# En local se resuelve desde la raíz del repositorio; Docker aporta la misma
# carpeta de payloads en una ruta explícita y de solo lectura.
PAYLOADS_DIR = Path(
    os.environ.get(
        "PAYLOADS_DIR",
        str(HERE.parent.parent / "henri-tfm" / "01-ataque" / "payloads"),
    )
)
# Algunos Turns llaman varias tools y cada llamada puede consumir la salida máxima
# del modelo. 90 s bastaba para una respuesta simple, pero no para esos casos y
# dejaba el trabajo del backend vivo sin que el runner esperase su Session File.
# El límite sigue siendo configurable para entornos donde se prefiera fallar antes.
REQUEST_TIMEOUT = float(os.environ.get("SUITE_REQUEST_TIMEOUT", "300"))

# El backend corre en un contenedor con ./audit:/app/audit montado (lab/docker-compose.yml).
# `audit_subdir` viaja en la petición y lo usa `append_turn()` DENTRO del contenedor — tiene que
# ser la ruta tal como la ve el contenedor, no la ruta host de este script. Bug real encontrado
# en Fase 2.9: antes se enviaba la ruta host (`str(run_folder / ep_name)`); el contenedor la creaba
# igualmente sin fallar, pero en su propio filesystem efímero — invisible y no persistente desde
# el host. Mismo bug (y mismo arreglo) que ya se había aplicado en
# henri-tfm/01-ataque/evidencia/ejecutar_evidencia.py.
AUDIT_RUNS_DIR_CONTAINER = "/app/audit/runs"

ALL_KINDS = ["attack-prompts", "legitimate-prompts", "navi-prompts"]

CHAT_ENDPOINTS: dict[str, str] = {
    "simple-prompt":        "/api/v1/chat/simple-prompt",
    "complex-prompt":       "/api/v1/chat/complex-prompt",
    "complex-with-context": "/api/v1/chat/complex-with-context",
    # El pipeline completo de defensa. Sin él no hay forma de producir una corrida
    # "defendida" que comparar contra las líneas base, que es lo que la pantalla de
    # Corridas del SOC pone una al lado de la otra.
    "proxy": "/api/v1/chat/proxy",
    # `/chat/complex-with-document` quedó deprecado en PR7 (ADR-0018): el documento
    # pasó a ser un campo `multipart/form-data` opcional de los cuatro endpoints de
    # arriba, no una ruta propia. El canal documental sigue viviendo aquí como
    # `--document-profile` sobre `proxy` (ver más abajo) — PR10/P10.
}

#: Matriz de ablaciones (PR5 / ADR-0017): "only-*" añade la del catálogo de perfiles
#: del backend con un control a la vez, con `vulnerable=False` en todos (a diferencia
#: de "baseline"), así que son comparables entre sí en los cinco flags declarados.
PROXY_PROFILES = (
    "baseline", "gatekeeper", "output", "full",
    "only-input", "only-pii", "only-gatekeeper", "only-auditor", "only-leak",
)

#: Posturas del canal DOCUMENTAL. Un fixture documental solo es comparable contra otra
#: postura del mismo pipeline documental: enfrentarlo a un chat sin documentos mediría
#: la diferencia entre dos canales, no la eficacia de la defensa (P10).
DOCUMENT_PROFILES = ("document-baseline", "document-full")

#: `document-baseline`/`document-full` (nombre del target, comparable con
#: `proxy-baseline`/`proxy-full`) frente a `baseline`/`full` (nombre que espera
#: `proxy_profile` en el servidor). Desde PR7/ADR-0018 el documento es un campo
#: opcional de `/chat/proxy`: un único `proxy_profile` gatea a la vez Input
#: Sanitizer/PII Shield/Tool Gatekeeper/Output Auditor/Leak Guard Y Document
#: Sanitizer/detector estructural (`documento_activo = not request.vulnerable`,
#: derivado del mismo perfil) — ya no hay flags `defensa_*` propios que enviar.
DOCUMENT_PROXY_PROFILE = {name: name.removeprefix("document-") for name in DOCUMENT_PROFILES}

#: Postura SOLICITADA por target. El backend devuelve la efectiva y el runner las
#: compara: una divergencia es un error de instrumentación que invalida el experimento,
#: no un resultado del que se pueda informar (P02).
REQUESTED_CONTROLS: dict[str, dict[str, bool]] = {
    "baseline": {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
                 "output_auditor": False, "leak_guard": False},
    "gatekeeper": {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": True,
                   "output_auditor": False, "leak_guard": False},
    "output": {"input_sanitizer": False, "pii_shield": True, "tool_gatekeeper": True,
               "output_auditor": True, "leak_guard": True},
    "full": {"input_sanitizer": True, "pii_shield": True, "tool_gatekeeper": True,
             "output_auditor": True, "leak_guard": True},
    "only-input": {"input_sanitizer": True, "pii_shield": False, "tool_gatekeeper": False,
                   "output_auditor": False, "leak_guard": False},
    "only-pii": {"input_sanitizer": False, "pii_shield": True, "tool_gatekeeper": False,
                 "output_auditor": False, "leak_guard": False},
    "only-gatekeeper": {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": True,
                        "output_auditor": False, "leak_guard": False},
    "only-auditor": {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": False,
                     "output_auditor": True, "leak_guard": False},
    # `leak_guard` depende de `tool_gatekeeper` en el pipeline (ablación condicionada,
    # no independiente — ver ADR-0017).
    "only-leak": {"input_sanitizer": False, "pii_shield": False, "tool_gatekeeper": True,
                 "output_auditor": False, "leak_guard": True},
}

#: Los endpoints pedagógicos no llevan ningún control externo. Se declara para poder
#: detectar si el backend aplicara alguno por herencia, que es exactamente lo que
#: ocurría con el Output Auditor antes de P02.
PEDAGOGICAL_REQUESTED = {name: False for name in REQUESTED_CONTROLS["baseline"]}


def requested_posture(target: str, profile: str | None) -> dict[str, bool]:
    if profile:
        return dict(REQUESTED_CONTROLS[profile])
    if target == "proxy":
        return dict(REQUESTED_CONTROLS["full"])
    return dict(PEDAGOGICAL_REQUESTED)

DOCUMENT_CONTENT_TYPES: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


# ---------------------------------------------------------------------------
# Single fixture execution
# ---------------------------------------------------------------------------

def auth_headers(user_id: str) -> dict[str, str]:
    """Credencial firmada del sujeto. La suite tampoco elige identidad desde el body.

    Sin esto, un experimento que mide autorización estaría midiendo un backend que
    acepta cualquier `user_id` — y sus resultados de seguridad serían optimistas por
    construcción (P16).
    """
    return {"Authorization": f"Bearer {issue_token(user_id)}"}


async def _run_document_execution(
    client: httpx.AsyncClient,
    execution: dict,
    user_id: str,
    api_base: str,
    endpoint_path: str,
) -> dict:
    """Ejecuta una repetición de un fixture `type: document-upload` vía multipart."""
    fixture = execution["fixture"]
    doc_path = PAYLOADS_DIR / fixture["document"]
    started_at = time.time()
    if not doc_path.is_file():
        return _attempt(execution, started_at, error=f"Documento no encontrado: {doc_path}")

    content_type = DOCUMENT_CONTENT_TYPES.get(doc_path.suffix.lower(), "application/octet-stream")
    # Una repetición debe producir evidencia independiente; un id único evita que las
    # repeticiones se agreguen en un único Session File documental.
    session_id = f"suite_{fixture['id']}_{int(time.time() * 1000)}_{execution['repetition']}"
    try:
        with open(doc_path, "rb") as f:
            resp = await client.post(
                f"{api_base}{endpoint_path}",
                data={
                    "user_id": user_id,
                    "session_id": session_id,
                    "message": fixture.get("message", ""),
                    "fixture_id": fixture.get("id"),
                    "fixture_kind": fixture.get("kind"),
                    "fixture_expected_result": fixture.get("expected_result"),
                    "fixture_execution_id": execution["fixture_execution_id"],
                    "audit_subdir": execution["audit_subdir"],
                    # `/chat/proxy` deriva `vulnerable` (y con él, si el documento pasa
                    # por Document Sanitizer/detector estructural) del propio
                    # `proxy_profile` — un solo campo gatea texto y documento a la vez.
                    "proxy_profile": execution.get("proxy_profile") or "full",
                },
                files={"document": (doc_path.name, f, content_type)},
                headers=auth_headers(user_id),
                timeout=REQUEST_TIMEOUT,
            )
        data = resp.json()
    except Exception as exc:
        fallo = from_exception(exc)
        return _attempt(execution, started_at, error=fallo.message, session_id=session_id,
                        execution_status="TECHNICAL_ERROR", failure=fallo)
    error = data.get("error") or None
    return _attempt(
        execution, started_at, session_id=session_id,
        response=data.get("response", ""), error=error,
        effective_posture=data.get("effective_posture"),
        execution_status=data.get("execution_status", "COMPLETED"),
        failure=from_backend(error) if error else None,
    )


async def _run_chat_execution(
    client: httpx.AsyncClient,
    execution: dict,
    user_id: str,
    api_base: str,
    endpoint_path: str,
) -> dict:
    """Ejecuta una repetición de un fixture conversacional (uno o varios steps)."""
    fixture = execution["fixture"]
    # Cada repetición arranca una conversación nueva; dentro de la misma repetición los
    # pasos de un fixture multi-step SÍ comparten memoria real (session_store.py): el
    # primer step no manda session_id y los siguientes reutilizan el que devuelve la API.
    session_id: str | None = None
    last_response = ""
    error: str | None = None
    block_code: str | None = None
    effective_posture: dict | None = None
    execution_status = "COMPLETED"
    started_at = time.time()
    try:
        for step in fixture.get("rendered_steps", []):
            body = {
                "user_id": user_id,
                "message": step.get("content", ""),
                "fixture_id": fixture.get("id"),
                "fixture_kind": fixture.get("kind"),
                "fixture_expected_result": fixture.get("expected_result"),
                "fixture_execution_id": execution["fixture_execution_id"],
                "audit_subdir": execution["audit_subdir"],
            }
            if execution["proxy_profile"]:
                body["proxy_profile"] = execution["proxy_profile"]
            if session_id:
                body["session_id"] = session_id
            resp = await client.post(
                f"{api_base}{endpoint_path}", json=body,
                headers=auth_headers(user_id), timeout=REQUEST_TIMEOUT,
            )
            data = resp.json()
            last_response = data.get("response", "")
            error = data.get("error") or None
            block_code = data.get("block_code") or None
            effective_posture = data.get("effective_posture") or effective_posture
            execution_status = data.get("execution_status", execution_status)
            returned_id = data.get("session_id")
            if returned_id:
                session_id = returned_id
        fallo = from_backend(error) if error else None
    except Exception as exc:
        fallo = from_exception(exc)
        error = fallo.message
        execution_status = "TECHNICAL_ERROR"
    if error and execution_status == "COMPLETED":
        execution_status = "TECHNICAL_ERROR"
    return _attempt(
        execution, started_at, session_id=session_id or "", response=last_response,
        error=error, block_code=block_code, effective_posture=effective_posture,
        execution_status=execution_status, failure=fallo,
    )


def _attempt(
    execution: dict,
    started_at: float,
    *,
    session_id: str = "",
    response: str = "",
    error: str | None = None,
    block_code: str | None = None,
    effective_posture: dict | None = None,
    execution_status: str = "COMPLETED",
    failure: ExecutionError | None = None,
) -> dict:
    """Resultado de una Fixture Execution, con su postura verificada.

    La postura EFECTIVA la devuelve el backend. Compararla con la solicitada es lo que
    convierte «creo que corrí sin defensas» en una afirmación verificable: una
    divergencia invalida la comparación causal en vez de colarse como resultado.
    """
    posture = TargetPosture(
        target=execution["target"],
        requested=execution["requested_posture"],
        effective=effective_posture or {},
    )
    divergences = posture.divergences() if effective_posture else ["postura efectiva no reportada"]
    return {
        "fixture_execution_id": execution["fixture_execution_id"],
        "fixture_id": execution["fixture"].get("id"),
        "target": execution["target"],
        "repetition": execution["repetition"],
        "latency_ms": round((time.time() - started_at) * 1000, 1),
        "response_preview": response[:120].replace("\n", " "),
        "error": error,
        "block_code": block_code,
        "session_id": session_id,
        "execution_status": execution_status,
        # El error se clasifica por fase y se sanea: el registro de fallos no puede
        # convertirse en una segunda vía de exposición del prompt o de un IBAN.
        "failure": failure.to_dict() if failure else None,
        "posture": posture.to_dict(),
        "posture_divergences": divergences,
        "attempt_no": execution.get("attempt_no", 1),
        "retry_of": execution.get("retry_of"),
    }


async def run_execution(
    client: httpx.AsyncClient, execution: dict, user_id: str, api_base: str,
) -> dict:
    endpoint_path = execution["endpoint_path"]
    if execution["fixture"].get("document"):
        return await _run_document_execution(client, execution, user_id, api_base, endpoint_path)
    return await _run_chat_execution(client, execution, user_id, api_base, endpoint_path)


# ---------------------------------------------------------------------------
# Diseño de ejecución
# ---------------------------------------------------------------------------

def build_executions(
    fixtures: list[dict],
    endpoints: dict[str, str],
    proxy_profile_by_target: dict[str, str | None],
    *,
    repeat: int,
    run_folder_name: str,
    document_profile_by_target: dict[str, str | None] | None = None,
) -> list[dict]:
    """Matriz completa de Fixture Executions, calculada ANTES de enviar tráfico.

    Cada ejecución nace con su `fixture_execution_id`: la evidencia se correlaciona por
    ese identificador y no por la ruta del Session File.
    """
    document_profile_by_target = document_profile_by_target or {}
    executions: list[dict] = []
    for fixture in fixtures:
        for target in applicable_targets(fixture, endpoints):
            profile = proxy_profile_by_target.get(target)
            for repetition in range(1, repeat + 1):
                executions.append({
                    "fixture_execution_id": str(uuid.uuid4()),
                    "fixture": fixture,
                    "fixture_id": fixture.get("id"),
                    "target": target,
                    "endpoint_path": endpoints[target],
                    "proxy_profile": profile,
                    "repetition": repetition,
                    "document_profile": document_profile_by_target.get(target),
                    "requested_posture": requested_posture(
                        "proxy" if target.startswith("proxy") else target, profile
                    ),
                    "audit_subdir": f"{AUDIT_RUNS_DIR_CONTAINER}/{run_folder_name}/{target}",
                })
    return executions


def applicable_targets(fixture: dict, endpoints: dict[str, str]) -> list[str]:
    """Targets en los que este fixture mide algo real.

    La decisión se toma por CAPACIDADES, no por nombre de ruta (P10): un fixture
    documental solo es aplicable donde hay subida de documentos, y renombrar un
    endpoint no cambia lo que mide. `applicable_endpoints` se conserva encima como
    exclusión declarada por el propio fixture — p. ej. System Prompt Leakage contra
    `simple-prompt`, que no tiene sección interna que filtrar: contarlo como bloqueo
    sería un artefacto de medición.
    """
    declarados = fixture.get("applicable_endpoints")
    targets = []
    for name in endpoints:
        if not decide(fixture, name).in_population:
            continue
        canonical = "proxy" if name.startswith("proxy") else name
        if declarados and canonical not in declarados and not fixture.get("document"):
            continue
        targets.append(name)
    return targets


def plan_rows(executions: list[dict], *, run_folder_name: str) -> list[dict]:
    """Filas del Plan de cobertura: el denominador del run, fijado antes de ejecutar.

    Se sella ANTES de enviar tráfico a propósito. Reconstruir la matriz a partir de los
    Session Files encontrados hace desaparecer del denominador justo lo que peor salió:
    lo que falló, lo que no llegó a lanzarse y lo que no dejó evidencia.
    """
    return [
        {
            "fixture_execution_id": execution["fixture_execution_id"],
            "run": run_folder_name,
            "fixture_id": execution["fixture_id"],
            "fixture_kind": execution["fixture"].get("kind"),
            "attack": execution["fixture"].get("attack"),
            "category": execution["fixture"].get("category"),
            "severity": execution["fixture"].get("severity"),
            "expected_result": execution["fixture"].get("expected_result"),
            "target": execution["target"],
            "proxy_profile": execution["proxy_profile"],
            "repetition": execution["repetition"],
            "requested_posture": execution["requested_posture"],
            "audit_subdir": execution["audit_subdir"],
            "applicable": True,
            "turns_expected": (
                1 if execution["fixture"].get("document")
                else len(execution["fixture"].get("rendered_steps", []))
            ),
        }
        for execution in executions
    ]


class ExecutionLedger:
    """Registro append-only de qué pasó con cada ejecución planificada.

    Cada línea se vuelca inmediatamente: una corrida interrumpida conserva lo que ya
    había ocurrido en vez de perderlo entero. `PLANNED`, `DISPATCHED` y `FINISHED` son
    lo que después permite afirmar que ninguna ejecución desapareció en silencio.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file = path.open("a", encoding="utf-8")

    def record(self, event: str, execution: dict, **extra) -> None:
        linea = {
            "event": event,
            "ts": datetime.now(timezone.utc).isoformat(),
            "fixture_execution_id": execution["fixture_execution_id"],
            "fixture_id": execution["fixture_id"],
            "target": execution["target"],
            "repetition": execution["repetition"],
            **extra,
        }
        self._file.write(json.dumps(linea, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def order_in_blocks(executions: list[dict], *, seed: int) -> list[dict]:
    """Diseño de bloques aleatorizados: un bloque por (fixture, repetición).

    Ejecutar todos los fixtures de un target y luego los del siguiente confunde la
    eficacia de una postura con la deriva temporal del proveedor (carga, caché,
    calentamiento). Intercalando las posturas dentro del mismo bloque, esa deriva afecta
    por igual a las dos ramas de la comparación. El orden se deriva de una semilla
    registrada en el manifiesto, así que la corrida sigue siendo reproducible.
    """
    rng = random.Random(seed)
    bloques: dict[tuple, list[dict]] = {}
    for execution in executions:
        bloques.setdefault((execution["fixture_id"], execution["repetition"]), []).append(execution)

    ordenadas: list[dict] = []
    for clave in sorted(bloques, key=lambda k: (str(k[0]), k[1])):
        bloque = list(bloques[clave])
        rng.shuffle(bloque)
        ordenadas.extend(bloque)
    return ordenadas


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SEP  = "─" * 70
SEP2 = "═" * 70


def _flush(text: str) -> None:
    print(text, flush=True)


def _attempt_outcome(attempt: dict) -> str:
    """Clasifica un intento sin confundir un bloqueo esperado con un fallo técnico."""
    if attempt.get("block_code"):
        return "blocked"
    error = attempt.get("error") or ""
    if not error:
        return "ok"
    if error.startswith("BLOCKED_BY_"):
        return "blocked"
    return "error"


#: Reintentos trazables y presupuestados (PR6). Solo fases transitorias
#: (`execution_errors.RETRYABLE_PHASES`: CONNECT/MODEL/BACKEND) se reintentan, y
#: siempre a nivel de la MISMA Fixture Execution — nunca se crea un
#: `fixture_execution_id` nuevo. Una denegación, un fallo de validación determinista
#: o un efecto ambiguo no son transitorios y `failure.retryable` ya los excluye por
#: construcción (ver `execution_errors.py`). Post-PR2 ninguna escritura financiera se
#: compromete de forma síncrona dentro de un turno de chat — como mucho un reintento
#: crea una propuesta nueva que expira sin autorizar — así que reintentar un turno no
#: puede duplicar un efecto de dominio.
MAX_RETRY_ATTEMPTS = int(os.environ.get("SUITE_MAX_RETRIES", "2"))
RETRY_BACKOFF_BASE_SECONDS = float(os.environ.get("SUITE_RETRY_BACKOFF", "2.0"))


def _should_retry(attempt_no: int, resultado: dict) -> bool:
    """Decisión pura de reintento — separada de la espera/E/S para poder testearla."""
    if attempt_no > MAX_RETRY_ATTEMPTS:
        return False
    if _attempt_outcome(resultado) != "error":
        return False
    return bool((resultado.get("failure") or {}).get("retryable"))


async def run_execution_with_retries(
    client: httpx.AsyncClient, execution: dict, user_id: str, api_base: str,
    *, ledger: "ExecutionLedger | None" = None,
) -> dict:
    """Reintenta la MISMA Fixture Execution ante un fallo transitorio.

    Cada intento queda en `resultado["attempts"]` (fase, si era reintentable) y, si se
    pasa `ledger`, también como su propio evento `FINISHED` con `retry_of` apuntando al
    `fixture_execution_id` — es el contrato que `check_suite_run.py::check_execution`
    ya esperaba (`len(eventos) > 1` es válido solo si los adicionales declaran
    `retry_of`; más de un terminal SIN declararlo es `EXECUTION_DUPLICATE_TERMINAL`).
    El último intento decide `attempt_no`/resultado; el histórico completo es lo que
    permite reportar first-attempt vs. after-retry sin perder la observación de que
    el primero falló (un reintento con éxito mejora la disponibilidad, no la borra).
    """
    historial: list[dict] = []
    intento_no = 1
    while True:
        resultado = await run_execution(client, execution, user_id, api_base)
        resultado["attempt_no"] = intento_no
        es_reintento = intento_no > 1
        resultado["retry_of"] = execution["fixture_execution_id"] if es_reintento else None
        fallo = resultado.get("failure") or {}
        historial.append({
            "attempt_no": intento_no,
            "outcome": _attempt_outcome(resultado),
            "phase": fallo.get("phase"),
            "retryable": bool(fallo.get("retryable")),
        })
        if ledger is not None:
            ledger.record(
                "FINISHED", execution,
                execution_status=resultado["execution_status"],
                session_id=resultado["session_id"],
                error=resultado["error"],
                failure=resultado["failure"],
                posture_divergences=resultado["posture_divergences"],
                latency_ms=resultado["latency_ms"],
                attempt_no=intento_no,
                retry_of=resultado["retry_of"],
            )
        if not _should_retry(intento_no, resultado):
            break
        await asyncio.sleep(RETRY_BACKOFF_BASE_SECONDS * (2 ** (intento_no - 1)))
        intento_no += 1
    resultado["attempts"] = historial
    return resultado


def _repeat_log_summary(result: dict) -> str:
    """Resumen compacto y completo de todos los intentos de un endpoint."""
    attempts = result["attempts"]
    total = len(attempts)
    outcomes = Counter(_attempt_outcome(attempt) for attempt in attempts)
    latencies = [attempt["latency_ms"] for attempt in attempts]
    latency = f"{min(latencies):.0f}–{max(latencies):.0f}ms"
    parts = [f"✓ {outcomes['ok']}/{total}"]
    if outcomes["blocked"]:
        parts.append(f"BLOQUEADO {outcomes['blocked']}/{total}")
    if outcomes["error"]:
        parts.append(f"ERROR {outcomes['error']}/{total}")
    return " · ".join(parts) + f"  {latency}"


async def main():
    global REQUEST_TIMEOUT
    parser = argparse.ArgumentParser(description="PromptGuard suite runner")
    parser.add_argument("--kind", choices=ALL_KINDS, help="Ejecutar solo este kind")
    parser.add_argument("--type", dest="attack_type", help="Filtrar por attack_type")
    parser.add_argument(
        "--id", dest="fixture_ids", action="append", metavar="FIXTURE_ID",
        help="Ejecutar un fixture concreto; se puede repetir para una corrida curada",
    )
    parser.add_argument(
        "--proxy-profile",
        choices=PROXY_PROFILES,
        action="append",
        dest="proxy_profiles",
        metavar="PROFILE",
        help=(
            "Ejecuta el endpoint proxy con uno o varios perfiles experimentales. "
            "baseline=sin defensas; gatekeeper=autorización; output=gatekeeper+controles "
            "de salida; full=proxy completo. Sin este flag se conserva el proxy normal."
        ),
    )
    parser.add_argument(
        "--document-profile",
        choices=DOCUMENT_PROFILES,
        action="append",
        dest="document_profiles",
        metavar="PROFILE",
        help=(
            "Ejecuta el canal documental (fixtures con `document:`) contra `proxy` "
            "con una o varias posturas — requiere --endpoint proxy. "
            "document-baseline pide proxy_profile=baseline (documento y texto sin "
            "defensa); document-full pide proxy_profile=full (Document Sanitizer y "
            "detector estructural incluidos). Un fixture documental solo es "
            "comparable contra otra postura de ESTE pipeline, no contra un chat sin "
            "documentos."
        ),
    )
    parser.add_argument("--user", default="usr_001")
    parser.add_argument("--host", default=os.environ.get("SUITE_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("SUITE_PORT", "8000")))
    parser.add_argument(
        "--endpoint",
        choices=list(CHAT_ENDPOINTS),
        action="append",
        dest="endpoints",
        metavar="ENDPOINT",
        help=f"Endpoint(s) a usar (puede repetirse). Por defecto todos: {list(CHAT_ENDPOINTS)}",
    )
    parser.add_argument("--repeat", type=int, default=1, metavar="N",
                        help="Repetir cada fixture N veces (default: 1)")
    parser.add_argument(
        "--timeout", type=float, default=REQUEST_TIMEOUT, metavar="SEGUNDOS",
        help=(
            "Timeout por petición HTTP al backend (default: %(default)s). "
            "Auméntalo para fixtures que requieren varias tools."
        ),
    )
    parser.add_argument(
        "--resume-run", metavar="RUN_FOLDER",
        help=(
            "Reanudar una corrida en lab/audit/runs/<RUN_FOLDER>. Solo admite el "
            "nombre de carpeta; útil para completar combinaciones sin crear otro Run Folder."
        ),
    )
    parser.add_argument(
        "--seed", type=int, default=int(os.environ.get("SUITE_SEED", "20260831")),
        metavar="N",
        help=(
            "Semilla del diseño de bloques aleatorizados (default: %(default)s). Fija el "
            "orden en que se intercalan las posturas dentro de cada bloque "
            "(fixture, repetición); queda registrada en el manifiesto."
        ),
    )
    parser.add_argument(
        "--baseline-pure", action="store_true",
        help=(
            "OBSOLETO. Los endpoints pedagógicos ya corren sin ningún control externo y "
            "la línea base causal del proxy es --proxy-profile baseline. Se acepta un "
            "tiempo más y solo emite un aviso."
        ),
    )
    args = parser.parse_args()

    REQUEST_TIMEOUT = args.timeout

    if args.baseline_pure:
        print(
            "  ⚠ --baseline-pure es obsoleto y se ignora: los endpoints pedagógicos ya "
            "corren sin controles externos y la línea base causal es "
            "--proxy-profile baseline.",
            file=sys.stderr, flush=True,
        )

    api_base = f"http://{args.host}:{args.port}"

    endpoints: dict[str, str] = (
        {k: v for k, v in CHAT_ENDPOINTS.items() if k in args.endpoints}
        if args.endpoints
        else CHAT_ENDPOINTS
    )
    # La suite general conserva el directorio histórico `proxy`. Al pedir perfiles,
    # cada configuración recibe un directorio propio para que report.py no mezcle
    # resultados de posturas defensivas diferentes.
    proxy_profile_by_target: dict[str, str | None] = {name: None for name in endpoints}
    document_profile_by_target: dict[str, str | None] = {name: None for name in endpoints}
    # Documento y texto comparten la misma ruta física (`/chat/proxy`, PR7/ADR-0018) y
    # el mismo target de origen (`"proxy"`); lo que los separa es el nombre lógico que
    # cada bloque le da (`proxy-document-*` vs `proxy-*`), así que la comprobación de
    # que el usuario pidió `proxy` se hace una sola vez, antes de que cualquiera de los
    # dos bloques lo retire de `endpoints`.
    proxy_solicitado = "proxy" in endpoints
    if args.document_profiles:
        if not proxy_solicitado:
            parser.error("--document-profile requiere incluir --endpoint proxy (o no filtrar endpoints)")
        proxy_path = CHAT_ENDPOINTS["proxy"]
        endpoints.pop("proxy", None)
        document_profile_by_target.pop("proxy", None)
        proxy_profile_by_target.pop("proxy", None)
        for profile in dict.fromkeys(args.document_profiles):
            target = f"proxy-{profile}"
            endpoints[target] = proxy_path
            document_profile_by_target[target] = profile
            # `proxy_profile_by_target` es la fuente de `requested_posture()` y de
            # `execution["proxy_profile"]`: un target `proxy-document-baseline` debe
            # pedir el perfil real "baseline" en la petición, no `None` (que
            # `requested_posture` interpretaría como "full" — ver su rama sin
            # `profile` para `target == "proxy"`).
            proxy_profile_by_target[target] = DOCUMENT_PROXY_PROFILE[profile]
    if args.proxy_profiles:
        if not proxy_solicitado:
            parser.error("--proxy-profile requiere incluir --endpoint proxy (o no filtrar endpoints)")
        proxy_path = CHAT_ENDPOINTS["proxy"]
        endpoints.pop("proxy", None)
        proxy_profile_by_target.pop("proxy", None)
        for profile in dict.fromkeys(args.proxy_profiles):
            target = f"proxy-{profile}"
            endpoints[target] = proxy_path
            proxy_profile_by_target[target] = profile

    kinds = [args.kind] if args.kind else ALL_KINDS
    fixtures: list[dict] = []
    fixture_ids = args.fixture_ids or [None]
    for fixture_id in fixture_ids:
        for k in kinds:
            fixtures.extend(
                load_prompts(kind=k, attack_type=args.attack_type, prompt_id=fixture_id)
            )

    if not fixtures:
        print("No se encontraron fixtures con los filtros indicados.", file=sys.stderr)
        sys.exit(1)

    # Fetch model info
    model_info: dict = {}
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{api_base}/api/v1/health/llm", timeout=5.0)
            d = r.json()
            model_info = {"provider": d.get("provider"), "model": d.get("configured_model")}
        except Exception:
            model_info = {"provider": "unknown", "model": "unknown"}

    run_ts    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    model_slug = (model_info.get("model") or "unknown").replace(":", "-").replace("/", "-")
    if args.resume_run:
        resume_path = Path(args.resume_run)
        if resume_path.name != args.resume_run or args.resume_run in {".", ".."}:
            parser.error("--resume-run debe ser solo el nombre de un Run Folder")
        ts_file = args.resume_run
    else:
        ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + f"_{model_slug}"
    run_folder = RUNS_DIR / ts_file

    # Create run folder and endpoint/profile subdirs
    for ep_name in endpoints:
        (run_folder / ep_name).mkdir(parents=True, exist_ok=True)

    # La matriz completa se calcula ANTES de enviar nada: es el denominador del run y
    # la fuente del `fixture_execution_id` de cada ejecución.
    executions = build_executions(
        fixtures, endpoints, proxy_profile_by_target,
        repeat=args.repeat, run_folder_name=ts_file,
        document_profile_by_target=document_profile_by_target,
    )

    # Cobertura cero: un fixture cargado que ningún target puede ejecutar no genera ni
    # un hueco que reclamar. Se declara antes de empezar, no se descubre en el informe.
    # PR4: la decisión completa (`auditoria.to_dict()`, APPLICABLE/NOT_APPLICABLE con
    # reason code por fixture × target) ya se persiste dentro de `coverage-plan.json`
    # bajo la clave `applicability` (ver más abajo, al sellar el plan) — no hace falta
    # un fichero aparte; solo los huérfanos se destacan aquí por consola.
    auditoria = audit_coverage(fixtures, list(endpoints))
    if auditoria.orphans:
        _flush("")
        _flush("  ⚠ FIXTURES SIN NINGÚN TARGET APLICABLE (cobertura cero):")
        for fixture_id in auditoria.orphans:
            _flush(f"      · {fixture_id}")
        _flush(
            "    Ningún claim sobre su familia puede sostenerse con esta matriz. "
            "Añade un target compatible o decláralos fuera de alcance con razón."
        )
    ordered = order_in_blocks(executions, seed=args.seed)

    # Una ejecución es una combinación fixture-target-repetición. No equivale siempre a
    # una petición HTTP: los fixtures multi-turn envían un turno por cada step.
    total = len(executions)
    requests_total = sum(
        1 if e["fixture"].get("document") else len(e["fixture"].get("rendered_steps", []))
        for e in executions
    )

    # Marcador legible por máquina, ligado al run_id (PR3): el log de shell donde se
    # redirija esta salida es append-only y ajeno al código — puede acumular texto de
    # corridas o comandos previos. Sin un delimitador explícito, leer "el log" mezcla
    # colas de ejecuciones distintas bajo el mismo fichero (ver docs/reports/pr-03-*).
    _flush(f"=== RUN START run_id={ts_file} ts={run_ts} ===")
    _flush(SEP2)
    _flush(f"  🎯 PromptGuard Suite Run · {run_ts}")
    _flush(f"  Modelo    : {model_info.get('model')} ({model_info.get('provider')})")
    _flush(f"  Endpoints : {', '.join(endpoints)}")
    _flush(f"  Fixtures  : {len(fixtures)} · Ejecuciones totales: {total}")
    _flush(f"  Peticiones HTTP al backend: {requests_total}")
    if args.repeat > 1:
        _flush(f"  Repeticiones: {args.repeat}x por fixture")
    _flush(f"  Diseño    : bloques aleatorizados (fixture, repetición) · seed={args.seed}")
    if args.proxy_profiles:
        _flush(f"  Perfiles proxy: {', '.join(dict.fromkeys(args.proxy_profiles))}")
    _flush(f"  Run Folder: {display_path(run_folder)}")
    _flush(SEP2)

    # Procedencia: qué artefactos exactos produjeron estos números. Se genera antes de
    # abrir tráfico y no vuelve a tocarse (P14).
    manifiesto_procedencia = provenance.build(
        model_info, seed=args.seed, repeat=args.repeat, judge_bundle=judge_bundle(),
    )
    procedencia_path = run_folder / "provenance.json"
    if not (args.resume_run and procedencia_path.is_file()):
        procedencia_path.write_text(
            json.dumps(manifiesto_procedencia, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    if manifiesto_procedencia["git"]["dirty"]:
        _flush(
            "  ⚠ árbol de trabajo sucio: el commit no identifica el código que corre. "
            "Este run no puede agregarse con otros."
        )

    # Manifiesto versionado: describe la intención experimental, no etiquetas de
    # pipeline que puedan aparecer en sesiones bloqueadas antes de invocar al LLM.
    manifest_path = run_folder / "suite-config.json"
    # Una recuperación suele ejecutar un subconjunto de targets. El manifiesto
    # debe describir la campaña completa original, no ese subconjunto; de otro
    # modo check-suite dejaría de exigir evidencia de los restantes endpoints.
    if not (args.resume_run and manifest_path.is_file()):
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "run_started_at": run_ts,
                    # `model` se conserva durante una versión para lectores históricos.
                    "model": model_info.get("model"),
                    "requested_model": model_info.get("model"),
                    "provider": model_info.get("provider"),
                    # `defense_version` se conserva por compatibilidad; la identidad real
                    # del código está en provenance.json (commit + estado + digests).
                    "defense_version": os.environ.get("DEFENSE_VERSION", "dev"),
                    "git_commit": manifiesto_procedencia["git"]["commit"],
                    "git_dirty": manifiesto_procedencia["git"]["dirty"],
                    "fixtures_sha256": hashlib.sha256(
                        json.dumps(fixtures, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
                    ).hexdigest(),
                    "repeat": args.repeat,
                    "targets": list(endpoints),
                    "proxy_profiles": {
                        target: profile
                        for target, profile in proxy_profile_by_target.items()
                        if profile is not None
                    },
                    "seed": args.seed,
                    # Sin modelo, prompt y temperatura del juez registrados, un juicio
                    # semántico no puede reproducirse desde el Run Folder (P07).
                    "judge_bundle": judge_bundle(),
                    "provenance_fingerprint": provenance.fingerprint(manifiesto_procedencia),
                    "execution_design": "randomized_blocks(fixture, repetition)",
                    "requested_postures": {
                        target: requested_posture(
                            "proxy" if target.startswith("proxy") else target,
                            proxy_profile_by_target.get(target),
                        )
                        for target in endpoints
                    },
                    "pedagogical_targets": [
                        target for target in endpoints if not target.startswith("proxy")
                    ],
                    "fixture_count": len(fixtures),
                    "http_requests_expected": requests_total,
                },
                indent=2,
                ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    # El plan se sella antes de enviar nada y no vuelve a tocarse.
    plan_path = run_folder / "coverage-plan.json"
    if not (args.resume_run and plan_path.is_file()):
        plan_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run": ts_file,
                    "sealed_at": run_ts,
                    "seed": args.seed,
                    # Sin modelo, prompt y temperatura del juez registrados, un juicio
                    # semántico no puede reproducirse desde el Run Folder (P07).
                    "judge_bundle": judge_bundle(),
                    "provenance_fingerprint": provenance.fingerprint(manifiesto_procedencia),
                    "repeat": args.repeat,
                    "gates": CoverageGates().to_dict(),
                    "applicability": auditoria.to_dict(),
                    "rows": plan_rows(executions, run_folder_name=ts_file),
                },
                indent=2, ensure_ascii=False,
            ) + "\n",
            encoding="utf-8",
        )

    ledger = ExecutionLedger(run_folder / "execution-ledger.jsonl")
    for execution in ordered:
        ledger.record("PLANNED", execution, requested_posture=execution["requested_posture"])

    errors = 0
    blocked = 0
    sent   = 0
    # Desglose por fase (PR3): consola y Analyze Pass deben explicar los mismos
    # errores con la misma taxonomía (execution_errors.ErrorPhase), no solo un total
    # que un lector tenga que reconciliar a mano contra run.md.
    error_phases: Counter = Counter()
    # PR6: cuántas Fixture Executions necesitaron algún reintento y a cuántas les
    # resolvió el fallo transitorio — "first-attempt" es sent+blocked+errors con
    # retried=0; "after-retry" es el resultado final que ya se está contando arriba.
    retried = 0
    rescatados = 0
    divergencias: list[dict] = []
    resultados: list[dict] = []

    async with httpx.AsyncClient() as client:
        for idx, execution in enumerate(ordered, 1):
            fixture = execution["fixture"]
            etiqueta = (
                f"[{idx:>4}/{total}] {fixture.get('id')} · {execution['target']}"
                f" · rep {execution['repetition']}"
            )
            print(f"  {etiqueta:<70}", end="", flush=True)

            ledger.record("DISPATCHED", execution)
            # Cada intento (incluidos los reintentos) escribe su propio evento
            # FINISHED dentro de run_execution_with_retries — ver su docstring.
            attempt = await run_execution_with_retries(
                client, execution, args.user, api_base, ledger=ledger,
            )
            resultados.append(attempt)

            outcome = _attempt_outcome(attempt)
            sent += outcome == "ok"
            blocked += outcome == "blocked"
            errors += outcome == "error"
            if outcome == "error" and attempt.get("failure"):
                error_phases[attempt["failure"]["phase"]] += 1
            if len(attempt["attempts"]) > 1:
                retried += 1
                if outcome != "error":
                    rescatados += 1
            if attempt["posture_divergences"]:
                divergencias.append({
                    "fixture_execution_id": attempt["fixture_execution_id"],
                    "target": attempt["target"],
                    "divergences": attempt["posture_divergences"],
                })
            marca = {"ok": "✓", "blocked": "BLOQUEADO", "error": "ERROR"}[outcome]
            aviso = " ⚠postura" if attempt["posture_divergences"] else ""
            reintento = f" ↻{len(attempt['attempts'])}" if len(attempt["attempts"]) > 1 else ""
            print(
                f"{marca}{aviso}{reintento}  {attempt['latency_ms']:.0f}ms  "
                f"«{attempt['response_preview'][:50]}»",
                flush=True,
            )

    ledger.close()

    # El registro de ejecuciones es lo que permite comprobar después que ninguna
    # desapareció en silencio y con qué postura corrió cada una.
    (run_folder / "executions.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )

    if divergencias:
        _flush("")
        _flush(SEP2)
        _flush("  ⚠ POSTURA SOLICITADA ≠ EFECTIVA — la comparación causal queda invalidada")
        for item in divergencias[:10]:
            _flush(f"    · {item['target']}: {', '.join(item['divergences'])}")
        if len(divergencias) > 10:
            _flush(f"    · … y {len(divergencias) - 10} más (ver executions.json)")

    _flush("")
    _flush(SEP2)
    _flush(
        f"  SUITE COMPLETADA — {sent} correctos · {blocked} bloqueados"
        f" · {errors} errores técnicos"
    )
    if error_phases:
        desglose = " · ".join(f"{fase}={n}" for fase, n in sorted(error_phases.items()))
        _flush(f"  Errores por fase: {desglose}")
    if retried:
        _flush(
            f"  Reintentos: {retried} ejecuciones necesitaron reintento · "
            f"{rescatados} resueltos tras reintentar · {retried - rescatados} siguen en error"
        )
    _flush(f"  Run Folder : {display_path(run_folder)}")
    _flush(f"  Siguiente  : python scripts/evaluate.py --run {display_path(run_folder)}")
    _flush(SEP2)
    _flush(f"=== RUN END run_id={ts_file} errors={errors} ===")


if __name__ == "__main__":
    asyncio.run(main())
