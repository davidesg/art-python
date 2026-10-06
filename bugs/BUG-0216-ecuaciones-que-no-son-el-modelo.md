---
id: BUG-0216
title: Ecuaciones que no son el modelo estimado: «(1 − 0·B)» en un (0,1,0), y record_version escribe una ecuación genérica sin coeficientes, con μ o un AR que el modelo no tiene
status: fixed
severity: low
component: describe/equation
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - ecuacion
  - presentacion
  - guion
references:
  - src/art/describe.py
  - src/art/mcp_server.py (record_version)
  - bugs/BUG-0208-repro/repro.py
---

## Summary

- `confirm_and_estimate` de un (0,1,0) con μ: «(2) (1 − 0·B) (∇Nₜ − 0.1159) = aₜ».
- `record_version`: «∇[ln y_t] = μ + [1-φ(B)]⁻¹·a_t» para el (0,1,0) de IPC_DE (no hay AR),
  «∇^2[ln y_t] = [1-φ(B)]⁻¹·[1-θ(B)]·a_t» sin coeficientes para todos.

## Impact

La ecuación que queda en el guion —el registro— no es la del modelo; hay que ir al `.out`.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0216; y `record_version` sobre cualquier `.pre` de `solucion/`.

## Root cause

Plantilla de ecuación sin coeficientes en `record_version`; el factor AR vacío no se suprime.

## Fix

Usar la misma ecuación con coeficientes de `confirm_and_estimate`; omitir factores vacíos.

## Validation

Repro, bloque 0216, y la ecuación del guion de una versión adoptada.

## Resolution (2026-10-06)

**Fix.** A (0,d,0) carries a fixed AR placeholder `[0.0]` in its `.inp`.
`model_equation` now omits all-fixed-zero factors and fixed-zero terms, and
the one-line form (`_forma_estructural`: guion entry, `record_version`,
`compare_versions`) counts only factors with a real term; the stored spec is
unchanged. `record_version` shows the estimated equation with its
coefficients AND its standard errors (decision of David, 6-oct-2026: an
equation without them says nothing about which coefficient holds), plus the
one-line form. It looks at a `.pre`, whose covariance cannot be recovered by
re-estimating from the optimum (BUG-0090), so the SEs are READ FROM THE `.out`,
the record of the estimation, when its values are this model's
(`_errores_del_out`); without a matching `.out` it says so and prints none.

The report's block 0216 now prints:

    (2)  (∇Nₜ − 0.1159) = aₜ
    Forma (guion): ∇[ln y_t] = μ + a_t

**Validation:** `tests/test_bug_0216_ecuaciones_que_no_son_el_modelo.py`:
- the (0,1,0) equation has no `0·B`;
- `record_version` gives the coefficients with the `.out`'s SEs, and a guion
  form with μ and without φ(B); a `.pre` without its `.out` says so;
- a real AR(1) keeps φ(B).

With the old code all three fail. `test_frontera_del_servidor_mcp` was updated:
it pinned `_build_equation` in `record_version`; it now pins
`_errores_del_out`.
