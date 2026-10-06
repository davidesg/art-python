---
id: BUG-0213
title: «La Q falla en el retardo 12» se lee como «falta estructura estacional»: la Q(12) acumula los retardos 1-12, y lo que falla es el 1
status: fixed
severity: medium
component: diagnosis
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - diagnosis
  - ljung-box
  - reformulacion
references:
  - src/art/mcp_server.py (confirm_and_estimate, §4 alternativa B)
---

## Summary

ES_CORE (IPC subyacente de España, INE, 2002-2019), m01 = (0,1,0)(0,1,1)₁₂: falla r₁ = 0,26
(FAP que corta en 1); r₁₂ = −0,07. La alternativa B dice «Añadir estructura ESTACIONAL — la Q
falla en un retardo estacional, que es donde se ve lo que los armónicos no absorben» y propone
P=1.

## Impact

Sugiere la reformulación equivocada justo donde el alumno tiene que aprender a mirar QUÉ retardo falla.

## Reproduction

Serie `ES_CORE` (SF_MEG/empirical/data, 2002-01…2019-12): `confirm_and_estimate(lam=0, d=1, D=1, p=0, q=0, P=0, Q=1, estimate_mu=False, domain='price_index')`. El ejemplo está en `02-practicas/P04-art-identificacion/ejemplo_ES/ES_CORE_m01.*` del repositorio del curso.

## Root cause

La alternativa se elige por el retardo de la Q que rechaza (12), no por la barra de la FAS que falla.

## Fix

Elegir la alternativa por las barras fuera de banda (retardos bajos ⇒ parte regular; s, 2s ⇒ estacional), no por el retardo de la Q.

## Validation

ES_CORE m01 propone la parte regular.

## Resolution (2026-10-06)

**Fix.** The ARMA alternative is chosen by the residual ACF/PACF bars outside
±2/√n (`DiagnosisResult.fas_fuera`/`fap_fuera`), not by the lag of the
rejecting Q: lags 1–3 ⇒ regular order; s, 2s ⇒ seasonal; both ⇒ both,
regular first. The conclusion says each Q(k) accumulates lags 1…k and names
the bars. The current order no longer counts the (0,d,0) AR placeholder.

On the course file `ejemplo_ES/ES_CORE`, m01 = (0,1,0)(0,1,1)₁₂:

    Barras de la FAS/FAP de los residuos fuera de banda: 1, 3, 5, 15.
    B) Subir el orden regular — hoy AR(0) MA(0); … retardo(s) 1, 3.

No seasonal alternative is offered.

**Validation:** `tests/test_bug_0213_la_q_de_12_no_es_el_retardo_12.py`: a
synthetic (0,1,1)(0,1,1)₁₂ fitted as m01 (Q(12) rejects through r₁):
- the regular part is proposed, not the seasonal one, with «hoy AR(0) MA(0)»;
- the conclusion names bar 1;
- a bar at 12 proposes seasonal structure;
- bars at 1 and 12 give both, regular first.

With the old code, three of the five tests fail.
