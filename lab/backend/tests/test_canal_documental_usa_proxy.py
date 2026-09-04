"""PR10 — el canal documental deja de apuntar a `/chat/complex-with-document`
(deprecado en PR7/ADR-0018) y pasa a ser `proxy_profile` sobre `/chat/proxy`.

Antes de este PR, `--document-profile` enviaba flags `defensa_*` que el backend ya
no lee en esa ruta — silenciosamente no gateaban nada — y once fixtures documentales
quedaban sin ningún target aplicable (`capabilities.py`, P10).
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
from run_attack_suite import (  # noqa: E402
    CHAT_ENDPOINTS,
    DOCUMENT_PROFILES,
    DOCUMENT_PROXY_PROFILE,
    applicable_targets,
    requested_posture,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
from src.models.capabilities import decide  # noqa: E402


def test_el_endpoint_deprecado_ya_no_es_una_opcion_de_la_cli():
    assert "complex-with-document" not in CHAT_ENDPOINTS
    assert set(CHAT_ENDPOINTS) == {"simple-prompt", "complex-prompt", "complex-with-context", "proxy"}


def test_cada_postura_documental_resuelve_al_proxy_profile_real_del_servidor():
    """`proxy-document-baseline` debe pedir `proxy_profile=baseline`, no `None`
    (que el servidor no distingue de "sin perfil" y el runner interpretaría como
    "full" — ver `requested_posture`)."""
    assert DOCUMENT_PROXY_PROFILE == {"document-baseline": "baseline", "document-full": "full"}


def test_la_postura_solicitada_de_un_target_documental_coincide_con_su_perfil():
    for profile_doc, profile_servidor in DOCUMENT_PROXY_PROFILE.items():
        target = f"proxy-{profile_doc}"
        assert requested_posture(target, profile_servidor) == requested_posture("proxy", profile_servidor)


def test_un_fixture_documental_solo_es_aplicable_al_canal_documental_del_proxy():
    fixture = {"id": "atk_doc", "document": "payload.pdf", "kind": "attack-prompts"}
    endpoints = {
        "simple-prompt": "/s", "complex-prompt": "/c", "complex-with-context": "/x",
        "proxy-baseline": "/p", "proxy-full": "/p",
        "proxy-document-baseline": "/p", "proxy-document-full": "/p",
    }
    assert applicable_targets(fixture, endpoints) == ["proxy-document-baseline", "proxy-document-full"]


def test_un_fixture_de_texto_no_es_aplicable_al_canal_documental():
    fixture = {"id": "atk_texto", "kind": "attack-prompts", "rendered_steps": [{"content": "x"}]}
    decision = decide(fixture, "proxy-document-full")
    assert not decision.in_population


def test_document_profiles_produce_nombres_de_target_consistentes_con_capabilities():
    """`f"proxy-{profile}"` para cada valor de DOCUMENT_PROFILES debe coincidir con
    lo que `capabilities.capabilities_of_target` reconoce como canal documental."""
    from src.models.capabilities import capabilities_of_target, Capability  # noqa: PLC0415

    for profile in DOCUMENT_PROFILES:
        target = f"proxy-{profile}"
        caps = capabilities_of_target(target)
        assert Capability.DOCUMENT_UPLOAD in caps.supported, target
