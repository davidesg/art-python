---
id: BUG-0049
title: un candidato AR/MA disperso se enumeraba con la misma etiqueta que el completo del mismo orden — dos modelos distintos, un solo nombre, y el disperso primero
status: fixed
severity: medium
component: describe
found_in: 0.1.12 (unreleased)
fixed_in: 0.1.12 (unreleased)
reported: 2026-08-29
reporter: David / réplica TFM Bolivia — visto al revisar la lista de PGAS
tags:
  - identification
  - presentation
references:
  - src/art/describe.py (describe_identification — la lista de candidatos)
  - tests/test_bug_0049_disperso_etiquetado.py
---

## Summary

`suggest_orders` genera, además de los candidatos completos, candidatos
**dispersos**: un AR o MA con un solo coeficiente, en el retardo k, y los
anteriores en cero (`sparse_ar_lag`, `sparse_ma_lag` en el `ModelSpec`). Es un
modelo distinto del completo del mismo orden — un AR(2) disperso tiene φ₁=0 y
φ₂≠0, uno completo tiene los dos.

La lista nunca mostraba esos campos. Sobre `∇ln PGAS` salía así:

```
   4. ARIMA(2,1,0)(0,0,0)_4  sim=0.755  —  PACF se corta en lag 2 → AR(2) puro
   5. ARIMA(2,1,0)(0,0,0)_4  sim=0.732  —  PACF se corta en lag 2 → AR(2) puro
```

Dos entradas, mismo nombre, misma explicación, similitudes distintas. Y el
**disperso va primero**, así que quien pida «el AR(2) de la lista» se lleva el
que no cree estar pidiendo.

## Fix

La etiqueta dice qué es:

```
   4. ARIMA(2,1,0)(0,0,0)_4  [AR sólo en B^2]  sim=0.755  —  ...
   5. ARIMA(2,1,0)(0,0,0)_4  sim=0.732  —  ...
```

El test comprueba lo que importa —que **ninguna etiqueta se repita**— y no la
redacción, para que un cambio de estilo no lo rompa.
