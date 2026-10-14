---
id: BUG-0250
title: confirm_and_estimate con base_pre_path y p=0, q=0 conserva el AR de la base en vez de quitarlo
status: fixed
severity: high
component: pipeline
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-10-14
reporter: David / Claude — rodaje de art con el ejemplo lutkepohl_poskitt de sima (Minneapolis, carril guiado)
tags:
  - confirm_and_estimate
  - encadenamiento
references:
  - src/art/pipeline.py, constructor incremental (~l. 1060): `ar = m_base.ar or [[0.0]]`
---

## Summary

El modo incremental (`base_pre_path`) promete conservar intervenciones y
armónicos y SUSTITUIR el ARMA por (p, q, P, Q). Con p = q = P = Q = 0 no lo
sustituye: copia el AR de la base.

m04 = AR(1) + step×2 en 12/1973 (φ = 0.1176, t 1.16). Para quitar el φ no
significativo:

    confirm_and_estimate(m04.inp, m05.inp, base_pre_path=m04.pre, p=0, q=0)

m05 sale idéntico a m04: `(1 − 0.1176·B) (∇Nₜ) = aₜ`, mismo ℓ, y el informe
vuelve a proponer «Quitar lo que sobra — AR(1) con t = +1.16». La ruta que la
propia herramienta recomienda para quitar un parámetro no lo quita.

## Impact

Alto: es la operación «vuelve al modelo sin él» del nodo de sobreparametrización
y de la reformulación tras una intervención. El analista cree haber quitado el
AR y sigue estimando con él; sólo se ve leyendo la ecuación. El encabezado
«Punto de partida: ARIMA(0,1,0) + 1 interv.» además lo afirma.

## Reproduction

`python3 bugs/BUG-0250-repro/repro.py` — con los datos del ejemplo (`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

    # sima examples/lutkepohl_poskitt/data/flour_prices.csv, columna Minneapolis
    confirm_and_estimate(lam=0, d=1, D=0, p=1, q=0, n_harmonics=0, seasonal=False)   # m02
    guided_intervention(m02.pre, date="12/1973", form="step", n_omega=2, output_path=m04.inp)
    confirm_and_estimate(m04.inp, m05.inp, base_pre_path=m04.pre, p=0, q=0)         # sigue el AR(1)

## Root cause

    elif q == 0 and P == 0 and Q == 0:
        # Keep the p=0,q=0 workaround only when there is truly no ARMA at all
        ar   = m_base.ar or [[0.0]]
        ar_f = m_base.ar_free or [[False]]

El «workaround» (fue necesita un AR placeholder cuando no hay ARMA) debía ser
siempre `[[0.0]]` fijo; `m_base.ar or` hereda el AR libre de la base.

## Fix

En `_build_arma_on_model` (`src/art/pipeline.py`), sin ARMA el relleno es
siempre el AR(1) fijo a cero:

    ar   = [[0.0]]
    ar_f = [[False]]

Test: `tests/test_bug_0250_encadenar_p0_q0_quita_el_ar.py` — un base con
AR(1) libre, encadenado con p = q = 0, no deja ningún AR libre, y estimado
no lleva AR. Falla sin el arreglo.

## Validation

El repro sale con 0: m05 (p = 0, q = 0 sobre m04) es `∇Nₜ = aₜ` con los
escalones.

Antes del arreglo se rodeó en el ejemplo construyendo la intervención sobre el (0,1,0) (m03 → m06
con `suggest_intervention_form`): ω = 14.33, 14.01, ℓ −294.20, AIC 592.40.
