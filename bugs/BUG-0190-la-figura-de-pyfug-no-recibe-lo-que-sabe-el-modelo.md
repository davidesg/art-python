---
id: BUG-0190
title: La figura de residuos de pyfug no recibe lo que sólo sabe el modelo — la Q rotula retardos y no grados de libertad, la identificación sobre residuos sale ×100, y el texto no cuenta los factores de frecuencia fija
status: fixed
severity: high
component: figuras
found_in: 0.2.1
fixed_in: 0.2.2
reported: 2026-09-25
reporter: David — revisión de las figuras (al reabrir BUG-0165)
tags:
  - figuras
  - ljung-box
  - degrees-of-freedom
  - pyfug
references:
  - BUG-0165
  - BUG-0166
  - BUG-0074
  - BUG-0084
  - fue/bugs/BUG-0023
  - tests/test_bug_0165_0190_una_figura_de_residuos.py
---

## Summary

pyfug sólo sabe de SERIES: su `plot_combined(ser, npar=0, nlags=0, …)` rotula la
Q como `Q(nlags − npar)` y deja al llamante decir cuántos parámetros ARMA se
estimaron. art la llamaba sobre RESIDUOS de modelos sin decírselo. Tres
defectos de la misma familia:

1. **La Q de la figura rotulaba los retardos.** `describe_diagnosis` y
   `describe_interventions` llamaban `_pyfug_combined(pf, d=0, title=…)`, con
   `npar=0`. El rótulo decía `Q(39)` donde los grados de libertad eran 38. Sólo
   acertaba cuando el modelo no estimaba ningún ARMA.
2. **La identificación sobre los residuos de un `.pre` salía ×100.**
   `guided_identification(…, pre_path=…)` pasaba los residuos en la escala de
   `refactor` (ya en %), y pyfug multiplica por 100 para rotular: vuelve
   BUG-0084. Y también con `npar=0`.
3. **El texto no contaba los factores de frecuencia fija.** El recuento de ARMA
   de `diagnose()` (el arreglo de BUG-0166) sumaba los factores AR/MA regulares
   y estacionales pero no `ar_f`/`ma_f`, los que introducen las reformulaciones
   del MEG. En un modelo reformulado la Q del texto tenía un grado de libertad
   de más por factor.

Y los retardos: pyfug usa su propia regla (`max(10, 3(f+1))`, con tope n/2 − 1
por statsmodels), que no es la de fug C; en series anuales la figura y el texto
miraban un número distinto de retardos.

## Impact

Alto: el rótulo de la Q es un número publicado que se lee para decidir si un
modelo está terminado. Medido sobre el run 3 de SF_MEG:

| modelo | ARMA estimados | figura (pyfug) | texto | correcto |
|---|---|---|---|---|
| ES_CPI_A_m00 | 0 | Q(39) | 39 | 39 |
| ES_CPI_A_m02 | 1 | **Q(39)** | 38 | 38 |
| ES_CPI_A_m06 (MA(2) de frecuencia fija) | 2 | **Q(39)** | **38** | 37 |

## Root cause

Lo que decide si una figura de residuos es correcta no está en los residuos,
está en el modelo —cuántos ARMA se estimaron, cuánto consumió la diferenciación,
en qué escala vienen—, y cada llamante lo reconstruía a mano, o no.

## Fix

* `art.diagnosis.figura_residuos(model, title)` —el constructor único de
  BUG-0165— pasa a pyfug `npar = fue.diagnostics.free_arma_count(model)` y
  `nlags = fue.diagnostics.default_lags(n, s)` (la regla de fug C), y los
  residuos en fracción y fechados con `fue.diagnostics.residuals_start`.
* `describe_identification(…, npar=0)` acepta los ARMA del modelo cuando lo que
  identifica son residuos, y usa la regla de fug C para los retardos;
  `guided_identification` con `pre_path` le pasa los residuos en fracción y el
  `npar` del `.pre`.
* `diagnose()` cuenta con `fue.diagnostics.free_arma_count`, la del `.out`, que
  incluye los factores de frecuencia fija.
* `desfase_observaciones`, `_resid_start` y `_default_lags_fug` delegan en fue
  (fue/BUG-0023): el conocimiento del modelo vive en su dueño.

Requiere fue con BUG-0023.

## Validation

`tests/test_bug_0165_0190_una_figura_de_residuos.py`: Q(39), Q(38) y Q(37) en la
figura; la serie de residuos en fracción y fechada; los p-valores del texto de
A_m06 con 2 grados de libertad menos; `describe_identification` pasa `npar` y
`nlags=39`. Fallan con el código anterior.
