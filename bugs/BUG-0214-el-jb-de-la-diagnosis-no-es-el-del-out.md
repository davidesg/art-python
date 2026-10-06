---
id: BUG-0214
title: El Jarque-Bera de la diagnosis no coincide con el del .out del mismo modelo (367,74 frente a 359,19)
status: fixed
severity: low
component: diagnosis
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - diagnosis
  - normalidad
  - coherencia
references:
  - src/art/diagnosis.py
  - fue: report (.out)
  - bugs/BUG-0208-repro/repro.py
---

## Summary

IPC_US AR(2): la diagnosis da JB = 367,742; el `.out` del mismo ajuste, 359,190.

## Impact

Dos cifras para el mismo contraste; el alumno no sabe cuál citar.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0214.

## Root cause

Probablemente distinta muestra de residuos (condicionados frente a incondicionales, o los primeros d) o distinto estimador de los momentos.

## Fix

Calcularlo una vez y citarlo igual en los dos sitios, o decir en cada uno sobre qué residuos.

## Validation

Repro, bloque 0214: las dos cifras iguales.

## Resolution (2026-10-06)

**Root cause.** Not the residuals: both use the 215 unconditional residuals and
the same population moments. fue's `.out` copied the old C program, which
computes n/6 in integers: JB_out = ⌊n/6⌋·(S²+K²/4) = 35·10.262 = 359.190, while
the diagnosis uses n/6 exact = 367.742. They agreed only when 6 divides n.

**Fix (decision of David, 6-oct-2026: one JB everywhere).** fue now uses n/6
exact (fue/BUG-0026), like the current C of atsw-gui (`nobs / 6.0`), scipy,
pyfug and art. The diagnosis and the `.out` give the same figure, so the
diagnosis cites one JB. `.out` files written before keep the truncated value.
The old C copies (gtkfue, fue-1.14) are not in use and were left as they are.

**Validation:** `tests/test_bug_0214_el_jb_de_la_diagnosis_y_el_del_out.py`:
with n = 215 (6 does not divide it) the diagnosis line gives exactly the
`.out`'s JB and no second figure. fue: `tests/test_bug_0026_jarque_bera_n_entre_6.py`.
