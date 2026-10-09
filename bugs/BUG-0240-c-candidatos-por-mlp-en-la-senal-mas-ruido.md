---
id: BUG-0240
title: El identificador en C (atsw-gui) acierta el 18 % del ARMA(1,1) señal + ruido (0,95/0,7) frente al 64 % de art-python: sus candidatos salen del MLP y no de los filtros de corte
status: open
severity: medium
component: identification (C)
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — batería ARIMA del identificador (ART_18/tests/benchmark_arima.py)
tags:
  - identificacion
  - c
  - atsw-gui
  - mlp
references:
  - ART_18/src/model_detection.c (MLP shortlist, add_arma_grid_candidates)
  - atsw-gui/docs/ESTUDIO-identificador.md §2, §7 (diferencias conocidas, 18.3)
  - ART_18/tests/results_arima.txt
---

## Summary

`benchmark_arima.py` (50 réplicas, n = 200, la misma serie para los tres motores):

| | C (`art_cli --mlp-direct`) | art-python (B) | pmdarima |
|---|---|---|---|
| ARMA(1,1) 0,95/0,7, 1.º / top-3 | **18 % / 38 %** | 64 % / 90 % | 48 % |
| AR(4) Salamanca | 20 % / 54 % | 0 % / 0 % (BUG-0238) | 46 % |
| media | 71 % / 80 % | 74 % / 81 % | 71 % |

Es la primera de las tres diferencias conocidas del C (ESTUDIO-identificador §2): el C toma
sus candidatos de una red neuronal (MLP) y art-python enumera los que pasan los filtros de
corte.

## Impact

En atsw-gui, la ventana de identificación no propone en primer lugar el modelo de los precios
de vivienda persistentes con ruido de medida.

## Reproduction

`cd ART_18 && python3 tests/benchmark_arima.py 50 200 2026` (fila «(1,1,1) .95/.7 sig+noise»).

## Fix

18.3: candidatos por filtros, como art-python (y, a la vez, BUG-0238, para que ninguno de los
dos pierda el AR(4)). Validar con las tres baterías del C.

## Validation

La fila del ARMA(1,1) señal + ruido del C a la altura de art-python, sin pérdida en la media.
