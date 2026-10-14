---
id: BUG-0247
title: El nodo Box-Cox dice a la vez «Eso NO es "las dos son razonables"» y «Ambas transformaciones son razonables»
status: fixed
severity: low
component: describe
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
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

En `describe_boxcox` (`src/art/describe.py`):

- El bloque «Decisión ambigua» sólo sale con `ambiguous and not horquilla`:
  con la horquilla ya está el aviso que remite al dominio, y el genérico lo
  contradecía.
- `rec` tiene una rama nueva para la horquilla: «Signos opuestos: la λ correcta
  está entre 0 y 1, y este estadístico no la decide; la decide el dominio…»,
  sin «puedes usar λ=1.0».
- «Siguiente paso: detección de estacionalidad» pasa a ser, en las tres ramas,
  «Siguiente paso: la serie transformada y su ACF/PACF a d = 0, para decidir d.»

Test: `tests/test_bug_0247_boxcox_horquilla_sin_ambigua.py` — Buffalo
(horquilla y Δ = 0.082): el resumen no contiene «Ambas transformaciones son
razonables», la recomendación remite al dominio y el siguiente paso es d.
Falla sin el arreglo.

## Validation

El repro sale con 0: la llamada 1 sobre Buffalo saca sólo el aviso de la
horquilla, y la recomendación manda a d. `tests/test_bug_0059_boxcox_conserva_el_signo.py`
sigue pasando.
