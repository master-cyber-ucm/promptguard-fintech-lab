"""El puente entre un turno capturado y lo que el proyecto ya sabe sobre ese ataque.

No hay metadatos que mantener ni etiquetado manual: **fixtures y documentación comparten
el mismo árbol de taxonomía**, así que la correspondencia es estructural.

    lab/backend/tests/fixtures/LLM07-system-prompt-leakage/filtrado-por-repeticion/…
    docs/ataques/           LLM07-system-prompt-leakage/filtrado-por-repeticion/07-playbook…
    docs/defensas/          LLM07-system-prompt-leakage/filtrado-por-repeticion.md

El índice se construye en memoria al arrancar recorriendo el disco. Nada se copia a la
base: la fuente de verdad sigue siendo el repositorio, y editar un documento se refleja
al reiniciar el backend.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from src.utils.fixture_loader import FIXTURES_DIR, iter_prompt_files, _load_yaml

logger = logging.getLogger(__name__)


def _resolver_docs() -> Optional[Path]:
    """Localiza `docs/`, que vive fuera del backend y se monta en el contenedor."""
    candidatos = []
    if os.environ.get("SOC_DOCS_DIR"):
        candidatos.append(Path(os.environ["SOC_DOCS_DIR"]))
    candidatos.append(Path("/app/docs"))
    # En el contenedor el árbol es /app/src/soc/, que no tiene 4 niveles por encima:
    # se recorre hacia arriba lo que haya en vez de indexar a ciegas.
    aqui = Path(__file__).resolve()
    candidatos.extend(p / "docs" for p in aqui.parents)
    for c in candidatos:
        if (c / "ataques").is_dir():
            return c
    return None


DOCS_DIR = _resolver_docs()

# Los 7 documentos por subcategoría de ataque tienen nombre y orden regulares. El título
# legible se fija aquí en vez de derivarlo del nombre de fichero, que produce etiquetas
# como "01 Mapeo Taxonomico".
TIPOS_ATAQUE = {
    "README":                       ("Resumen", 0),
    "01-mapeo-taxonomico":          ("Mapeo taxonómico", 1),
    "02-threat-modeling":           ("Threat modeling", 2),
    "03-casos-reales":              ("Casos reales", 3),
    "04-analisis-tecnico":          ("Análisis técnico", 4),
    "05-cumplimiento-normativo":    ("Cumplimiento normativo", 5),
    "06-contexto-verdabank":        ("Contexto VerdaBank", 6),
    "07-playbook-incident-response": ("Playbook de respuesta", 7),
}

# Severidad por categoría cuando el turno no viene de un fixture que la declare. Es un
# mapa fijo y declarado, no una puntuación calculada: el panel dice siempre de dónde
# sale la severidad para no presentar como objetivo un juicio que no lo es.
SEVERIDAD_POR_CATEGORIA = {
    "LLM01-prompt-injection": "HIGH",
    "LLM02-sensitive-information-disclosure": "CRITICAL",
    "LLM06-excessive-agency": "CRITICAL",
    "LLM07-system-prompt-leakage": "MEDIUM",
    "_extensiones": "HIGH",
}

_H1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_H2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)


# --- Taxonomía de los fixtures ---------------------------------------------------

@lru_cache(maxsize=1)
def _indice_fixtures() -> dict[str, dict]:
    """`fixture_id` → taxonomía y severidad, leído del árbol de fixtures.

    Recorre los tres kinds, no solo `attack-prompts`: un turno legítimo también tiene
    taxonomía y también merece contexto.
    """
    indice: dict[str, dict] = {}
    for ruta in iter_prompt_files(root=FIXTURES_DIR, kind=None):
        try:
            datos = _load_yaml(ruta)
        except Exception:  # noqa: BLE001 — un YAML roto no puede tumbar el arranque
            logger.warning("[soc] fixture ilegible, se omite del índice: %s", ruta)
            continue
        fid = str(datos.get("id") or "").strip()
        if not fid or fid in indice:
            continue
        partes = ruta.relative_to(FIXTURES_DIR).parts
        if len(partes) < 3:
            continue
        indice[fid] = {
            "categoria": partes[0],
            "subcategoria": partes[1],
            "kind": partes[2],
            "severity": (datos.get("severity") or "").upper() or None,
            "attack": datos.get("attack"),
            "nombre": datos.get("name") or datos.get("title") or fid,
        }
    return indice


def taxonomia_de_fixture(fixture_id: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not fixture_id:
        return None, None
    entrada = _indice_fixtures().get(fixture_id)
    if not entrada:
        return None, None
    return entrada["categoria"], entrada["subcategoria"]


def severidad_de(
    fixture_id: Optional[str], categoria: Optional[str], attack_type: Optional[str]
) -> tuple[str, str]:
    """Severidad de una alerta y **de dónde salió**.

    El segundo valor es la mitad importante: distingue una severidad declarada por el
    fixture de una heredada de un mapa fijo, para que el panel no las presente igual.
    """
    if fixture_id:
        entrada = _indice_fixtures().get(fixture_id)
        if entrada and entrada.get("severity"):
            return entrada["severity"], "fixture"
    if categoria and categoria in SEVERIDAD_POR_CATEGORIA:
        return SEVERIDAD_POR_CATEGORIA[categoria], "mapa-categoria"
    if attack_type:
        return "HIGH", "mapa-categoria"
    return "MEDIUM", "por-defecto"


# --- Índice documental -----------------------------------------------------------

def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8", errors="replace")


def _titulo(texto: str, respaldo: str) -> str:
    m = _H1.search(texto)
    return m.group(1).strip() if m else respaldo


@lru_cache(maxsize=1)
def _indice_docs() -> dict:
    """Recorre `docs/ataques` y `docs/defensas` y devuelve el árbol navegable."""
    if DOCS_DIR is None:
        logger.warning("[soc] no se encontró docs/ — la base de conocimiento irá vacía")
        return {"disponible": False, "taxonomia": {}, "documentos": {}}

    taxonomia: dict[str, dict] = {}
    documentos: dict[str, dict] = {}

    def _registrar(clave: str, ruta: Path, meta: dict) -> None:
        texto = _leer(ruta)
        documentos[clave] = {
            **meta,
            "clave": clave,
            # `titulo` es la etiqueta canónica del tipo de documento y es la que usa el
            # árbol: los H1 reales varían de una subcategoría a otra ("Mapeo Taxonómico —
            # Prompt Injection Directa" frente a "01 — Mapeo Taxonómico") y mezclarlos
            # hace que el índice parezca desordenado. El H1 real se conserva aparte.
            "titulo_documento": _titulo(texto, meta.get("titulo", clave)),
            "secciones": _H2.findall(texto),
            "palabras": len(texto.split()),
            "ruta_relativa": str(ruta.relative_to(DOCS_DIR)),
        }

    raiz_ataques = DOCS_DIR / "ataques"
    for dir_cat in sorted(p for p in raiz_ataques.iterdir() if p.is_dir()):
        cat = dir_cat.name
        entrada_cat = taxonomia.setdefault(cat, {"categoria": cat, "subcategorias": {}})
        # README de la categoría: la visión de conjunto del vector, útil como entrada a
        # la pantalla de Conocimiento antes de bajar a una subcategoría concreta.
        readme_cat = dir_cat / "README.md"
        if readme_cat.is_file():
            clave = f"ataques/{cat}/README"
            _registrar(clave, readme_cat, {
                "tipo": "ataque", "categoria": cat, "subcategoria": None,
                "documento": "README", "titulo": "Ataque — visión de categoría",
                "orden": 0, "playbook": False,
            })
            entrada_cat["ataque_categoria"] = clave
        for dir_sub in sorted(p for p in dir_cat.iterdir() if p.is_dir()):
            sub = dir_sub.name
            sub_entrada = entrada_cat["subcategorias"].setdefault(
                sub, {"subcategoria": sub, "ataque": [], "defensa": None}
            )
            for md in sorted(dir_sub.glob("*.md")):
                nombre, (titulo, orden) = md.stem, TIPOS_ATAQUE.get(md.stem, (md.stem, 99))
                clave = f"ataques/{cat}/{sub}/{nombre}"
                _registrar(clave, md, {
                    "tipo": "ataque", "categoria": cat, "subcategoria": sub,
                    "documento": nombre, "titulo": titulo, "orden": orden,
                    "playbook": nombre == "07-playbook-incident-response",
                })
                sub_entrada["ataque"].append(clave)
            sub_entrada["ataque"].sort(key=lambda k: documentos[k]["orden"])

    raiz_defensas = DOCS_DIR / "defensas"
    if raiz_defensas.is_dir():
        for dir_cat in sorted(p for p in raiz_defensas.iterdir() if p.is_dir()):
            cat = dir_cat.name
            for md in sorted(dir_cat.glob("*.md")):
                if md.stem == "README":
                    clave = f"defensas/{cat}/README"
                    _registrar(clave, md, {
                        "tipo": "defensa", "categoria": cat, "subcategoria": None,
                        "documento": "README", "titulo": "Defensa — visión de categoría",
                        "orden": 0, "playbook": False,
                    })
                    taxonomia.setdefault(cat, {"categoria": cat, "subcategorias": {}})
                    taxonomia[cat]["defensa_categoria"] = clave
                    continue
                sub = md.stem
                clave = f"defensas/{cat}/{sub}"
                _registrar(clave, md, {
                    "tipo": "defensa", "categoria": cat, "subcategoria": sub,
                    "documento": sub, "titulo": "Diseño de la defensa", "orden": 0,
                    "playbook": False,
                })
                entrada_cat = taxonomia.setdefault(cat, {"categoria": cat, "subcategorias": {}})
                sub_entrada = entrada_cat["subcategorias"].setdefault(
                    sub, {"subcategoria": sub, "ataque": [], "defensa": None}
                )
                sub_entrada["defensa"] = clave

    return {"disponible": True, "taxonomia": taxonomia, "documentos": documentos}


def indice() -> dict:
    """Árbol de conocimiento + las subcategorías de fixtures que no tienen documentación.

    El hueco se declara, no se esconde: `_extensiones` (jailbreak, chained, ingeniería
    social, ofuscación) son fixtures reales sin ningún documento asociado, y quien mire
    un evento de esos tiene derecho a saber que no hay playbook porque no se ha escrito,
    no porque el panel no lo encuentre.
    """
    idx = _indice_docs()
    documentadas = {
        (cat, sub)
        for cat, datos in idx["taxonomia"].items()
        for sub in datos["subcategorias"]
    }
    con_fixtures: dict[tuple[str, str], int] = {}
    for entrada in _indice_fixtures().values():
        clave = (entrada["categoria"], entrada["subcategoria"])
        con_fixtures[clave] = con_fixtures.get(clave, 0) + 1

    sin_documentar = [
        {"categoria": c, "subcategoria": s, "fixtures": n}
        for (c, s), n in sorted(con_fixtures.items())
        if (c, s) not in documentadas
    ]
    return {**idx, "sin_documentar": sin_documentar}


def documento(clave: str) -> Optional[dict]:
    """Devuelve un documento con su contenido Markdown crudo.

    El SOC no reescribe ni resume: sirve el texto tal cual está en el repositorio.
    """
    idx = _indice_docs()
    meta = idx["documentos"].get(clave)
    if not meta or DOCS_DIR is None:
        return None
    ruta = DOCS_DIR / meta["ruta_relativa"]
    if not ruta.is_file():
        return None
    return {**meta, "contenido": _leer(ruta)}


def documentos_de(categoria: Optional[str], subcategoria: Optional[str]) -> dict:
    """Todo lo que el proyecto sabe sobre una taxonomía: ataque, defensa y playbook."""
    idx = _indice_docs()
    vacio = {
        "disponible": False, "categoria": categoria, "subcategoria": subcategoria,
        "ataque": [], "defensa": None, "playbook": None, "defensa_categoria": None,
    }
    if not categoria or not subcategoria:
        return vacio
    entrada_cat = idx["taxonomia"].get(categoria)
    if not entrada_cat:
        return vacio
    sub = entrada_cat["subcategorias"].get(subcategoria)
    if not sub:
        return vacio

    docs = idx["documentos"]
    playbook = next((k for k in sub["ataque"] if docs[k].get("playbook")), None)
    return {
        "disponible": True,
        "categoria": categoria,
        "subcategoria": subcategoria,
        "ataque": [docs[k] for k in sub["ataque"]],
        "defensa": docs.get(sub["defensa"]) if sub["defensa"] else None,
        "defensa_categoria": (
            docs.get(entrada_cat.get("defensa_categoria"))
            if entrada_cat.get("defensa_categoria") else None
        ),
        "playbook": docs.get(playbook) if playbook else None,
    }


def recargar() -> None:
    """Vacía los índices. Los tests lo usan; en producción basta con reiniciar."""
    _indice_fixtures.cache_clear()
    _indice_docs.cache_clear()
