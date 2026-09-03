---
id: BUG-0075
title: el conjunto de retardos del Ljung-Box empieza en s/2 —1 grado de libertad— y no llega a f·3+3, así que `min(q_pvalues)` decide sobre el punto más frágil
status: fixed
severity: high
component: diagnosis
found_in: 0.1.12
fixed_in: 0.2.0 (unreleased)
reported: 2026-09-03
reporter: David / run 5 guiado sobre PGAS
tags:
  - ljung-box
  - diagnosis
  - adequacy
  - convention
references:
  - src/art/diagnosis.py:503 (q_check_lags)
  - tests/test_bug_0075_q_lag_set.py
  - BUG-0074 (los grados de libertad de la etiqueta, misma sesión)
---

## Summary

```python
q_check_lags = [s // 2, s, 2 * s, 3 * s]     # estacional
q_check_lags = [6, 12, 24]                    # no estacional
```

Con datos trimestrales (s=4) eso es **[2, 4, 8, 12]**. Dos problemas:

**Empieza en el retardo 2.** Tras restar el parámetro ARMA quedan **1 grado de
libertad**. Es el punto más frágil del conjunto, y como el veredicto de ruido
blanco se toma con `min(q_pvalues)`, **es el que decide casi siempre**.

**No llega al punto de decisión.** La convención para datos trimestrales y
mensuales es **f·3+3** retardos — 15 para trimestral, 39 para mensual — y aquí
se para en `3s = 12`. Para series anuales o sin estacionalidad, 10.

**Y el propio motor no está de acuerdo.** El `.out` de `fue` sobre el mismo
modelo reporta el Ljung-Box en **{4, 8, 12, 15}**, con sus DF corregidos:

```
   4  ...   4.98   3
   8  ...  10.42   7
  12  ...  13.76  11
  15  ...  15.27  14      ← f·3+3, y no está en la lista de Python
```

La diagnosis de Python y el motor en C evalúan la adecuación **en sitios
distintos**.

## Repro — el caso que lo destapó

PGAS, dos especificaciones rivales de la misma intervención:

| | Q(2) *(lo que decidía)* | **Q(15) df=14** *(la convención)* |
|---|---|---|
| 4 escalones | 0,0655 ✓ | 15,27 → **0,3599 ✓** |
| 3 impulsos (ω(1)=0) | **0,0392 ✗** | 14,10 → **0,4421 ✓** |

Con el retardo 2 la forma simplificada **se descarta por inadecuada**. Con la
convención **es la mejor de las dos**. El veredicto se invierte, y la
simplificación —que además gana en BIC, en JB y en un parámetro— se habría
perdido.

Es Portmanteau: hasta cierto punto el número de retardos es arbitrario, y
mirarlos todos siempre es bueno. Pero **el punto en el que se decide** no puede
ser el de 1 grado de libertad.

## Fix

`q_check_lags` sigue la convención y **coincide con la del motor**:

- estacional: `[s, 2s, 3s, 3s+3]` → trimestral {4, 8, 12, **15**}, mensual
  {12, 24, 36, **39**}
- no estacional o anual: `[5, 9]`, con el punto de decisión en **9** — que es
  la convención del propio motor: `_default_lags_fug` devuelve 9 para `freq=1`
  porque es lo que hace `diagnose.c` de `fug`

Se retira `s//2`. Los retardos cortos siguen visibles en el `.out` y en el
gráfico; lo que cambia es **dónde se decide**.

## Test

`tests/test_bug_0075_q_lag_set.py` — exige que el último retardo sea f·3+3 en
estacional y 9 en no estacional, que `s//2` no esté, y que el conjunto
coincida con el del `.out` del motor.
