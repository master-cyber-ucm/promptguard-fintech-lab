# PR 5 — Evidencia de validación

## Naturaleza de esta PR

Entrega de diseño (ADR-0017), perfiles y un gate — no lanza la campaña
baseline/full/ablaciones completa, tal como el informe original la delimita
explícitamente ("la PR entrega diseño, perfiles, validadores y plan; lanzar la
campaña requiere aprobación de coste/duración").

## Hallazgo: el validador de comparabilidad ya existía y ya funcionaba

Antes de escribir código, se verificó `TargetPosture.comparable_fingerprint` /
`comparison_blockers` (`backend/src/models/posture.py`). Ya calcula una huella sobre
todo lo que NO es un control defensivo declarado (`DEFENSE_CONTROLS`) y ya rechaza
como no comparables dos posturas que difieran en cualquier otra cosa — es
exactamente el mecanismo que produjo `causal_comparison.proxy-full.comparable=false`
en el run citado por el informe, porque `vulnerable` (`true` en baseline, `false` en
full) no está en `DEFENSE_CONTROLS` y por tanto cuenta como "factor no defensivo
distinto". El validador no tenía ningún defecto; el defecto está en que hoy no existe
ninguna postura que comparta `vulnerable` y siga siendo un contrafactual real, porque
ese flag condiciona más de 15 puntos de `chat.py` fuera de los 5 controles
declarados (protección DoS, `enforce_gatekeeper`, interacciones de `leak_guard`/
`pii_shield`). Documentado en ADR-0017 con el mapa exacto de esos condicionales.

## Implementado

1. **Matriz de ablaciones**: `only-input`, `only-pii`, `only-gatekeeper`,
   `only-auditor`, `only-leak` en `chat.py` (perfiles del backend) y
   `run_attack_suite.py` (`PROXY_PROFILES`/`REQUESTED_CONTROLS`). Los cinco fijan
   `vulnerable=False` — igual que `full` — así que son comparables entre sí sin
   necesitar el desacoplamiento diferido.
2. **Gate de reproducibilidad accionable**: `--require-clean-tree` convierte el aviso
   histórico de árbol sucio en un abort previo a abrir tráfico.

## Validación

### Unitaria

Suite completa sin regresiones: 852/852 en verde
(`PYTHONPATH="$(pwd):$(pwd)/.." python -m pytest tests/ -q` desde `lab/backend`).
`test_flag_vulnerable.py` (perfiles `baseline`/`gatekeeper`/perfil inválido) sigue
pasando sin cambios — los perfiles nuevos son aditivos.

### Funcional (backend en vivo)

`POST /api/v1/chat/proxy` con `proxy_profile=only-pii` contra `qwen2.5:3b`:

```json
{
  "vulnerable": false,
  "input_sanitizer": false,
  "pii_shield": true,
  "tool_gatekeeper": false,
  "output_auditor": false,
  "leak_guard": false
}
```

`effective_posture` confirma exactamente el control único declarado: `pii_shield=true`,
el resto de controles en `false`, `vulnerable=false`. El perfil llega al backend, se
resuelve y se refleja en la postura efectiva verificable — no solo en la solicitada.

## Fuera de alcance (anotado en ADR-0017, no ejecutado en este PR)

- Desacoplar `vulnerable` de los más de 15 condicionales de `chat.py` que lo leen hoy
  fuera de los 5 controles declarados — es el único cambio que haría a
  `proxy-baseline` comparable de verdad contra `full`/ablaciones. Alto riesgo de
  regresión en rutas de seguridad activas (DoS, ownership) sin ventana de regresión
  completa; se documenta el mapa exacto de condicionales para el PR que lo ejecute.
- `document-baseline`/`document-full` comparables y ataques directos de `SYSTEM_LEAK`
  contra el proxy: requieren fixtures nuevos en el catálogo, no solo código de
  runner/backend.
- Lanzar la campaña de ablaciones completa (coste/duración fuera del alcance de este
  PR, según el propio informe).
