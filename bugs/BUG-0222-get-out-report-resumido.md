---
id: BUG-0222
title: Mejora: get_out_report devuelve el .out entero (≈ 40 KB); falta un modo resumido para el carril autónomo
status: fixed
severity: low
component: mcp-tools
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - mejora
  - autonomo
  - contexto
references:
  - src/art/mcp_server.py (get_out_report)
---

## Summary

`get_out_report` devuelve el `.out` completo, con la serie tipificada línea a línea y la calibración de la FAS: unos 40 KB por llamada.

## Impact

En autónomo se llama decenas de veces para leer tres cifras; satura el contexto.

## Reproduction

`get_out_report` sobre cualquier `.pre` de `solucion/`.

## Root cause

No hay modo resumido.

## Fix

`resumen=True`: parámetros con e.t., σ̂ₐ, ℓ/AIC/BIC, correlaciones altas, raíces, Q en 12/24/36/39 con g.l. y p, JB, y anómalos con fecha.

## Validation

Tamaño del resumen < 3 KB con todas esas cifras.

## Resolution (2026-10-06)

**Fix.** `get_out_report(inp_path, resumen=False)`. With `resumen=True` it
returns, from the same `.out` and without re-estimating, what decides a node:
parameters with s.e. and t (named φ/Φ/θ/Θ/ω/δ/μ with their factor), σ̂ₐ,
ℓ/AIC/BIC (the formulas of fue's `model.aic`/`model.bic`), correlations
|ρ| ≥ 0.7 by name, the roots of each factor (modulus and period; annual in
B^s), Ljung-Box Q at the lags the `.out` publishes (12/24/36/39 monthly) with
d.f. and p, Jarque-Bera with p, and the outlier table with dates. The default
stays the verbatim `.out` (it is the record); the docstring and the REGISTRO
line of the instructions send the autonomous lane to `resumen=True`, decision
first (BUG-0116). The logic is `art.outfile.resumen_out`; the parser is split
into `lee_texto_out` so the no-`.out` (re-estimated) path is summarized too.

On the way: the reader read "175 observations: from 2/2011" as n = 2 (the
month after the colon). It now reads 175; BIC depends on it.

On the P02 repro data:

    Retiro  ARIMA(1,1,1)(0,1,0)12   summary 1249 B · full 38570 B
    IPC_US  AR(2)+μ                 summary 1246 B · full 41545 B

**Validation:** `tests/test_bug_0222_get_out_report_resumido.py`:
- the summary is < 3 KB and < 1/10 of the full report, and the default is
  still the full `.out`;
- every parameter with s.e. and t; AIC/BIC equal `model.aic`/`model.bic`;
- Q at 12/24/36/39 with d.f. = lag − #ARMA; JB with p; the injected outlier
  with its date; roots (annual in B^12, AR(1) root = 1/φ);
- when fue omits the outlier table (> 8σ), the summary says so instead of
  "none"; without a `.out` it summarizes the re-estimation and says so.
