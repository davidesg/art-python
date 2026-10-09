---
id: BUG-0242
title: formal_tests calla el Shin-Fuller por sobreajuste cuando la raíz real recuperada es NEGATIVA y dice «el lado AR no existe», cuando sí es informativa
status: open
severity: medium
component: formal_tests
found_in: 0.2.3.dev0 (+ arreglos sin commit)
fixed_in:
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

## Fix (propuesto)

Que `shin_fuller_sobreajuste` devuelva un resultado «sin raíz real positiva» con la φ̂
recuperada (como el BUG-0215 hace en el SF directo), y que el informe lo presente así: «lado
AR por sobreajuste: la raíz real recuperada es −0,21, lejos de ρ=1, así que no apoya d+1».

## Validation

El caso de la repro y las celdas de AR(2) complejo de la batería de la fase 2.
