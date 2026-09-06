"""Test del fix de 'thinking mode' en OllamaClient — ver ollama_client.py::chat().
Bug real encontrado en la campaña de 6 técnicas del 2026-09-06 (fusión con
Red Team_): sin `think: False`, qwen3.5 vuelca el texto en `message.thinking` y
`message.content` llega vacío, degradando toda generación a un fallback fijo."""

from __future__ import annotations

import httpx
import pytest

from ollama_client import OllamaClient


class _RespuestaFalsa:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_chat_envia_think_false(monkeypatch):
    capturado = {}

    def _post_falso(url, json, timeout):
        capturado["json"] = json
        return _RespuestaFalsa({"message": {"content": "PAYLOAD: hola"}})

    monkeypatch.setattr(httpx, "post", _post_falso)
    client = OllamaClient("http://localhost:11434", "qwen3.5:4b")
    client.chat([{"role": "user", "content": "hola"}])

    assert capturado["json"]["think"] is False


def test_chat_devuelve_content_normal(monkeypatch):
    monkeypatch.setattr(
        httpx, "post",
        lambda url, json, timeout: _RespuestaFalsa({"message": {"content": "  PAYLOAD: x  "}}),
    )
    client = OllamaClient("http://localhost:11434", "qwen3.5:4b")
    assert client.chat([{"role": "user", "content": "hola"}]) == "PAYLOAD: x"


def test_chat_cae_a_thinking_si_content_viene_vacio(monkeypatch):
    """El caso real del bug: content vacío pese a think:False (versión de Ollama que
    ignora el flag) — antes de este fix, esto producía "" y el fallback fijo de
    attacker.py._extraer_payload en TODOS los intentos sin semilla."""
    monkeypatch.setattr(
        httpx, "post",
        lambda url, json, timeout: _RespuestaFalsa({
            "message": {"content": "", "thinking": "razonamiento con el texto real"}
        }),
    )
    client = OllamaClient("http://localhost:11434", "qwen3.5:4b")
    assert client.chat([{"role": "user", "content": "hola"}]) == "razonamiento con el texto real"


def test_chat_sin_content_ni_thinking_devuelve_vacio(monkeypatch):
    monkeypatch.setattr(
        httpx, "post",
        lambda url, json, timeout: _RespuestaFalsa({"message": {}}),
    )
    client = OllamaClient("http://localhost:11434", "qwen3.5:4b")
    assert client.chat([{"role": "user", "content": "hola"}]) == ""
