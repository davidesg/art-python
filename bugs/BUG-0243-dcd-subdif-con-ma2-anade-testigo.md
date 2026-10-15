---
id: BUG-0243
title: dcd_underdiff_regular con un MA(2) en el modelo AÑADE un testigo MA(1) aparte en vez de contrastar la raíz del MA(2) en +1 — sale θ̂ = −0,12, LR = 50,6, sin significado
status: fixed
severity: medium
component: formal_tests
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in: 0.2.3
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

## Fix

- `dcd_underdiff_regular` (`src/art/formal_tests.py:1105`): el testigo es la
  raíz REAL más cercana a +1 de los factores MA regulares libres, de cualquier
  orden. El modelo libre es el del analista (su ℓ, sin reajustar); el
  restringido parte el factor en (1 − B)·MA(q−1), con el MA(q−1) sembrado por
  la deflación y libre. Un MA(1) es el caso q = 1 (lo de siempre). Si el MA
  sólo tiene raíces complejas, ninguna puede ser la (1 − B): se calcula el LR
  de la restricción (MA(q) con una raíz en +1 frente al libre, que es la GLR
  de la misma H₀) y el resultado se marca `raices_complejas`; el informe dice
  que no hay raíz real que cancele la ∇ y lo da como no concluyente si no
  rechaza. El testigo añadido queda sólo para el modelo sin MA regular.
- `dcd_overdiff_regular` (`src/art/formal_tests.py:1340`): un MA(q ≥ 2) ya no
  se sustituye por el testigo; se conserva, libre, y el testigo va en su propio
  factor. La propuesta del informe («lo mismo» —refactorizar y contrastar la
  raíz del MA— en la sobrediferenciación) no responde a la pregunta de ese
  contraste, que es si sobra la ∇ EXTRA, no si el MA del modelo tiene raíz en
  +1. Lo que sí estaba mal es que, al sustituir un MA(2) por un MA(1), bajo
  H₀ el candidato ya no era el modelo base por (1 − B)/(1 − B). El MA(1) se
  sigue sustituyendo: misma dimensión, y es el comportamiento validado
  (BUG-0011).

Test: `tests/test_bug_0243_ma2_testigo.py` — Moncloa m03: θ̂ es la raíz del
MA(2) (0,8516), el ℓ libre es el del modelo, LR ≥ crítico; un MA(2) de raíces
complejas sale `raices_complejas`; la sobrediferenciación conserva el MA(2)
(el testigo en el factor 1). Falla sin el arreglo (3 de 3).

## Validation

`bugs/BUG-0243-repro/repro.py` (nuevo) sale con 0; con HEAD, 1. Moncloa m03:
«θ̂=+0.8516, LR=80.852 → la ∇ es genuina», «Testigo: la raíz real del MA(2) más
cercana a +1» (antes θ̂ = −0,1177, LR 50,576 de un MA(1) añadido). Con d = 2 la
sobrediferenciación no se construye (BUG-0235).
