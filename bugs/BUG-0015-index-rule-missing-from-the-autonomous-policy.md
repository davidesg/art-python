---
id: BUG-0015
title: The INDEX RULE that forces lambda=0 on a price index exists only in the guided MCP layer, so the autonomous pipeline splits one family of CPI indices between logs and levels on the sign of a near-zero statistic
status: fixed
severity: high
component: policy
found_in: 0.1.5
fixed_in: 0.1.11 (unreleased)
reported: 2026-08-08
reporter: David / IPC-WTI passthrough, 8-country batch
tags:
  - policy
  - boxcox
  - lambda
  - silent-failure
  - autonomous
references:
  - src/art/policy.py:46-53 (`decide_lambda`: `gap >= 0 ? log : identity`, and nothing else)
  - src/art/mcp_server.py (the index rule, printed by `guided_identification` as "REGLA ÍNDICE APLICADA")
  - src/art/pipeline.py:731-732 (`run_full`: `lam = pol.decide_lambda(bc.data)` — the only door)
  - bugs/BUG-0013-autonomous-pipeline-can-never-estimate-mu.md (same architecture, different decision)
  - bugs/BUG-0015-repro/
---

## Summary

`guided_identification` applies, and announces, a domain rule:

> ⚠ **REGLA ÍNDICE APLICADA:** «IPC_ES» es una serie índice sin base natural —
> se impone **λ=0 (log)** independientemente de las estadísticas Box-Cox.

`policy.decide_lambda`, which is what `run_full` — and therefore `build_model`
and `batch_build` — actually calls, is the whole of it:

```python
gap = boxcox_data.get("gap", 0.0)
return 0.0 if gap >= 0 else 1.0
```

No index rule, and `build_model` exposes no way to supply one. Same shape as
BUG-0013: **a decision the guided layer makes and the autonomous path has no
door to ask for.**

`gap = corr(raw) − corr(log)` of the mean–std scatter over 18 annual groups. On
a CPI index both correlations are small and unstable, so the SIGN — which is
what decides the transformation — is close to a coin flip.

## Reproduction

```
python3 bugs/BUG-0015-repro/repro.py      # exits 1 while the bug is live
```

Eight monthly CPI indices, one source file, one window (2002-01…2019-12,
n=216), same nature:

```
  series      corr(raw)   corr(log)      gap    policy lambda   index rule wants
  IPC_ES         0.269       0.541    -0.272      LEVELS (1)           log (0)
  IPC_FR         0.045       0.309    -0.264      LEVELS (1)           log (0)
  IPC_DE         0.668       0.540    +0.129         log (0)           log (0)
  CPI_USA        0.109       0.329    -0.220      LEVELS (1)           log (0)
  EMU            0.401       0.096    +0.304         log (0)           log (0)
  IPC_JP         0.171       0.147    +0.023         log (0)           log (0)
  IPC_CA         0.083       0.334    -0.251      LEVELS (1)           log (0)
  IPC_UK         0.226       0.095    +0.132         log (0)           log (0)

  policy: 4 in logs, 4 in LEVELS.   index rule: 8 in logs.
```

**Four and four**, and `IPC_JP` sits at `gap = +0.023` — one hair from flipping.
`|gap|` never exceeds 0.304 anywhere. Nothing in the data says these eight series
differ in kind; the statistic says so, barely, and the policy obeys the sign.

Confirmed end to end through `build_model` / `batch_build` on the same files:
IPC_ES, IPC_FR, CPI_USA and IPC_CA come back with `λ=1` and coefficients in index
points (`+10.081 (−1)^t`, `σ̂ₐ = 22.82`), the rest in logs.

## Resolution (2026-08-12) — junto con BUG-0016, como este informe exigía

**`decide_domain` es la séptima decisión del protocolo `Policy`**, y cierra el
hueco general que este informe identificó: *«la política toma evidencia pero
nunca dominio»*. Es la misma forma que BUG-0013 y se arregla con la misma
plantilla.

```python
domain = pol.decide_domain(ts)          # price_index | generic
lam    = pol.decide_lambda(bc.data, domain)
```

`decide_lambda(boxcox_data, domain=None)` devuelve λ=0 cuando el dominio es
`price_index`, diga lo que diga la estadística. `PipelineResult.domain` registra
lo decidido y `build_model(domain=…)` / `ClaudePolicy(domain=…)` lo declaran.

### Declarado gana a inferido

