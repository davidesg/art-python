---
id: BUG-0247
title: El nodo Box-Cox dice a la vez «Eso NO es "las dos son razonables"» y «Ambas transformaciones son razonables»
status: open
severity: low
component: describe
found_in: 0.2.3.dev0
fixed_in: 
reported: 2026-10-14
reporter: David / Claude — rodaje de art con el ejemplo lutkepohl_poskitt de sima (Buffalo, carril guiado)
tags:
  - guided_identification
  - box-cox
references:
  - src/art/describe.py, describe_boxcox: bloques `if horquilla:` (~l. 199) y `if ambiguous:` (~l. 214 y ~l. 248)
---

## Summary

Cuando las dos correlaciones media-dt tienen signos opuestos (`horquilla`) y
además |Δcorr| < 0.10 (`ambiguous`), el informe de la llamada 1 de
`guided_identification` saca los dos avisos seguidos, y se contradicen:

> ⚠ **Los dos signos son OPUESTOS: la λ correcta está ENTRE las dos.** … Eso NO
> es «las dos son razonables» — es que ninguna de las dos anula la dependencia …
> la decisión no la cierra este estadístico: la cierra el DOMINIO de la serie.

> ⚠ **Decisión ambigua** — la diferencia entre escalas es pequeña
> (Δcorr=0.082 < 0.10). Ambas transformaciones son razonables.

El aviso de la horquilla (BUG-0040) se escribió precisamente para sustituir al
genérico en este caso, y el genérico no se calla.

Además, la recomendación final (`rec`, rama `ambiguous`) termina en «Siguiente
paso: detección de estacionalidad», cuando el siguiente nodo de la llamada 2 es
d (la serie transformada y su ACF/PACF a d = 0). Lo mismo en la rama no ambigua.

## Impact

El analista lee dos lecturas opuestas del mismo estadístico en un nodo de
decisión. Con dominio declarado no cambia la λ (el dominio decide y lo dice),
pero en un carril sin dominio el aviso genérico invita a elegir λ = 1
«por interpretabilidad», que es lo que BUG-0040 quería evitar.

## Reproduction

`python3 bugs/BUG-0247-repro/repro.py` — con los datos del ejemplo (`flour_prices.csv`); sale con 1 mientras el bug siga abierto.

    load_data(flour_prices.csv, column="Buffalo")            # ejemplo lutkepohl_poskitt de sima
    guided_identification(inp, domain="price_index")         # llamada 1

corr λ=1 = +0.159, corr λ=0 = −0.077: horquilla y Δ = 0.082 < 0.10.

## Root cause

`describe_boxcox` evalúa `horquilla` y `ambiguous` por separado y añade los dos
bloques; `ambiguous` no mira `horquilla`.

## Fix

Con `horquilla`, omitir el bloque «Decisión ambigua» (o reducirlo a la regla
del dominio, sin «Ambas … son razonables»), y en `rec` decir «la decide el
dominio» en vez de «puedes usar λ=1.0». Cambiar «Siguiente paso: detección de
estacionalidad» por el nodo real (d).

## Validation

Test en `tests/` con un par de correlaciones de signo opuesto y |Δ| < 0.10: el
texto no contiene «Ambas transformaciones son razonables».
