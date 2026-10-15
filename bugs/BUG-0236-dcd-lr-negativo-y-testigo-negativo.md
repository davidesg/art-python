---
id: BUG-0236
title: DCD de sobrediferenciación: un LR negativo (el modelo libre peor que el restringido) y un testigo que se va a θ̂ < 0 se publican como «testigo NO invertible (θ→+1) … d confirmado ✓»
status: fixed
severity: high
component: formal-tests
found_in: 0.2.3.dev0 @088933d (+ arreglos sin commit de BUG-0225…0231)
fixed_in: 0.2.3
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

En `_frontera_theta_uno` (`src/art/formal_tests.py:973`), que usan ahora los
dos DCD del orden de integración (puntos 1, 2 y 4 del informe):

- si el LR sale negativo, o el testigo libre sale con θ̂ < 0, el libre se
  reajusta ARRANCANDO del restringido con θ⁰ = 0,95, y se toma el mejor de los
  dos máximos (es la estimación de MV, no una corrección del número);
- un LR en [−1e−3, 0) es ruido del optimizador y se lee como 0; uno por debajo,
  o no finito, sale con `motivo_no_calculable` y `calculable` falso: nunca un
  veredicto (ver BUG-0232).

Medido: en los dos casos de la batería el reintento llega al máximo libre en
θ̂ = 1,0000 con LR = 0 (ℓ libre = ℓ restringida). Es decir, el libre se había
quedado en un máximo local; con θ = 1 la ∇ extra sí sobra.

Punto 3: el titular del DCD de sobrediferenciación (`_texto_sobredif_no_rechaza`,
`src/art/describe.py:2420`) dice «θ̂→+1 … d confirmado ✓» sólo con θ̂ a ≤ 0,10
de +1; con θ̂ < 0, «el testigo se fue al eje de π: no mide f=0», y con θ̂ lejos,
«no se rechaza, pero el testigo no se apila en +1 … sin confirmación fuerte».
Un LR no calculable se dice así y no entra en el par.

El caso d = 2 (AR(1) 0,95) ya no construye ∇³ (BUG-0235).

Test: `tests/test_bug_0236_lr_negativo.py` — el AR(2) de la batería da LR ≥ 0;
la frontera, con un ℓ libre malo y θ̂ = −0,2, reintenta y lo mejora; un LR
negativo no es calculable; los titulares con θ̂ = −0,19, 0,80 y 0,999, y uno con
LR negativo. Sin el arreglo no se importa (`_frontera_theta_uno`); el caso de la
batería daba LR = −0,053.

## Validation

`bugs/BUG-0236-repro/repro.py` sale con 0 (con HEAD, 1); ahora decide la salida
con los casos de BUG-0236 y el añadido de BUG-0235 (los bloques 0237 sólo
imprimen). d=1 AR(2) reales: «θ̂=+1.0000, LR=0.000 → testigo en la frontera».
d=2 AR(1) .95: sin ∇³, y SF sin «considerar d+1».