El detector infiere del NOMBRE, que es evidencia débil — un modelo no puede salir
distinto porque el fichero se llamara `IPC_ES` en vez de `serie3`. Dos cosas lo
mantienen honesto: la respuesta **se registra** en vez de aplicarse en silencio,
y **lo declarado gana siempre**. La inferencia existe para que el camino autónomo
no se quede sin nada, no porque el nombre sea buena evidencia.

**Y el propio caso lo demuestra:** `EMU` sale del detector como `generic` — es un
índice de precios y su nombre no lo dice. Acaba en logs sólo porque su gap es
+0.304. Es exactamente el argumento para poder declararlo.

### Una copia de la regla, no dos

La regla vivía dentro de `guided_identification` con su propia tupla de prefijos.
Ahora esa capa llama a `policy.decide_domain(ts)`: `_INDEX_PREFIXES` aparece
**cero veces** en `mcp_server.py`. Tener el criterio escrito dos veces, y sólo uno
de los dos corriendo en el camino autónomo, ERA el defecto.

### Medido

`bugs/BUG-0015-repro/repro.py` sale con 0. Y de punta a punta por `run_full`:

```
serie     dominio         λ  d  D  dec      μ
IPC_ES    price_index   0.0  1  0   B1   True
IPC_FR    price_index   0.0  1  0   B1   True
IPC_DE    price_index   0.0  1  0   B1   True
CPI_USA   price_index   0.0  1  0   B1   True
EMU       generic       0.0  1  0   B1   True
IPC_JP    price_index   0.0  1  0   B1  False
IPC_CA    price_index   0.0  1  0   B1   True
IPC_UK    price_index   0.0  1  0   B1   True
```

Las ocho en logs (antes 4 y 4) y las ocho con d=1 (antes dos con d=2). Y IPC_JP
sigue sin media, que es el control de BUG-0013 intacto.

Tests: `tests/test_bug_0015_0016_policy_domain_and_d_cap.py`, 23 tests para los
dos informes. Contra el código previo fallan 20.

## Impact

Three levels, and the third is what makes it a defect rather than a preference.

1. **A level model of an index has no interpretable scale.** The base year is a
   convention (here 2016=100). Only relative changes carry meaning, which is the
   whole content of the index rule.

2. **It breaks the comparison the batch exists to make.** In a transfer function
   against a log input, a log output gives an ELASTICITY and a level output a
   semi-elasticity. The four countries in levels cannot be put in the same table
   as the four in logs — and nothing warns you, because each model is internally
   fine.

3. **It is silent.** Q, Jarque-Bera and the residual-mean test added by BUG-0013
   all pass on the level models. The check that closed BUG-0013's silence does
   not cover this one: a wrong transformation does not show up as a non-zero
   residual mean.

## Root cause

Structural, and identical to BUG-0013's layer 1. The `Policy` protocol declares
`decide_lambda(boxcox_data)` and passes it **only the Box-Cox statistics**. The
index rule needs something the signature cannot carry: what KIND of series this
is. So the rule could not be implemented in the policy even if someone wanted
to — there is no argument to hold the answer.

This is now the third decision found on the wrong side of that line
(μ — BUG-0013; the AR/MA tie-break for price series — already in `TODO.md`;
λ — here). They share a cause: **the policy protocol takes evidence but never
domain.**

## Fix

The narrow fix and the general one point the same way.

- **Narrow:** give `decide_lambda` the series identity it already has upstream —
  `run_full` holds `ts`, and `ts.name` is what the guided rule keys on — and move
  the index rule into the policy so both paths share it. Expose `lam` on
  `build_model` (it already is) *and* a domain marker so a caller can assert
  "this is an index" instead of hoping the heuristic guesses.

- **General:** add a domain/kind field to whatever the policy receives, and route
  the three known domain rules through it. `TODO.md` already asks for exactly
  this for the AR/MA tie-break — "decide_orders no recibe la marca de dominio de
  la serie" — so one change closes both.

Until then, the honest interim is for the autonomous path to **say** it could not
apply the rule: if the series looks like an index (name, scale near 100, positive
drift, no natural zero) and the heuristic chose λ=1, warn.

## Validation

- `bugs/BUG-0015-repro/repro.py` must return 0: all eight in logs.
- Guard the other direction — a series that genuinely wants λ=1 (a rate, a
  temperature, anything with a natural zero and no base convention) must not be
  forced into logs by an over-broad rule. The repro covers only the index case,
  deliberately; a fix that logs everything would pass it and be wrong.
