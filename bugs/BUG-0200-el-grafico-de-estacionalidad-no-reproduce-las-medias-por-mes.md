---
id: BUG-0200
title: El gráfico de estacionalidad no reproduce las medias por mes de calendario — en el IPC español pinta enero −0.87, julio −0.22 y diciembre −0.76 donde las medias son −1.15, −0.81 y −0.11
status: fixed
severity: medium
component: seasonality
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-02
reporter: David / Claude — evaluación del carril autónomo (IPC_ES del pass-through)
tags:
  - seasonality
  - figura
references:
  - src/art/seasonal_detection.py — dummies desde los armónicos vía A0 (≈274), plot_seasonality (≈329)
  - docs/STUDY-autonomous-lane-and-the-domain.md §5
---

## Summary

`guided_identification(IPC_ES, lam=0, d=1)` (llamada 3) pinta el patrón
estacional de ∇100·ln IPC_ES. Sus barras no son las medias por mes de
calendario (desviaciones respecto a la media global), que son las clásicas del
IPC español — rebajas de enero y julio, abril y octubre al alza:

| mes | gráfico | media real |
|---|---|---|
| ene | −0.87 | −1.15 |
| feb | −0.47 | −0.11 |
| mar | +0.44 | +0.39 |
| abr | +0.54 | +0.90 |
| may | +0.54 | +0.10 |
| jun | −0.27 | −0.01 |
| jul | −0.22 | −0.81 |
| ago | −0.22 | +0.04 |
| sep | +0.41 | −0.01 |
| oct | +0.49 | +0.63 |
| nov | +0.38 | +0.07 |
| dic | −0.76 | −0.11 |

No es una rotación de etiquetas: parece una versión suavizada o con otra fase.
La serie empieza en 02/2002 (el ∇, en 03/2002).

## Impact

Medio. La detección (F-HAC) y la decisión no cambian, pero el gráfico es lo
que el analista mira para LEER la estacionalidad (qué meses, cuánto), y aquí
desaparecen las rebajas de julio y aparece una caída en diciembre que no existe.

## Reproduction

`levels_2002_2019.csv`, columna IPC_ES, freq=12, inicio 02/2002;
`guided_identification(..., lam=0, d=1)`. Las medias reales:
`(100*log(y)).diff()` agrupado por mes, menos su media.

## Root cause

Por investigar. Candidatas: la fase de los armónicos respecto al mes de la
primera observación de ∇ (la serie no empieza en enero) en `_generate_A0_matrix`
o en la regresión; o el mapeo γ → ω.

## Fix

Que las barras sean las medias por mes de calendario del ajuste (con la fase
correcta), y un test que las compare con las medias directas en una serie que
no empiece en enero.

## Validation

Test: serie sintética con patrón conocido que empieza en un mes distinto de
enero; las barras deben reproducirlo.

## Resolution (2026-10-02)

**Root cause, measured: two things, only one of them a defect.**

1. **Phase (the defect).** `detect_seasonality` returned the effects in
   SAMPLE order: `dummies[i]` belongs to time t=i+1, the period in which the
   series starts. `plot_seasonality` labelled them Jan…Dec. IPC_ES starts in
   02/2002, so every bar was one month off: the bar labelled «Jan −0.87» was
   February.
2. **What the bars measure (not a defect).** The regression uses harmonics in
   LEVELS, differenced with the series, so the bars are the seasonal effect
   on the level 100·ln y, estimated on ∇^d. They are not the means of ∇ by
   month; the means are the differences between consecutive bars.

Once rotated, IPC_ES reads:

| Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| −0.76 | −0.87 | −0.47 | +0.44 | +0.54 | +0.54 | −0.27 | −0.22 | −0.22 | +0.41 | +0.49 | +0.38 |

This matches a regression on calendar dummies exactly. The report's
expectations come back as differences:
- Jan − Dec = −1.14 (∇ mean −1.15): the January sales;
- Jul − Jun = −0.81 (∇ mean −0.81): the July sales;
- Apr − Mar = +0.91 (∇ mean +0.90).

**Fix.**
- `detect_seasonality` rotates `dummies` and `dummy_se` to calendar order,
  using `ts.start[1]`, so every consumer reads them alike. It falls back to
  sample order when the start is unknown.
- The title says «Seasonal effect on the level».

**Validation:** `tests/test_bug_0200_fase_del_grafico_estacional.py`:
- a known level pattern, starting in Jan, Feb, Jul and Dec, with d=0 and
  d=1, is recovered in calendar order;
- the reported case starts in February;
- the title says «level».

