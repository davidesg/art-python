---
id: BUG-0219
title: Escalas y rótulos: la media de ln z se presenta en % («w̄ = 429,39 %») y el histograma de residuos rotula «%» un eje que es una densidad (barras de más del 100 %)
status: fixed
severity: low
component: figuras
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - figuras
  - presentacion
  - escalas
references:
  - src/art/describe.py (figura del paso 2)
  - fue: plots (histograma)
---

## Summary

- Figura de la serie en log (paso 2 de `guided_identification`): «w̄ (σ̂w̄) = 429,39 % (0,66 %)»
  para ln ES_CPI; 857,15 % para ln Salamanca. Un nivel en logaritmos no se expresa en %.
- Histograma de residuos (Ciudad Lineal, Moratalaz): eje rotulado «%», barra central por encima
  del 100 %.

## Impact

Cifras sin sentido delante del alumno.

## Reproduction

`guided_identification(<serie>.inp, lam=0)` (figura del paso 2); `model_histogram` de un residuo muy concentrado.

## Root cause

El rótulo en % aplica el factor 100 del λ=0 también al nivel; el histograma usa density=True con rótulo de frecuencia.

## Fix

No dar en % la media de un nivel en log (o no darla); rotular «densidad».

## Validation

Las dos figuras.

## Resolution (2026-10-06)

**Fix.** Both labels come from pyfug, which follows fug C's convention (the
plotted series is a rate; the histogram is 100·density). Art now corrects the
figures pyfug returns, without changing pyfug:
- `_plot_series_at_d` (steps 2 and 3): unless λ=0 and d≥1, the
  "w̄ (σ̂w̄) = …" line is rewritten with the same statistics in the series' own
  scale, without % (`describe._estadisticos_sin_porcentaje`). ln IPC_ES now
  shows "w̄ (σ̂w̄) = 4.46 (0.006557)  σ̂w = 0.09637".
- The residual histogram (`describe_diagnosis` → `model_histogram`,
  `confirm_and_estimate`; and `diagnosis.plot_diagnosis_histogram`): bars and
  normal curve ÷100, axis "densidad" (`describe._histograma_en_densidad`). The
  normal peaks at 0.399 and the bars have area 1.

**What should change in pyfug:** `graphics/fugplot.py::statistics()` should take
`percent=` (passed through `plot_combined` and `plot_series`), and
`graphics/histogram.py::plot_histogram()` should plot density or label the
axis honestly. Once it does, art's two helpers can be removed.

**Validation:** `tests/test_bug_0219_escalas_y_rotulos.py`: no % on a log level
or on an unlogged series, % kept on ∇ln; histogram labelled "densidad" with
area 1 and normal peak 0.399, both in `describe_diagnosis` and
`plot_diagnosis_histogram`.

Not covered: the step-4 ACF/PACF figure and the residual figures of λ≠0
models still show pyfug's %.

**pyfug 2.0.2 (2026-10-06).** The pyfug side is done (pyfug/BUG-0008):
`plot_series`/`plot_combined(percent=)` and `plot_histogram(density=)`. art
dropped the two helpers that rewrote pyfug's figures and passes the rule
(`describe._en_porcentaje`): % only for a rate, λ=0 with d+D ≥ 1 (and model
residuals when λ=0); the histogram as a density. It covers the five series and
residual figures (steps 2–4, the identification listing, the residual figure),
so the step-4 and λ≠0 residual figures no longer show pyfug's %. art requires
`pyfug>=2.0.2`.
