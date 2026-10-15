---
id: BUG-0242
title: formal_tests calla el Shin-Fuller por sobreajuste cuando la raíz real recuperada es NEGATIVA y dice «el lado AR no existe», cuando sí es informativa
status: fixed
severity: medium
component: formal_tests
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in: 0.2.3
reported: 2026-10-09
reporter: David / Claude — análisis guiado de IPC_US (P02)
tags: [shin-fuller, sobreajuste, bug-0068, bug-0215]
references:
  - src/art/describe.py:2464 (sf_sobre = _try(...))
  - src/art/formal_tests.py shin_fuller_sobreajuste
---

## Summary

IPC_US m06 es un AR(2) con raíces complejas más dos intervenciones. `shin_fuller` no es
aplicable, así que se entra en la rama de sobreajuste (BUG-0068). El AR(3) sobreajustado se
factoriza en AR(1)·AR(2) con φ̂ = −0,206. `shin_fuller` lanza la excepción de BUG-0215
(«raíz negativa»), y `_try` la convierte en `None`. La salida dice entonces «El lado AR —la
nula opuesta— no existe en esta corrida».

## Impact

Es evidencia que se pierde: una raíz real recuperada negativa, lejos de +1, dice que el lado AR
NO apoya d+1. Y justo aquí el DCD de sobrediferenciación queda dentro de la banda (θ̂ = 0,958)
con dos deterministas. El analista tiene que ejecutar la función a mano para verlo.

## Reproduction

```python
from art.mcp_server import _load_fitted
from art.formal_tests import shin_fuller_sobreajuste
ts, m = _load_fitted("bugs/BUG-0242-repro/IPC_US_m06.pre")
shin_fuller_sobreajuste(m)   # ValueError: «Sus raíces reales son negativas (φ̂ = -0.2060)»
```

## Fix

El propuesto. `shin_fuller_sobreajuste` (`src/art/formal_tests.py:716`) mira las
raíces reales del AR(p+1): si alguna es positiva, contrasta como antes; si
todas son negativas, devuelve el resultado con `sf = None` y `phi_real` = la
raíz recuperada (`sin_raiz_positiva`, l. 625); si no hay ninguna real, lanza
como siempre.

`describe.py:2882` lo presenta: «su raíz real sale NEGATIVA (φ̂ = −0,2060),
lejos de ρ = +1. No hay Φ̂₁ᵤ … pero la lectura existe: el AR ampliado tuvo
sitio para una raíz cerca de +1 y no la puso, así que el lado AR no apoya
d+1», con el ΔAIC. Y el cierre lo lee (`describe.py:3441`): con el DCD de
sobrediferenciación pidiendo d+1 y el lado AR por sobreajuste sin apoyarlo
(raíz negativa o Φ̂₁ᵤ que rechaza), el par discrepa y va a `pendientes`; si los
dos apuntan a d+1, lo dice. Antes, con el sobreajuste presente, el cierre no
leía ese caso.

Test: `tests/test_bug_0242_sobreajuste_raiz_negativa.py` — IPC_US m06:
`sin_raiz_positiva`, φ̂ ≈ −0,206; el informe no dice «no existe en esta
corrida», lo presenta, y el cierre dice «NO lo apoya». Falla sin el arreglo.

## Validation

`bugs/BUG-0242-repro/repro.py` (nuevo) sale con 0; con HEAD, 1. IPC_US m06: el
DCD de sobrediferenciación θ̂ = 0,958, LR = 4,52 (d+1, en la banda, con dos
deterministas) frente al lado AR recuperado (φ̂ = −0,206, ΔAIC +1,34): el cierre
dice que el par discrepa y que d no queda fijado.
