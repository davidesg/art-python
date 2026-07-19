---
id: BUG-0004
title: ar_factorization should return standard errors for damping d and period (delta method)
status: fixed
severity: low
component: roots
found_in: 0.1.1
fixed_in: 0.1.2
reported: 2026-07-09
reporter: D. E. Guerrero
tags:
  - enhancement
  - roots
  - standard-errors
references:
  - src/art/roots.py (Factorization; damping r, period)
  - /home/david/Dropbox/Cycles/caracterizar_operadores.py
  - /home/david/Dropbox/Cycles/ABTreadway-Dperar2.xls
  - /home/david/Dropbox/Cycles/bugs_art_fue.md (ENH #5)
---

## Summary

**Enhancement (not a defect).** `ar_factorization` correctly computes, for each
complex AR(2) factor, the damping `d`, the frequency and the period — matching
`caracterizar_operadores.py` on GE/GEP/ZU — but it returns **no standard errors**
for those statistics. The SEs are needed to report cycles in the research (is a
period/damping significantly different?).

## Impact

Cycles cannot be reported with uncertainty from the tool; the user falls back to
`caracterizar_operadores.py` (repo root), which already characterises the cycles
of the three definitive models (GE days AR(7), GEP AR(5), ZU AR(6)) but is a
separate script.

## Reproduction

Call `ar_factorization` on a model with complex AR(2) factors: the damping and
period are returned without SEs.

## Root cause

`src/art/roots.py` computes point estimates of `r`/period from the factor
coefficients but never propagates the parameter covariance into them.

## Fix

**Applied** in 0.1.2.  Ported `caracterizar_operadores.car_ar2` into
`src/art/roots.py` as `complex_factor_se(a1, a2, cov, excel_compat=False)` (the
delta method: `var(d)=var(a₂)/(4·(−a₂))`; `var(per)` via `∂per/∂a₁`, `∂per/∂a₂`
using the sign-consistent `w`, with an `excel_compat` flag for the Excel's
`arccos(|t|)`).  `factor_ar(..., cov=...)` attaches `se_r`/`se_period` (and
`half_life`) to a directly-estimated AR(2) factor; `describe()` prints `d ± SE`,
`per ± SE` when present.  `ar_factorization` extracts each AR(2) factor's 2x2
sub-block from the fitted parameter covariance (`m._result.cov_matrix`, aligned
with `m.params` via the same index walk that reconstructs the coefficients) and
passes it through.  Higher-order (unfactored) operators, whose sub-factors are
derived from the polynomial roots, are left without SEs (no single coefficient
covariance) — unchanged output.

## Validation

- `complex_factor_se(-0.146222, -0.26976, V, excel_compat=True)` → `se_d=0.11984`,
  `se_per=0.38194`, matching ABTreadway-Dperar2.xls (0.119839 / 0.381938).
- `ar_factorization` on GE.3 (AR(7) factored) → cycles `~7y 6.89 ± 0.42`,
  `~3.6y 3.63 ± 0.14`, `~2.3y 2.32 ± 0.05`, i.e. the SEs (2–7 % relative) reported
  by `caracterizar_operadores.py`.
- Regression test `tests/test_bug_0004_factor_se.py` (Excel parity, consistent-vs-
  Excel derivative, cov attaches SEs, no cov → no SEs, higher order ignores cov,
  `describe` shows `±`).  roots.py self-test still passes.
