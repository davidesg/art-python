---
id: BUG-0004
title: ar_factorization should return standard errors for damping d and period (delta method)
status: open
severity: low
component: roots
found_in: 0.1.1
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

Let `ar_factorization` optionally accept the factor parameter covariance matrix
and return `d ± SE` and `period ± SE` by the **delta method**, replicating
`ABTreadway-Dperar2.xls`:

- `d = √(−a₂)`;  `var(d) = var(a₂) / (4·(−a₂))`
- `per = 2π / arccos(a₁ / (2d))`;  `var(per)` by delta with `∂per/∂a₁`, `∂per/∂a₂`

(Note: the Excel uses `arccos(|t|)` in the derivative — sign-inconsistent;
`caracterizar_operadores.py` has the consistent version to follow.)

## Validation

Compare `d ± SE`, `period ± SE` against `caracterizar_operadores.py` /
`ABTreadway-Dperar2.xls` on GE/GEP/ZU. Until implemented,
`caracterizar_operadores.py` covers the need.
