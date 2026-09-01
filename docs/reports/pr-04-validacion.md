# PR 4 — Evidencia de validación

## Corrección (post-verificación)

La primera versión de este documento afirmaba que `run_attack_suite.py` escribía un
`applicability-manifest.json` nuevo porque la decisión completa de aplicabilidad "se
descartaba". Al preparar la validación funcional de PR6 se comprobó que eso era falso:
`coverage-plan.json` ya persiste `auditoria.to_dict()` completo bajo la clave
`applicability` desde el commit `46f7fe0` ("feat(suite): make evidence and coverage
reproducible"), que ya estaba en la rama antes de empezar este trabajo. El fichero
añadido era una duplicación exacta de datos ya persistidos — se retiró
(`run_attack_suite.py` vuelve a solo auditar y destacar huérfanos por consola; la
persistencia sigue viviendo en `coverage-plan.json`, que ya la tenía). El punto 1 de
más abajo queda tachado por esa razón; los puntos 2-4 sí son correcciones de código
propias de este PR y se mantienen.

## Alcance implementado

De las cinco causas listadas en el informe, se abordaron dos con corrección de código
bien delimitada y bajo riesgo de regresión (más una tercera que resultó ya resuelta,
ver arriba); las otras dos quedan anotadas como seguimiento explícito (ver "Fuera de
alcance").

1. ~~**Manifiesto de aplicabilidad persistido.**~~ Ya existía (ver corrección arriba).
2. **Denominador OWASP solo cuenta ataques.** `category_claims()` sumaba TODAS las
   filas del plan (incluidas legítimas) en `applicable`, pero solo ataques en
   `executed`/`successes`. Ahora ambos lados del claim se filtran por
   `_traffic_kind(fila) == ATTACK`.
3. **Gate por subtipo para LLM07.** `evaluate_claim` ya soportaba `subtype_cells`,
   pero `category_claims()` no lo usaba. Ahora siembra una celda para
   `PROTECTED_SECRET_LEAK` (fuga directa del system prompt) aunque tenga 0 casos
   aplicables — que es justo el caso `applicable=0` el que bloquea el claim con
   «sin evidencia suficiente para `PROTECTED_SECRET_LEAK`: 0 casos aplicables», en vez
   de publicar «100%» sobre un vector que el target ni siquiera ejecutó.
4. **Errores técnicos visibles en el total por endpoint.** `by_endpoint.summary.total`
   salía de los Session Files existentes; una Fixture Execution sin Session File
   (error antes de cualquier turno) desaparecía. Se añaden `planned_total` (del
   ledger reconciliado, ya existente en `coverage.by_target`) y
   `technical_errors_missing_evidence`; `run.md` muestra una fila adicional
   "Total planificado (ledger)" solo cuando diverge del total con Session File.

## Validación

### Unitaria

- `test_claims_por_cobertura.py::test_el_denominador_solo_cuenta_trafico_de_ataque`:
  una fila legítima en la misma categoría no infla `applicable` (10, no 11) ni puede
  aparecer en `executed`.
- `test_llm07_sin_ningun_caso_directo_de_fuga_no_publica_el_claim`: 20/20 ejecutados y
  bloqueados sin ningún caso `PROTECTED_SECRET_LEAK` → `SUPPRESSED` con el blocker
  "sin evidencia suficiente", no un claim de 100%.
- `test_el_informe_publica_el_claim_con_cobertura_completa`: con al menos un caso
  directo de fuga cubierto al 100%, el claim se publica normalmente (no regresión).

Suite completa: 852/852 en verde.

### Funcional (suite real contra el backend en vivo)

```
make suite SUITE_ENDPOINTS="proxy" PROXY_PROFILES="full" REPEAT=1 \
  ARGS="--id atk_030 --id leg_002_bloqueo_tarjeta_propia"
FIXTURES_DIR=/app/tests/fixtures python scripts/evaluate.py --run <folder> --force
FIXTURES_DIR=/app/tests/fixtures python scripts/report.py   --run <folder> --force
```

- `coverage-plan.json["applicability"]` contiene la decisión completa por fixture ×
  target (`orphans: []`, dos fixtures con `APPLICABLE`/`proxy-full`) — confirmado que
  ya se persistía correctamente antes de este PR.
- `category_claims` publica `proxy-full/LLM01` (el ataque, 1/1) y **no** genera ninguna
  entrada para la categoría del fixture legítimo — confirma que el tráfico legítimo ya
  no contamina el denominador de contención por categoría.
- `planned_total == total == 2` en este run sin errores; la fila condicional de
  "Total planificado" correctamente no aparece (solo se muestra cuando diverge).

## Fuera de alcance (anotado, no resuelto en este PR)

- **Gates jerárquicos como abort duro del sellado.** El informe pide que "el sellado
  falle si un fixture en alcance queda huérfano sin decisión explícita". La
  arquitectura actual (`decide()` se llama para cada par fixture×target sin
  excepción) ya garantiza que ningún fixture queda sin decisión — el hueco real era
  solo la falta de persistencia, corregida arriba. Convertir un huérfano legítimo (0
  targets aplicables, decisión `NOT_APPLICABLE` explícita) en un abort duro del
  runner es un cambio de mayor radio de impacto (puede detener corridas válidas) que
  no se pudo validar con seguridad en el tiempo disponible de este PR; queda como
  seguimiento con su propio diseño de escape hatch (`--allow-orphans` o similar).
- **Poblaciones tipadas completas (`APPLICABLE`/`NOT_APPLICABLE`/`EXCLUDED` con
  responsable/issue/vigencia) para la exclusión declarada.** El esquema del manifiesto
  ya modela `owner`/`issue`/`expires`, pero ningún fixture del catálogo actual usa la
  vía `EXCLUDED` — no hay caso real que ejercite ese camino todavía.
