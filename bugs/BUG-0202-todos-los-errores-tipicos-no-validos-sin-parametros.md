---
id: BUG-0202
title: «TODOS los errores típicos de arriba NO son válidos» en un modelo que no tiene ningún parámetro
status: fixed
severity: low
component: diagnosis
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-02
reporter: David / Claude — evaluación del carril autónomo (WTI del pass-through)
tags:
  - covarianza
  - avisos
references:
  - src/art/mcp_server.py, _equation_for_prompt (≈1449) — cuantos = "TODOS los" if (not idx or len(idx) >= npar)
  - BUG-0124 (la lista única)
---

## Summary

El modelo base de WTI (ARIMA(0,1,0), sin μ ni deterministas: cero parámetros)
sale con:

    ⚠ **TODOS los errores típicos de arriba NO son válidos** (niter=None): provienen
    de la semilla del BFGS …

No hay ningún error típico arriba. El aviso entra porque
`covariance_is_degenerate` es verdadero con `niter` nulo y `cov_matrix`
presente, y con `npar = 0` la condición `len(idx) >= npar` se cumple.

## Impact

Bajo: ruido en la salida del modelo base, que es el primer modelo de cualquier
análisis; enseña al analista a ignorar el aviso.

## Reproduction

`confirm_and_estimate(WTI.inp, lam=0, d=1, D=0, p=0, q=0, n_harmonics=0,
seasonal=False, estimate_mu=False)`.

## Fix

Con `npar == 0` no hay aviso de covarianza.

## Validation

Test: modelo sin parámetros, sin aviso.

## Resolution (2026-10-03)

**Fix at the source.** `covariance_is_degenerate` returns False when the
result has no parameters (`npar`, or `len(params)`, is 0), before any seed
check. The five callers inherit it:
- the equation's warning;
- the correlation tool;
- `test_intervention`, twice;
- the summary.

The cause was as the report says: fue returns `niter=None` (read as 0) and
`cov_matrix=[]` (empty, but not `None`) for a model with nothing to
estimate.

**Validation:** `tests/test_bug_0202_sin_parametros_sin_aviso.py`:
- with no parameters the covariance is not degenerate;
- the BUG-0027 gate still fires with parameters and `niter=0`;
- the WTI base model, ARIMA(0,1,0) without μ, comes out without the warning.

