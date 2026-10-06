---
id: BUG-0211
title: confirm_and_estimate da en la misma salida «REVISAR ✗ / reformulación necesaria» y «No procede reformular: el modelo se sostiene»
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - diagnosis
  - contradiccion
  - veredicto
references:
  - src/art/mcp_server.py (confirm_and_estimate, §2-§4)
  - BUG-0036, BUG-0042 (predicados de adecuación)
---

## Summary

Casos de la P02: Chamartín ARMA(1,1) (estacionalidad residual), Chamberí m01, Carabanchel
ARIMA(0,2,1). La sección de diagnosis concluye REVISAR por la estacionalidad residual y la §4
dice que el modelo se sostiene.

## Impact

Dos predicados de adecuación otra vez divergentes (cf. BUG-0036, BUG-0042): el autónomo no sabe cuál seguir.

## Reproduction

Estimar en modo autónomo `solucion/Chamartin` ARMA(1,1) en ∇ln con μ (o el m01 de Chamberí): las dos frases salen juntas. Las `.inp` están en `02-practicas/P02-gtkfue-inp-out/solucion/<Serie>/` del repositorio del curso.

## Root cause

La §4 no incorpora la estacionalidad residual que sí entra en el veredicto de la §2.

## Fix

Un solo predicado: si el veredicto es REVISAR, la §4 no puede decir «no procede reformular».

## Validation

Los tres casos dan una conclusión coherente.

## Resolution (2026-10-06)

**Fix.** The §3 conclusion, the §4 reformulation and the "Adoptar" alternative
now read one predicate, `_adecuado()` = `DiagnosisResult.clean`, the same one
that writes «APROBADO ✓ / REVISAR ✗». `describe_diagnosis` publishes the two
criteria that were missing from its data (`centred`/`mean_t`,
`seasonal_residual`/`seasonal_p`), and the alternatives gain «Añadir la media»
and «Tratar la estacionalidad residual».

On the course files, Chamartín ARMA(1,1) and Carabanchel ARIMA(0,2,1) now say:

    Veredicto: REVISAR ✗ … ⚠ Estacionalidad residual: F=1.92, p=0.0399
    §4: El modelo NO se sostiene: queda estacionalidad en los residuos (p=0.0399).

(Carabanchel: p=0.0203.) IPC_ES_SA AR(1) without μ (the mean case) says «la
media residual NO es cero (t=+4.03)».

**Validation:** `tests/test_bug_0211_veredictos_contradictorios.py`:
- a REVISAR by the mean or by residual seasonality is never «se sostiene» or
  «No procede reformular», and is never offered «Adoptar»;
- `clean=False` with no named reason still does not hold;
- an APROBADO still holds and offers «Adoptar»;
- end to end: a random walk with drift fitted without μ (Q ✓, JB ✓) gives
  REVISAR and a §4 that names the mean.

With the old code, four of the five tests fail.
