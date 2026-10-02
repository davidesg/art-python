---
id: BUG-0200
title: El gráfico de estacionalidad no reproduce las medias por mes de calendario — en el IPC español pinta enero −0.87, julio −0.22 y diciembre −0.76 donde las medias son −1.15, −0.81 y −0.11
status: open
severity: medium
component: seasonality
found_in: 0.2.3.dev0
fixed_in:
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
