---
id: BUG-0218
title: Los anómalos de la diagnosis van sin fecha y con un número de observación relativo a los residuos, que cambia con d; y su z difiere del .out en el segundo decimal
status: fixed
severity: low
component: diagnosis
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - anomalos
  - presentacion
  - fechas
references:
  - src/art/diagnosis.py
  - src/art/mcp_server.py (confirm_and_estimate §2)
---

## Summary

«Residuos extremos (|z|>3): obs 149 (z=+3,56)»: el índice es del vector de residuos (obs 1 =
2010:02 con d=1 y 2010:03 con d=2): 2025:03 es la obs 182 con d=1 y la 181 con d=2. El `.out`
da 3,57.

## Impact

El enunciado pide los anómalos con fecha y nombre; con el número hay que contar a mano, y cambia al cambiar d.

## Reproduction

Cualquier distrito de `solucion/` con un anómalo, estimado con d=1 y con d=2.

## Root cause

Se imprime el índice del vector de residuos sin convertirlo a fecha.

## Fix

Imprimir la fecha (como ya hace el escaneo latente) y la misma z que el `.out`.

## Validation

Un anómalo da la misma fecha con d=1 y d=2.

## Resolution (2026-10-06)

**Fix.** The extreme residuals are printed with their date, the `.out`'s
observation number and the `.out`'s z: the z now divides by the population SD
(ddof=0, as fue's «Table of standardized values»), and the date comes from
`desfase_observaciones` (`DiagnosisResult.extreme_dates`,
`etiqueta_extremo`).

IPC_US AR(2) now prints:

    Residuos extremos (|z|>3): 3 — 11/2008 (obs 82, z=-5.50), 10/2008 (obs 81, z=-4.18), 09/2005 (obs 44, z=+4.14)

This matches the `.out` table row for row. On the course files, Carabanchel
(0,2,1) gives 01/2014 (obs 47, z=+3.09), Chamartín gives 05/2010 (obs 4,
z=+3.60), and ES_CORE m01 gives 09/2012 (5.12) and 01/2009 (−3.08). All are
identical to their `.out`.

**Validation:** `tests/test_bug_0218_anomalos_con_fecha.py`:
- a pulse in 03/2025 is dated 03/2025 with d=1 (obs 182) and with d=2
  (obs 181);
- every extreme's z equals the `.out` table's to two decimals.
