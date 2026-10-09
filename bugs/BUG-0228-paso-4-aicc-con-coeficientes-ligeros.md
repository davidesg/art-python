---
id: BUG-0228
title: Paso 4: el ΔAICc de los candidatos se calcula con coeficientes de la identificación ligera y pone primero un ARMA(2,1) (ΔAICc=0,0) cuando el ARMA(1,1) estimado ya está sobreparametrizado
status: wontfix
severity: low
component: identification
found_in: 0.2.3.dev0 @088933d
fixed_in:
reported: 2026-10-08
reporter: David / Claude — análisis GUIADO del IPC de España (P02, Econometría Aplicada UCM)
tags:
  - identificacion
  - criterios
  - sobreparametrizacion
references:
  - src/art/describe.py:811-816
  - bugs/BUG-0225-repro/repro.py
---

## Summary

IPC_ES, `guided_identification(lam=0, d=1, D=0)`: listado de candidatos con ΔAICc
MA(1) +4,6; AR(1) +5,7; ARMA(1,1) +6,0; **ARMA(2,1) +0,0**; ARMA(1,2) +4,0. Con MV exacta
(gretl y fue) el AR(1) y el MA(1) difieren en 1,1 de AIC y el ARMA(1,1) no deja ningún
coeficiente significativo (φ̂ = 0,17 e.t. 0,20; θ̂ = −0,27 e.t. 0,20; corr 0,94).

## Impact

El candidato «mejor por AICc» es el más sobreparametrizado; el alumno que ordena por esa columna empieza por un ARMA(2,1).

## Reproduction

`ART_NO_VIEWER=1 python bugs/BUG-0225-repro/repro.py` (recorre el carril guiado de `IPC_ES.inp`, 2002:01-2019:12, desestacionalizado, en un directorio temporal), bloque **0228**. Guion real del caso: `02-practicas/P02-gtkfue-inp-out/solucion_guiada/IPC_ES/IPC_ES_guion.json` del repositorio del curso.

## Root cause

El ΔAICc sale de un ajuste ligero (no MV exacta), que en modelos mixtos con raíces casi canceladas da verosimilitudes infladas.

## Fix

O calcular el ΔAICc con la estimación exacta de cada candidato, o rotular la columna como orientativa y no ordenar por ella; como mínimo, marcar los candidatos cuyo ajuste ligero tiene raíces AR/MA casi canceladas.

## Validation

Repro, bloque 0228: el ARMA(2,1) no aparece como ΔAICc=0 por delante de AR(1)/MA(1).

## Resolution (2026-10-08)

**Not a defect — retracted by the reporter.** Exact ML in gretl 2023c on the same series: ARMA(2,1) φ̂₁ = −0.464 (0.075), φ̂₂ = 0.282 (0.071), θ̂ = −0.946 in course notation (gretl +0.946, e.t. 0.033), all significant, AIC −1965.5 against −1959.4 for the AR(1): 6 points better, as art's ΔAICc said. The report's claim ("el ARMA(1,1) ya está sobreparametrizado, luego el (2,1) también") does not follow. What the (2,1) shows is an AR root at −1.23 and an MA root at −1.06 that almost cancel at frequency π — probably a remnant of the harmonic seasonal adjustment of IPC_ES_SA. That is worth reading with `ar_factorization`, not a ranking bug.

Repro: `bugs/BUG-0225-repro/repro.py`. Tests: `tests/test_bug_0225_0231_guiado_ipc_es.py`.
