---
id: BUG-0205
title: El intervalo al 95 % de la tabla de previsión sale simétrico en nivel en modelos en logaritmos — es la aproximación del método delta, no exp(ŷ ± 1,96 s); a 24 meses del airline, [383, 668] frente a [401, 689]
status: wontfix
severity: low
component: mcp-tools
found_in: 0.2.3.dev0
reported: 2026-10-04
reporter: David — preparación de la sección 2.3 (previsión) de Econometría Aplicada
tags:
  - forecast
  - box-cox
  - presentation
  - known-limitation
references:
  - src/art/mcp_server.py::_forecast_table (BUG-0008: se_abs = level_std · level^(1−λ))
  - bugs/BUG-0008-forecast-table-builds-the-95-band-as-level-1-96-.md
---

## Summary

`generate_forecast` publica una tabla «IC 95% (±1.96·s.e.)» que, para un modelo con
λ = 0, construye la banda en **nivel** como `level ± 1,96 · level · s`, donde `s` es el
error típico de ln y (método delta, corrección de BUG-0008). Es una aproximación de
primer orden: el intervalo correcto se construye en la escala del modelo y se
transforma, `[exp(ŷ − 1,96 s), exp(ŷ + 1,96 s)]`, y sale **asimétrico** —más ancho
hacia arriba—. La diferencia crece con `s`, es decir, con el horizonte.

## Impact

Bajo, y conocido. Es el precio de una tabla sencilla: una sola columna de intervalo,
legible por el asistente. A horizonte corto apenas se nota; a horizontes largos o con
σ̂ₐ grande, el límite inferior sale por debajo del correcto y el superior por encima
del simétrico. El informe HTML de previsión (las desviaciones típicas en % por escala)
y los gráficos **no** están afectados: el defecto es sólo de esta columna.

## Reproduction

Pasajeros aéreos (serie G), airline (0,1,1)(0,1,1)₁₂ sobre ln, origen 1960:12:

```
art> generate_forecast(inp_path=AIRLINE_m01.pre, horizon=24, ...)
```

| h | Previsión | Tabla de art (simétrico) | exp(ŷ ± 1,96 s) |
|---|---:|---|---|
| 1 | 450,4 | [418,0, 482,8] | [419,1, 484,0] |
| 12 | 477,2 | [400,9, 553,5] | [406,7, 560,0] |
| 24 | 525,4 | [382,9, 668,0] | [400,6, 689,3] |

(s = 0,0367, 0,0816, 0,1384; comprobado en gretl con `fcast` y `$fcse`.)

## Root cause

`_forecast_table`: `lo, hi = lvl ∓ 1.96 * se_abs`, con `se_abs = level_std · level`
para λ = 0. Simétrico por construcción.

## Fix

**No se corrige** (decisión de David, 4-oct-2026): se mantiene la tabla simple. Queda
registrado para que el comportamiento esté documentado y no se tome por correcto. Si
algún día se cambia, la línea es `lo, hi = exp(ln lvl ∓ 1,96 s)` para λ = 0 (y la
inversa de Box-Cox en general), y la cabecera debería dejar de decir «±1.96·s.e.».

## Validation

En la docencia, la sección 2.3 enseña el intervalo asimétrico con estas mismas cifras
y advierte de que el simétrico es la aproximación.
