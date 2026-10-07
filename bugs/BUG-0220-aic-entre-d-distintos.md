---
id: BUG-0220
title: Se compara el AIC de modelos con distinta d sin advertir que no son comparables
status: fixed
severity: low
component: diagnosis
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - criterios
  - orden-de-integracion
references:
  - src/art/mcp_server.py (tablas comparativas, compare_versions)
---

## Summary

IPC_ES: el AIC del ARIMA(1,2,1) se pone junto al de los modelos en d=1 como si fueran comparables (la serie efectiva no es la misma).

## Impact

Invita a decidir d por el AIC, que es precisamente lo que no se puede hacer así.

## Reproduction

`compare_versions` (o la tabla del guion) con un modelo en d=1 y otro en d=2 de `solucion/IPC_ES`.

## Root cause

Las comparaciones no comprueban que d y D coincidan.

## Fix

Advertir (o separar) cuando d o D difieren.

## Validation

La comparación del caso muestra el aviso.

## Resolution (2026-10-06)

**Fix.** `compare_versions` already suppressed the Δ and the LR across
operators (BUG-0051). The gap was the guion map, which stacked logL of ∇ and
∇² models; its sample check (BUG-0177) compares the series n, which d does
not change. `guion_map` now groups the versions by (λ, d, D, ifadf)
(`_grupos_de_operador`) and, when there is more than one group, says so.

On IPC_ES_SA with ARMA(1,1) and AR(2) at d=1 and ARIMA(1,2,1) it prints:

    ⚠ El árbol mezcla operadores de diferenciación — logL, AIC y BIC sólo se comparan DENTRO de cada grupo:
       · λ=0, d=1, D=0: v1, v2
       · λ=0, d=2, D=0: v3

**Validation:** `tests/test_bug_0220_aic_entre_d_distintos.py`:
- the map warns and groups;
- `compare_versions` still suppresses the Δ;
- a single operator does not warn, and ifadf counts as a distinct operator.

The `export_guion` HTML table follows the same rule (`guion.grupos_de_operador`,
now shared by the map and the HTML): with more than one group it warns, lists
the groups by letter, and each loglik/AIC/BIC figure carries its group's
letter.

**Nota (2026-10-06).** El «IPC_ES» de este informe es IPC_ES_SA, el IPC de España *desestacionalizado* de la P02 (`bugs/BUG-0208-repro/IPC_ES_SA.inp`), no el IPC_ES histórico de BUG-0015.
