---
id: BUG-0202
title: «TODOS los errores típicos de arriba NO son válidos» en un modelo que no tiene ningún parámetro
status: open
severity: low
component: diagnosis
found_in: 0.2.3.dev0
fixed_in:
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
