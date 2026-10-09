---
id: BUG-0236
title: DCD de sobrediferenciación: un LR negativo (el modelo libre peor que el restringido) y un testigo que se va a θ̂ < 0 se publican como «testigo NO invertible (θ→+1) … d confirmado ✓»
status: open
severity: high
component: formal-tests
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in:
reported: 2026-10-08
reporter: David / Claude — batería de contrastes del orden de integración (research/bateria_contrastes_d.py)
tags:
  - formal-tests
  - dcd
  - optimizacion
  - orden-de-integracion
references:
  - src/art/formal_tests.py:1006 (dcd_overdiff_regular)
  - src/art/describe.py (bloque «DCD sobre-diferenciación regular»)
  - BUG-0232 (LR = −inf en la subdiferenciación)
  - docs/ARBOL-orden-de-integracion.md §3
  - bugs/BUG-0236-repro/repro.py
---

## Summary

Batería de 21 modelos simulados (d = 0, 1, 2), estimados con su especificación verdadera:

- **AR(2) reales (0,5; 0,3), d=1**: DCD de sobrediferenciación θ̂ = +0,9667, **LR = −0,053**
  → «testigo NO invertible (θ→+1) → la ∇ extra sobre-diferencia → d confirmado ✓».
- **AR(1) φ=0,95, d=2**: θ̂ = **−0,1893**, **LR = −1,807** → el mismo texto: «θ→+1… d
  confirmado ✓».

Un LR negativo dice que el máximo «libre» es PEOR que el restringido (θ = 1): el optimizador
no llegó al máximo del modelo libre. Y un testigo en −0,19 se ha ido al lado de la frecuencia π,
que es justo lo que el arranque en +0,85 pretende evitar (docstring de `dcd_overdiff_regular`).
Ninguna de las dos cosas es «θ→+1», y el veredicto se da igual, porque se decide sólo por
LR < crítico.

## Impact

El contraste que confirma el orden de integración por el lado MA da un ✓ sobre un cálculo
fallido. En el segundo caso, además, sobre un candidato ∇³ que no debería existir (BUG-0235).

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0236-repro/repro.py`, bloques «0236». Las series son las de
`research/bateria_contrastes_d.py` (N = 200, SEED = 2026), regeneradas en el mismo orden.

## Root cause

El veredicto lee sólo `lr < crit`. No comprueba (a) que el LR sea ≥ 0 (con tolerancia
numérica), (b) que θ̂ esté cerca de +1 para escribir «θ→+1», (c) que el testigo no haya cambiado
de signo.

## Fix

1. LR < −tolerancia → «no calculable: el máximo libre no se alcanzó» y reintentar el libre
   arrancando desde el restringido (θ = 1) o desde la estimación del modelo base; nunca un
   veredicto.
2. Testigo con θ̂ < 0 → «el testigo se fue a la frecuencia π: no mide f=0», y reintentar con
   el arranque acotado a θ > 0.
3. El texto «θ→+1» sólo si θ̂ está a menos de la banda de cuasi-cancelación de +1.
4. Lo mismo, y con el mismo código, en el DCD de subdiferenciación (BUG-0232).

## Validation

Repro: los dos casos dicen «no calculable» (o, tras reintentar, un LR ≥ 0 con θ̂ > 0), nunca
«d confirmado ✓» sobre un LR negativo.
