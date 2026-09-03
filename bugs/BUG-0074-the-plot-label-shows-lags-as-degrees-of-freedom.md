---
id: BUG-0074
title: la etiqueta Q(·) del gráfico de correlograma muestra el número de RETARDOS donde debería ir los grados de libertad — no resta los parámetros ARMA
status: fixed
severity: medium
component: identification
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-03
reporter: David / run 5 guiado sobre PGAS
tags:
  - ljung-box
  - degrees-of-freedom
  - presentation
  - correlogram
references:
  - src/art/identification.py:170 (asignación) y :459 (la etiqueta)
  - tests/test_bug_0074_q_label_degrees_of_freedom.py
  - BUG-0075 (el conjunto de retardos, encontrado en la misma sesión)
---

## Summary

```python
ljung_box_stat=float(lb["statistic"][-1]), ljung_box_df=int(lb["lags"][-1])
```

`lb["lags"][-1]` es el número de **retardos**, no los **grados de libertad**. La
etiqueta del gráfico lo imprime como si lo fuera:

```
Q(15) = 15.3
```

Los grados de libertad de un Ljung-Box sobre residuos de un modelo estimado son
`retardos − nº de parámetros ARMA libres`. Con un AR(1) son **14**, no 15.

`ljung_box()` recibe y aplica `df_correction=npar` correctamente para los
p-valores; lo que está mal es sólo el campo que alimenta la etiqueta.

## Repro

Sobre PGAS m20 (ARIMA(1,1,0) + 1 intervención, n=83):

| | |
|---|---|
| etiqueta del gráfico | `Q(15) = 15.3` |
| `.out` del motor en C | `15.27  14` — estadístico **y DF**, correctos |
| p con df=15 (lo que invita a leer la etiqueta) | 0,4321 |
| p con df=14 (correcto) | 0,3599 |

Aquí las dos lecturas coinciden en el veredicto, pero el rótulo es erróneo
siempre y en un caso de frontera decidiría al revés.

## Cause

Confusión entre dos cantidades que en un Ljung-Box **sin** corrección
coinciden. Sobre residuos de un modelo estimado no coinciden nunca.

## Fix

`ljung_box_df = lags − npar`, tomando `npar` del mismo sitio que ya usa
`ljung_box()` para corregir los p-valores. El `.out` del motor ya lo hacía
bien: la discrepancia entre las dos salidas era la señal.

## Test

`tests/test_bug_0074_q_label_degrees_of_freedom.py` — exige que el `df` de la
etiqueta sea `lags − npar` y que coincida con la columna DF del `.out`.
