---
id: BUG-0215
title: formal_tests: una raíz AR en −0,99 se lee como raíz unitaria en +1; cierra «el modelo es adecuado» con el par discrepando; «ningún contraste aplicable» tras dar el DCD; «medido sin AR» con un testigo que depende del AR
status: fixed
severity: medium
component: formal-tests
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - formal-tests
  - shin-fuller
  - dcd
references:
  - src/art/formal_tests.py
---

## Summary

- Moncloa ARIMA(1,2,2): φ = −0,9855 (frecuencia π) tomado como raíz cerca de +1: «raíz
  unitaria, considerar d+1»; el texto del par invierte qué lado dice qué.
- Latina AR(4): cierra con «no detectan problemas. El modelo es adecuado» con Shin-Fuller y DCD
  discrepando fuera de la banda de cuasi-cancelación.
- IPC_DE (0,1,0) con μ: devuelve el DCD y a continuación «Ningún contraste aplicable a esta
  especificación».
- El texto del DCD dice «medido sin AR», pero el θ̂ testigo cambia con el modelo base
  (Salamanca: 0,93 sobre el AR(4), 0,81 sobre el ARMA(1,1)).

## Impact

Conclusiones formales falsas o contradictorias; en Moncloa, una recomendación de d+1 por una raíz en la frecuencia π.

## Reproduction

`formal_tests` sobre los modelos citados en `02-practicas/P02-gtkfue-inp-out/solucion/<Serie>/` del repositorio del curso (Moncloa ARIMA(1,2,2); Latina AR(4) en ∇ln; IPC_DE (0,1,0)).

## Root cause

Shin-Fuller toma la raíz de mayor módulo sin mirar su argumento; el cierre no lee el par; el mensaje de aplicabilidad se evalúa antes de añadir el DCD.

## Fix

Filtrar por raíces reales positivas cerca de +1; que el cierre dependa del par; ordenar los mensajes; aclarar qué AR queda en el testigo.

## Validation

Los cuatro casos.

## Resolution (2026-10-06)

**Fix.** Shin-Fuller only ever tests a POSITIVE real AR root, the one closest
to +1: `d` is about a unit root at +1. It used to take the smallest-modulus
root and compare |φ̂| with ρₘ, so φ̂ = −0.9855 (frequency π, Moncloa
ARIMA(1,2,2)) read as a root at +1 and printed "considerar d+1". If the AR has
no positive real root there is no statistic: the report says «no aplica: el
AR no tiene raíz real positiva; en f=0 decide el DCD». A real root at φ ≤ −0.9
only gets a note pointing to the Nyquist (1 + B) tests. The f=0 pair is then
one-sided, and the closing says so instead of "coinciden" or "discrepa"
(decision of David, 6-oct-2026: d+1 only concerns positive roots).

The f=0 pair text says which side says what in both directions. The closing
reads the pair: a discrepancy outside the quasi-cancellation band, or a single
DCD side pointing to d+1, goes to "no piden reformular, pero no cierran"
(`data["pendientes"]`) instead of "El modelo es adecuado". "Ningún contraste
aplicable" now counts the over/under-differencing DCDs. The DCD block states
that the base model's AR stays in the candidate (re-estimated), so θ̂ depends
on it; "medido sin AR" refers to fue's likelihood validation.

On the P02 files: Moncloa ARIMA(1,2,2) goes from "considerar d+1" to
«Shin-Fuller no aplica (φ̂ = −0.9855, nota Nyquist); en f=0 decide el DCD: d basta»; Latina AR(4) no longer ends
in "adecuado"; IPC_DE (0,1,0) no longer says "ningún contraste" after the
DCD; Salamanca's candidate names the AR it keeps.

**Validation:** `tests/test_bug_0215_formal_tests_raiz_negativa_y_cierres.py`:
- a negative root (φ̂ ≈ −0.984 with |φ̂| > ρₘ, and φ̂ = −0.3) gives no
  Shin-Fuller statistic and «no aplica … decide el DCD»; with a positive and a
  negative root, the positive one is tested;
- the pair in both directions, inside and outside the band, and the
  closing for each;
- no "Ningún contraste" after the DCD;
- the witness line with and without AR.
`test_mcp_server`'s RIPC1 case asserted the old contradiction and now asserts
the DCD block; `test_f0_confirmatory_pair` (φ̂ = −0.04) now expects the DCD alone.
