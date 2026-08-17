"""Configuración de una Campaña del Agente de red-team.

Todo lo que decidió el grilling vive aquí como defaults explícitos: modo caja
negra por defecto, motor de evolución paramétrico, target configurable con
`/chat/proxy` por defecto, presupuesto fijo de intentos por Ejercicio.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Relativos a `CampaignConfig.api_base` (que YA incluye /api/v1) — a diferencia de
# run_attack_suite.py, que compone la URL completa aparte y por eso ahí sí lleva el
# prefijo. Duplicarlo aquí produce un 404 silencioso: `resp.json()` de un 404 devuelve
# `{"detail": "Not Found"}`, que `data.get("response", "")` reduce a cadena vacía sin
# lanzar excepción — el juez se queda evaluando "nada" y su veredicto deja de tener
# ninguna relación con lo que de verdad pasó. Bug real encontrado en la primera corrida
# de humo (ver bitácora): 0 Session Files escritos, veredictos SUCCESS/FAILED sin base.
CHAT_ENDPOINTS: dict[str, str] = {
    "simple-prompt": "/chat/simple-prompt",
    "complex-prompt": "/chat/complex-prompt",
    "complex-with-context": "/chat/complex-with-context",
    "proxy": "/chat/proxy",
}

MOTORES = ("autorreflexivo", "genetico", "taxonomia")
MODOS = ("caja-negra", "caja-gris")


@dataclass
class CampaignConfig:
    target: str = "proxy"
    vulnerable: bool = False
    modo: str = "caja-negra"
    motor: str = "autorreflexivo"
    attacker_model: str = "qwen3.5:9b"
    max_intentos_por_ejercicio: int = 20
    user_id: str = "usr_001"
    tecnicas: list[str] = field(default_factory=list)  # vacío = todas
    host: str = "localhost"
    port: int = 8000
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    temperature: float = 0.9

    @property
    def api_base(self) -> str:
        return f"http://{self.host}:{self.port}/api/v1"

    @property
    def ollama_base(self) -> str:
        return f"http://{self.ollama_host}:{self.ollama_port}"

    @property
    def endpoint_path(self) -> str:
        return CHAT_ENDPOINTS[self.target]


def parse_args(argv: list[str] | None = None) -> CampaignConfig:
    p = argparse.ArgumentParser(
        prog="redteam-agent",
        description="Agente de red-team autónomo contra el lab PromptGuard (Campaña).",
    )
    p.add_argument("--target", choices=sorted(CHAT_ENDPOINTS), default="proxy",
                    help="Endpoint objetivo (default: proxy, pipeline defendido completo)")
    p.add_argument("--vulnerable", action="store_true",
                    help="Modo control: mismas defensas del target pero flag vulnerable=True")
    p.add_argument("--mode", dest="modo", choices=MODOS, default="caja-negra",
                    help="caja-negra (default): solo respuesta de Clara. caja-gris: lee también eventos SOC")
    p.add_argument("--engine", dest="motor", choices=MOTORES, default="autorreflexivo",
                    help="Motor de evolución: autorreflexivo (default) | genetico | taxonomia")
    p.add_argument("--attacker-model", default="qwen3.5:9b",
                    help="Modelo Ollama que hace de cerebro atacante (default: qwen3.5:9b)")
    p.add_argument("--max-attempts", dest="max_intentos_por_ejercicio", type=int, default=20,
                    help="Presupuesto de intentos por Ejercicio (default: 20)")
    p.add_argument("--user", dest="user_id", default="usr_001")
    p.add_argument("--techniques", dest="tecnicas", nargs="*", default=[],
                    help="Subconjunto de técnicas por id (default: todas las del harness)")
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--ollama-host", default="localhost")
    p.add_argument("--ollama-port", type=int, default=11434)
    p.add_argument("--temperature", type=float, default=0.9)
    ns = p.parse_args(argv)
    return CampaignConfig(
        target=ns.target, vulnerable=ns.vulnerable, modo=ns.modo, motor=ns.motor,
        attacker_model=ns.attacker_model, max_intentos_por_ejercicio=ns.max_intentos_por_ejercicio,
        user_id=ns.user_id, tecnicas=ns.tecnicas, host=ns.host, port=ns.port,
        ollama_host=ns.ollama_host, ollama_port=ns.ollama_port, temperature=ns.temperature,
    )
