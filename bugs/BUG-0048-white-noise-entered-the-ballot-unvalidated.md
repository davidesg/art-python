---
id: BUG-0048
title: el ruido blanco entraba en la papeleta sin pasar por ninguna puerta — admitido por BUG-0044, quedó como el único candidato sin filtro, y la bonificación de parsimonia lo puso por delante de un AR(2) con mejor similitud cruda
status: fixed
severity: high
component: model-detection
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: David — al comparar el PGAS del run 2 con el del modo guiado
tags:
  - identification
  - regression
  - parsimony
references:
  - src/art/model_detection.py (_validate_white_noise, suggest_orders)
  - bugs/BUG-0044-white-noise-was-not-on-the-ballot.md
  - tests/test_bug_0048_ruido_blanco_con_puerta.py
  - bugs/BUG-0048-repro/repro.py
---

## Summary

**Es una regresión nuestra, introducida al arreglar BUG-0044.**

Cada orden candidato pasa un filtro antes de entrar en la lista:
`_validate_ar(p, ...)` comprueba que la PACF respalda ese `p`; `_validate_ma(q,
...)` que la ACF respalda ese `q`. Las dos devuelven `True` de inmediato cuando
el orden es 0 —no hay «retardo p» que mirar— y mientras `(0,0,0,0)` estaba
excluido de la enumeración eso no tenía ninguna consecuencia.

BUG-0044 lo admitió, y hacía bien: «no hace falta ARMA» a veces es la respuesta,
y la herramienta imprime la regla «Sin estructura → p=0, q=0» justo encima de la
lista. Lo que no vio es que quedaba como **el único candidato que entra sin
filtro**. Y la bonificación de parsimonia lo empuja hacia arriba: no paga
parámetros (`penalty = 0.03`) y cobra el bonus de «simple y con buen ajuste»
(`+0.05`), o sea **+0.02 neto**, mientras un AR(2) paga `0.03 + 2×0.015` y cobra
el mismo bonus, **−0.01 neto**. Treinta milésimas de ventaja, regaladas.

## El caso real

`∇ln PGAS`, la serie del precio de exportación del gas boliviano:

```
n=83   banda 95% = ±0.2151
lag   ACF        PACF
 1   +0.5749*   +0.5819*
 2   +0.1321    -0.3074*
 3   -0.0076    +0.1136

Q(15) = 35.90   p = 0.0018     ← el ruido blanco se rechaza de plano
```

Y aun así la lista lo colocaba **cuarto**, por delante del AR(2):

```
 4  (0,0)(0,0)  ajustada=0.7814  cruda=0.7614   ← RUIDO BLANCO
 5  (2,0)(0,0)  ajustada=0.7549  cruda=0.7649
```

La similitud **cruda** favorece al AR(2) (0.7649 contra 0.7614). Los invierte el
ajuste de parsimonia. Un modelo con dos retardos de PACF significativos por
debajo de «no hace falta modelo», sobre una serie cuya Q rechaza el ruido blanco
con p=0.0018.

## Fix

El ruido blanco **tiene su propio contraste**, y es el que decide:

```python
def _validate_white_noise(w, lags, alpha=0.05):
    lb = _fue_ljung_box(w, lags=lags, df_correction=0)
    return float(lb["pvalue"][-1]) > alpha
```

Aplicado en la enumeración, con el mismo `continue` que los demás órdenes.

**Por qué la Q y no contar retardos fuera de banda.** Contar bandas es un
sucedáneo, y además depende de cuántos retardos se miren. La Q de Ljung-Box es
el contraste, y es **el mismo instrumento con el que la diagnosis decide si unos
residuos son blancos**: la identificación y la diagnosis pasan a preguntar lo
mismo de la misma forma. `df_correction=0` a propósito: aquí no se ha estimado
nada todavía, se pregunta por los DATOS.

## Lo que NO se rompe

El caso dorado de BUG-0044 sigue en pie. Sobre los residuos de `ITCER_m10`:

```
Q(15) = 10.02   p = 0.8185     ← el ruido blanco es sostenible
 1  (0,0)(0,0)  ajustada=0.9397  cruda=0.9197   ← RUIDO BLANCO, y también la mejor cruda
```

Que es exactamente el reparto correcto: donde la Q no rechaza, el ruido blanco
encabeza; donde rechaza, ni aparece.
