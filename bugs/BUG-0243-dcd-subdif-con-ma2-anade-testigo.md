---
id: BUG-0243
title: dcd_underdiff_regular con un MA(2) en el modelo AÑADE un testigo MA(1) aparte en vez de contrastar la raíz del MA(2) en +1 — sale θ̂ = −0,12, LR = 50,6, sin significado
status: open
severity: medium
component: formal_tests
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in:
reported: 2026-10-09
reporter: David / Claude — análisis guiado de Moncloa (P02)
tags: [dcd, subdiferenciacion, bug-0045, bug-0224]
references:
  - src/art/formal_tests.py dcd_underdiff_regular (filtro `len(fac) == 1`)
---

## Summary

`dcd_underdiff_regular` busca el testigo entre los factores MA regulares de longitud 1. Un
MA(2) como un solo factor no cuenta, así que el código cree que «no hay MA» y añade un MA(1)
libre ADEMÁS del MA(2). En Moncloa m03, que es un ARIMA(1,2,2), el testigo añadido sale con
θ̂ = −0,1177 y LR = 50,576, y la salida concluye «la ∇ es genuina → acotado por abajo».

## Impact

El veredicto no contrasta lo que dice. La pregunta es si el MA del modelo tiene una raíz en +1
que cancele la 2.ª ∇, y con el MA(2) libre al lado el testigo añadido no la recoge: su θ̂ y
su LR no tienen significado. En los distritos con d=2 y MA(2) (Moncloa) se lee una cota
inferior que no existe.

## Reproduction

`formal_tests("bugs/BUG-0243-repro/Moncloa_m03.pre", run_meg=False, subdiferenciacion=True)`

## Fix (propuesto)

Con un MA(q≥2) regular, refactorizarlo como (1 − θB)·MA(q−1) con θ inicializado en la raíz
real del MA más cercana a +1, y contrastar H₀: θ = 1 con `dcd`. Si sólo tiene raíces
complejas, decir que no hay raíz real que pueda cancelar la ∇. Lo mismo para el DCD de
sobrediferenciación, que hoy SUSTITUYE el MA(2) por el testigo («su MA regular (2 coef.)
sustituido por el testigo»).

## Validation

La repro, y una celda ARIMA(0,2,2) con θ₁+θ₂ cerca de 1 en la batería de la fase 2.
