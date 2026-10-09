---
id: BUG-0235
title: formal_tests sobre un modelo con d=2 contrasta d=3 (candidato ∇³) y lo presenta como «confirmatorio del orden de integración… d confirmado ✓»; el par que corresponde —subdiferenciación del modelo en d=2 con el Shin-Fuller del modelo en d=1— no existe
status: open
severity: medium
component: formal-tests
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO de Villaverde (P02, Econometría Aplicada UCM)
tags:
  - formal-tests
  - dcd
  - orden-de-integracion
  - un-paso
references:
  - src/art/formal_tests.py:1006 (dcd_overdiff_regular: mc.d = d + 1 sin tope)
  - src/art/describe.py:2472, 2608-2660 (bloque «confirmatorio del orden de integración»)
  - src/art/policy.py (_un_paso_desde: la regla de un paso, BUG-0226/0227)
  - BUG-0045 (el par confirmatorio miraba sólo hacia arriba)
  - bugs/BUG-0235-repro/repro.py
---

## Summary

Villaverde, IMA(2,1) (∇² ln z = (1 − 0,906B) a), `formal_tests(subdiferenciacion=True)`:

- «**DCD sobre-diferenciación regular** — confirmatorio del orden de integración … Candidato:
  **∇^3** … θ̂=+1.0000, LR=-0.000 → la ∇ extra sobre-diferencia → **d confirmado ✓**».
- Shin-Fuller «no es aplicable» (el IMA no tiene AR) y la salida dice «Sin par confirmatorio».

Dos defectos:

1. **Una tercera diferencia no es una hipótesis.** Con la regla de un paso (BUG-0226/0227)
   el orden de integración se mueve entre 0, 1 y 2; desde d=2 no se sube. Contrastar ∇³ y
   presentarlo como «confirmatorio» da un ✓ que no confirma nada de lo que está en duda.
2. **La duda en un modelo con d=2 es la de abajo**: ¿sobraba la segunda ∇? El par que la
   contesta cruza dos modelos: el **DCD de subdiferenciación** del modelo en d=2 (H₀: θ=1 en
   su MA) y el **Shin-Fuller** del modelo en d=1 (H₀: raíz unitaria en su AR). `formal_tests`
   mira un solo modelo y no puede formarlo; el analista tuvo que leerlo a mano (Villaverde:
   SF sobre el AR(7) d=1 → d=1 basta; DCD sobre el IMA(2,1), θ̂=0,906, LR=23,9 → la 2.ª ∇
   es genuina → ambiguo).

## Impact

El ✓ de «d confirmado» sobre ∇³ es lo más visible de la salida y es irrelevante; lo
relevante (la frontera d=1/d=2) queda sin par. En la P02 es la pregunta central de los
distritos (Salamanca, Villaverde).

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0235-repro/repro.py` (Villaverde, €/m², 2010:01-2025:08).

## Root cause

`dcd_overdiff_regular` hace `mc.d = d + 1` sin tope, y `describe` lo publica siempre como
lado MA del par en f=0.

## Fix

- Con d=2 (o d ≥ el máximo de la regla) no se construye ∇^{d+1}: el bloque dice «desde d=2 no
  se contrasta una tercera diferencia».
- Ofrecer el par de la frontera d−1/d: `formal_tests(…, modelo_d_menos_1=<.pre>)` (o una
  herramienta `integration_pair(pre_d, pre_d_menos_1)`) que lea el Shin-Fuller del modelo en
  d−1 y el DCD de subdiferenciación del modelo en d, con la tabla de cuatro casos
  (docs/ARBOL-orden-de-integracion.md).

## Validation

Repro: sin «Candidato: ∇^3» ni «d confirmado» sobre un modelo con d=2; con el modelo en d=1
dado, el par cruzado aparece y Villaverde sale «ambiguo».

## Addendum (2026-10-08) — batería de contrastes

`research/bateria_contrastes_d.py` (21 modelos verdaderos, d = 0, 1, 2) lo confirma en los 7
modelos con d = 2: siempre se construye ∇³. Y hay un segundo síntoma: **Shin-Fuller también
mira hacia arriba desde d = 2**. AR(1) φ = 0,95 con d = 2: «Φ̂₁ᵤ = 1,120 → Raíz unitaria —
considerar d+1 ✗», y el par en f=0 dice «lado AR: raíz unitaria → d+1»: art propone **d = 3**.
El par que forma con d = 2 (SF + DCD sobre ∇³) mira entero hacia arriba, que es lo que no
existe. Repro: `bugs/BUG-0236-repro/repro.py`, bloque «d=2 AR(1) .95».

Fix ampliado: con d = 2 (el máximo de la regla), el SF del modelo no propone d+1 (si no
rechaza, decir que hay un AR casi en 1 que, con d = 2, se lee como persistencia del modelo, no
como otra diferencia), no se construye ∇³, y el par de la frontera 1/2 es el cruzado.

