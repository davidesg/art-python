---
id: BUG-0039
title: the seasonal-lag MA had no non-invertibility test, so an airline model could not be refuted — the law exists (Davis, Chen & Dunsmuir, Table 3.2) and is in the project's own literature
status: fixed
severity: high
component: formal-tests
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-28
reporter: David / réplica TFM Bolivia
tags:
  - dcd
  - seasonality
  - missing-test
  - critical-values
references:
  - src/art/formal_tests.py (_DCD_CRIT_MA_S_TABLE, _dcd_crit_s, dcd_s)
  - src/art/pipeline.py (_seasonal_ma_invertible — el consumidor)
  - Davis, Chen & Dunsmuir, "Inference for Seasonal Moving Average Models With
    a Unit Root", Tabla 3.2 — SF_MEG/literature/978-1-4612-2412-9_12.pdf
  - bugs/BUG-0039-repro/repro.py
  - tests/test_seasonal_route_and_objetivo.py
---

## Summary

ART tenía **dos** regímenes de valores críticos para el DCD:

| régimen | dónde | 10% / 5% / 1% |
|---|---|---|
| raíz real (s=1) | MA regular, tendencia, Nyquist | 1.00 / 1.94 / 4.41 |
| par complejo (s=2) | frecuencias interiores (`ma_f`) | ~1.11 / 2.04 / 4.52 |

Falta el tercero. Un MA de **retardo estacional** `(1 − Θ·Bˢ)` en su frontera
pone **s raíces sobre el círculo a la vez** —las s raíces s-ésimas de la
unidad—, y su ley no es ninguna de las dos.

Consecuencia: **un modelo airline no se podía refutar.** En
`∇∇ₛ y = (1 − θB)(1 − ΘBˢ) a`, si Θ̂ se apila en la frontera entonces
`(1 − ΘBˢ)` cancela a la `(1 − Bˢ)` que se aplicó: la diferencia estacional
sobraba y la estacionalidad era **determinista**. Es el diagnóstico central del
modelo estacional de Box-Jenkins, y no existía en la suite — no había `dcd_s`,
y `dcd_f` no sirve porque contrasta los factores de FRECUENCIA FIJA (`ma_f`), no
el MA de retardo estacional (`ma_s`).

## Dónde mordió

Al implementar la adjudicación de la ruta estacional —el autónomo estima B1
(D=0 + armónicos) y B2 (D=1) y las contrasta— el par necesita los dos lados:

* B1 se contrasta con el **MEG**;
* B2 se contrasta con la no invertibilidad de su **MA estacional**.

El segundo lado no existía. Se implementó provisionalmente un **criterio de
distancia** (|Θ̂| > 0.95 ⇒ frontera) con la nota de que la ley no estaba
disponible. Lo estaba: en `SF_MEG/literature`, en el propio proyecto.

## La ley

Davis, Chen y Dunsmuir, **Tabla 3.2** — cuantiles asintóticos de `b_GLR(α)`:

| α | 0.10 | 0.05 | 0.025 | 0.01 |
|---|---|---|---|---|
| **s = 4** | 1.21 | **2.18** | 3.17 | 4.75 |
| **s = 12** | 1.36 | **2.31** | 3.44 | 5.12 |

Y es el **mismo estadístico** que ya calcula `dcd()`. El paper lo define como
`Z_T(β) = L_T(β) − L_T(0)`, *"the −2log of the likelihood ratio"*, con región
crítica `Z_T > b_GLR(α)` — misma fórmula y misma dirección que
`lr = 2·(L_libre − L_restringida)`.

**Tamaño en muestra finita (Tabla 3.3):** los cuantiles asintóticos aciertan casi
exactamente ya con n=20 ciclos — s=4: nominal 0.05 → alcanzado 0.0517; s=12:
0.0512. No hace falta corrección por n, al contrario que en el régimen del par
complejo. Y n=20 ciclos con s=4 son T=80, justo el tamaño de las series de la
réplica (84).

## Por qué importa el valor concreto

Los cuantiles estacionales son **más exigentes** que la ley desnuda: 2.18 y 2.31
frente a 1.94 al 5%. Aplicar la ley s=1 a un MA estacional **sobre-rechaza** el
cero unitario, y sobre-rechazar aquí significa **declarar genuina una ∇ₛ que
sobra** — precisamente el error que el contraste existe para evitar.

## Fix

* `_DCD_CRIT_MA_S_TABLE` con la Tabla 3.2, y `_dcd_crit_s(s)` que interpola
  linealmente fuera de {4, 12} **dejando constancia de que eso es aproximación**,
  no el valor del paper.
* `dcd_s(model)` — mismo patrón que `dcd()`: restringe cada factor MA estacional
  libre a Θ=1, reestima, LR, y compara contra la ley de su régimen.
* `DCDResult._crit` respeta un `_crit_override`, que es como el nuevo régimen
  entra sin tocar los dos que ya estaban.
* `pipeline._seasonal_ma_invertible` pasa del criterio de distancia al contraste
  calibrado, y con él la adjudicación de ruta tiene sus dos lados de verdad.

## Repro

`bugs/BUG-0039-repro/repro.py` construye las dos situaciones y las discrimina:

```
estacionalidad ESTOCÁSTICA (la ∇ₛ hace falta)
   Θ̂=+0.3972  LR=68.360  crít 5%=2.18  →  invertible → la ∇ₛ es GENUINA

estacionalidad DETERMINISTA (la ∇ₛ sobra)
   Θ̂=+1.0000  LR=-0.150  crít 5%=2.18  →  en la frontera → la ∇ₛ SOBRA
```

## Lo que queda abierto

El paper tabula **s=4 y s=12**, que son las dos frecuencias estacionales que la
suite maneja. Para cualquier otro `s` se interpola y se dice; si algún día hace
falta un `s` distinto, el valor hay que simularlo con el método del paper (§3),
no interpolarlo.
