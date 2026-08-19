"""Rastro de auditoría legible por Ejercicio/ataque — plan de excelencia §B7.

Una carpeta por Ejercicio (estable entre Campañas, nombrada por técnica) y, dentro, un
fichero por ATAQUE — una ejecución de ese Ejercicio dentro de una Campaña concreta,
nombrado por su `run_folder_name`. Dentro del fichero, los Intentos se separan con
divisores (`## Intento N` + `---`), mismo patrón que `_format_turn` ya usa en
`audit_repository.py` del backend para separar Turnos dentro de un Session File.

Append inmediato, no al cierre del Ejercicio — sobrevive un crash a mitad de campaña,
igual que `audit_repository.append_turn()` ya hace para los Session Files ("sin esperar
al fin de la sesión").

No sustituye los Session Files (`lab/audit/runs/`, que alimentan el SOC) ni el Informe de
Campaña (`run.json`/`run.md`) — es una tercera vista, propia del agente, pensada para
auditar un ataque completo de un vistazo sin cruzar ficheros.
"""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
EJERCICIOS_DIR = HERE / "ejercicios"


class EjercicioWriter:
    def __init__(self, tecnica_id: str, run_folder_name: str) -> None:
        self.path = EJERCICIOS_DIR / tecnica_id / f"{run_folder_name}.md"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def abrir_ejercicio(self, nombre: str, objetivo: str, motor: str, modo: str) -> None:
        cabecera = (
            f"# {nombre} — `{self.path.stem}`\n\n"
            f"**Objetivo**: {objetivo.strip()}\n\n"
            f"**Motor de evolución**: `{motor}` · **Modo**: `{modo}`\n\n---\n\n"
        )
        self.path.write_text(cabecera, encoding="utf-8")

    def abrir_intento(self, numero: int) -> None:
        self._append(f"## Intento {numero}\n\n")

    def append_turno(self, n_turno: int, payload: str, respuesta: str, error: str | None = None) -> None:
        bloque_respuesta = respuesta.strip() if respuesta else (f"[BLOQUEADO/ERROR] {error}" if error else "[sin respuesta]")
        self._append(
            f"### Turno {n_turno}\n\n"
            f"**Payload**:\n```\n{payload.strip()}\n```\n\n"
            f"**Respuesta**:\n```\n{bloque_respuesta}\n```\n\n"
        )

    def cerrar_intento(self, veredicto: str, razonamiento: str) -> None:
        self._append(f"**Veredicto**: `{veredicto}` — {razonamiento.strip()}\n\n---\n\n")

    def _append(self, texto: str) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(texto)
