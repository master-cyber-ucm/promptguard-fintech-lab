"""Motor de mutación — Fase 2.9 (red teaming automatizado), extensión post-cierre.

Prueba, contra el código real de defensa ((B) sanitizer + (A) structural detector, sin LLM —
esa parte es determinista y no necesita latencia de red), cada variante generada por
`generar_pdf_mutado.py --all` a partir del catálogo de `tecnicas_ofuscacion.py`. Cierra
parcialmente la limitación "no cubre generación de variantes nuevas" de CAPITULO.md §5: las
variantes de técnicas YA conocidas se generan y prueban aquí de forma programática y repetible,
sin escribir un experimento manual nuevo cada vez que se añade una técnica al catálogo.

Ejecutar DENTRO del contenedor backend (necesita importar src.*):
    docker cp henri-tfm/01-ataque/payloads/nomina_comprometida_*.pdf promptguard-backend:/app/tests/
    docker cp henri-tfm/01-ataque/evidencia/motor_mutacion/probar_mutaciones.py promptguard-backend:/app/tests/
    docker compose exec backend python tests/probar_mutaciones.py
    # limpiar después: docker compose exec backend rm -f tests/nomina_comprometida_*.pdf tests/probar_mutaciones.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.document_extractor import extract_text
from src.core.document_sanitizer import sanitize_document_text
from src.core.document_structural_detector import detect_hiding_techniques

TESTS_DIR = Path(__file__).resolve().parent
TECNICAS = ["zero_width", "homoglyph"]  # debe coincidir con tecnicas_ofuscacion.TECHNIQUES


def probar(tecnica: str) -> dict:
    filename = f"nomina_comprometida_{tecnica}.pdf"
    path = TESTS_DIR / filename
    content = path.read_bytes()
    text = extract_text(filename, content)

    decision = sanitize_document_text(text)
    structural = detect_hiding_techniques(filename, content)

    return {
        "tecnica": tecnica,
        "B_evadida": decision.action != "BLOCK",
        "B_accion": decision.action,
        "B_regla": decision.matched_rule,
        "A_detecta": len(structural) > 0,
        "A_hallazgos": structural,
    }


def main() -> None:
    resultados = [probar(t) for t in TECNICAS]

    print(f"{'Técnica':<15} {'(B) evadida':<14} {'(A) detecta':<14} Hallazgos (A)")
    print("-" * 70)
    for r in resultados:
        print(
            f"{r['tecnica']:<15} {'SÍ' if r['B_evadida'] else 'no':<14} "
            f"{'sí' if r['A_detecta'] else 'NO':<14} {', '.join(r['A_hallazgos'])}"
        )

    n_evadidas = sum(r["B_evadida"] for r in resultados)
    n_capturadas_por_A = sum(r["A_detecta"] for r in resultados)
    print(f"\n(B) evadida por {n_evadidas}/{len(resultados)} técnicas.")
    print(f"(A) sigue capturando {n_capturadas_por_A}/{len(resultados)} — indiferente al contenido textual.")

    out = TESTS_DIR / "resultados_motor_mutacion.json"
    out.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados guardados en {out}")


if __name__ == "__main__":
    main()
