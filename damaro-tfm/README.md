# Ataque #5 — Cross-Context Leakage (Darwin/Damaro)

Este directorio contiene el material de trabajo del vector Cross-Context Leakage (OWASP LLM02:2025, AML.T0024 de MITRE ATLAS).

El contenido consolidado y citable de este vector está en el documento grupal del TFM, seccion 5.3 y Anexos B.3, C.5 y D.

## Contenido de este directorio

- 01-ataque/: fixtures YAML usados (atk_008, atk_009), copia de lab/backend/tests/fixtures/LLM02-sensitive-information-disclosure/cross-context-leakage/attack-prompts/.
- 02-defensa/: referencia al mecanismo de defensa (Tool Gatekeeper), consolidado hoy en el pipeline compartido del proyecto (lab/backend/src/agents/tools.py).
- evidencia/: capturas de pantalla de las pruebas realizadas (ataque en modo vulnerable y verificacion de la defensa).
