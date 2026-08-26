# PromptGuard FinTech Lab

Repositorio de trabajo del lab de ciberseguridad en entornos de IA generativa.

## Contenido

- `lab/` - aplicación vulnerable, frontend, backend y scripts de verificación.
- `docs/` - documentación formal del proyecto.
- `openrouter.sh` - smoke test local para OpenRouter.

## Arranque rápido

```bash
cd lab
cp .env.example .env
docker compose up --build
```

## Modos de proveedor

- `LLM_PROVIDER=ollama`
- `LLM_PROVIDER=openrouter`
- `LLM_PROVIDER=custom`

La guía detallada de operación está en [lab/README.md](lab/README.md).

## Verificación

```bash
python scripts/check_providers.py --provider all
python scripts/smoke_test.py
python scripts/run_attack_suite.py
```

## Documentación

- [docs/propuesta-formal-promptguard-fintech.md](docs/propuesta-formal-promptguard-fintech.md)
- [docs/anexo-catalogo-ataques-llm.md](docs/anexo-catalogo-ataques-llm.md)
