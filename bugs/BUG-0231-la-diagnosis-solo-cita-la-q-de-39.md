---
id: BUG-0231
title: La diagnosis de confirm_and_estimate sólo cita la Q(39) («decide 3f+3»); la Q en s y 2s (12 y 24) no aparece, aunque el método y el guion la piden
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.3.dev0 @088933d
fixed_in: 0.2.3.dev0
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - diagnosis
  - ljung-box
  - guion
references:
  - src/art/describe.py:1988
  - BUG-0207 (D3: q_pass lo decidía la Q(39))
  - bugs/BUG-0225-repro/repro.py
---

## Summary

En los cuatro modelos de IPC_ES la sección de diagnosis da una sola línea: «Ruido blanco (Q): ✓
Q(39 retardos, 37 g.l.)=21.26, p=0.9822 — decide 3f+3». Las Q en 12 y 24 hubo que calcularlas
aparte (gretl): MA(1) p = 0,42/0,71; AR(1) p = 0,66/0,89. BUG-0207 corrigió que `q_pass` se
decidiera sólo con la Q(39), pero la salida sigue sin mostrar las otras.

## Impact

El guion y la rúbrica piden la Q en 12, 24 y 39; un modelo con r₁ fuera de banda puede pasar la Q(39) (BUG-0207, ES_CORE m01) y el alumno no ve la Q(12) que lo delata.

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0231**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

La diagnosis imprime sólo el «cancerbero» 3s+3.

## Fix

Una línea con las tres: «Q(12) = …, p = … · Q(24) = …, p = … · Q(39) = …, p = … (decide 3s+3)», con sus grados de libertad.

## Validation

Repro, bloque 0231: la salida cita Q(12) y Q(24).

## Resolution (2026-10-08)

The diagnosis line keeps the verdict of 3s+3 ("decide 3f+3") and adds the other Ljung-Box lags it already computed: "· Q(12)=8.52, p=0.5786 · Q(24)=15.06, p=0.8598 · Q(36)=18.50, p=0.9859".

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
