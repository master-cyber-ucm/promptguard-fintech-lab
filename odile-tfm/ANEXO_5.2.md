# Anexos 5.2 — reproducibilidad de este capítulo

Toda la evidencia de este capítulo es reproducible localmente contra el lab del proyecto (`~/Desktop/promptguard-fintech-lab/lab`):

## Payloads y fixtures de ataque

**Ubicación:** `lab/fixtures/LLM01-prompt-injection/directa/`

- atk_001_ignore_instructions_es.yaml
- atk_002_ignore_instructions_en.yaml
- atk_ignore_instructions_chinese.yaml
- atk_013_payload_splitting.yaml
- atk_016_base64.yaml
- atk_014_fake_security_test.yaml

## Evidencia de ejecución (audit runs)

**Ubicación:** `odile-tfm/audit-runs/`

- 20260804_154912_qwen2.5-3b/
- 20260804_211356_qwen2.5-3b/
- 20260805_163209_qwen2.5-3b/

Cada carpeta contiene los resultados de ejecución organizados por endpoint (`simple-prompt`, `complex-prompt`, `complex-with-context`).

## Reproducir ataque completo

```bash
docker exec -e FIXTURES_DIR=/app/tests/fixtures/LLM01-prompt-injection/directa \
promptguard-backend python scripts/run_attack_suite.py --repeat 1
```

## Metodología

- Cada fixture YAML especifica el payload, el objetivo de la cuenta, y el criterio de éxito determinista.
- Las sesiones se registran como archivos markdown timestamped en cada carpeta de audit run.
- El criterio de éxito es la invocación de `consulta_saldo` contra una cuenta no autorizada, sin depender de lectura subjetiva del texto de respuesta.
