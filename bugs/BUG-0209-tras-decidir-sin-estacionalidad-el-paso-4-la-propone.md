---
id: BUG-0209
title: Tras decidir «sin estacionalidad» (D=0, sin armónicos), el paso 4 de guided_identification propone candidatos SARIMA estacionales y sugiere n_harmonics=5
status: fixed
severity: medium
component: identification
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - identificacion
  - estacionalidad
  - contradiccion
references:
  - src/art/mcp_server.py (guided_identification, Call 4)
  - bugs/BUG-0208-repro/repro.py
---

## Summary

Con una serie desestacionalizada (IPC_US, F-HAC p=0,78, «Decisión A»: sin estacionalidad), el
paso 4 lista candidatos con parte estacional —(0,1,1)(0,0,1)₁₂, (0,1,1)(1,0,0)₁₂…— y su
«próximo paso» sugiere `n_harmonics=5`. En IPC_US el primero por AICc era el (0,1,1)(0,0,1)₁₂.
En Salamanca, la justificación del AR(4) habla de «estacionalidad híbrida en f=3» con el F-HAC
sin rechazar.

## Impact

El analista autónomo tiene que descartar a mano lo que el nodo anterior ya decidió; un alumno en guiado puede tomar la sugerencia y meter armónicos en una serie desestacionalizada.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0209: `guided_identification('IPC_US.inp', lam=0, d=1, D=0, domain='price_index')`.

## Root cause

El paso 4 no recibe (o no respeta) la decisión estacional del paso 3 cuando D=0 y no hay armónicos.

## Fix

Con D=0 y sin estacionalidad detectada, el listado debe restringirse a candidatos sin parte estacional y el próximo paso no debe sugerir armónicos.

## Validation

Repro, bloque 0209: ningún candidato con (P,0,Q)₁₂ ≠ (0,0,0) y sin `n_harmonics=5`.

## Resolution (2026-10-06)

**Fix.** Step 4 of `guided_identification` (D=0, no `pre_path`) now repeats
step 3's own seasonality test (`detect_seasonality` with the same defaults
`describe_seasonality` uses) and passes the decision to
`describe_identification(estacional=...)`. With Decision A the search runs with
`P_max=Q_max=0` and `n_harmonics=0`, so no candidate has a seasonal part and no
harmonics are removed that the model will not carry. The recommendation says
"Decisión A del nodo 3 (sin estacionalidad): sin armónicos" and names ARIMA,
not SARIMA. The next step carries `n_harmonics=0, seasonal=False`. The
high-order AR note no longer reads an isolated PACF bar as "estacionalidad
híbrida" when step 3 found none. With seasonality detected the B1 wording is
now definite. `estacional=None` keeps the old text.

The repro (block 0209) now prints `n_harmonics=5: False · candidatos: []`
(IPC_US: (0,1,1), (2,1,0), (1,1,1), (2,1,1), (1,1,0), all (0,0,0)_12).

**Validation:** `tests/test_bug_0209_sin_estacionalidad_sin_candidatos_estacionales.py`:
- a non-seasonal synthetic series: no (P,0,Q)_12 ≠ (0,0,0), no
  `n_harmonics=5`, `n_harmonics=0, seasonal=False` in the next step;
- `suggest_orders` is called with P_max=Q_max=n_harmonics=0;
- a seasonal series still gets route B1 with `n_harmonics=5`;
- `estacional=None` keeps the two-branch text.

`identification_analysis` takes the same decision (`_estacional_del_nodo3`,
shared with node 4), so the standalone listing no longer offers seasonal
candidates on a series without seasonality either.
