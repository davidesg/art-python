---
id: BUG-0210
title: Nodo d: la tabla ADF+KPSS marca «ambiguo» y el resumen dice «primera diferencia con consenso»; y textos que contradicen sus p-valores
status: fixed
severity: low
component: identification
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - identificacion
  - orden-de-integracion
  - texto
references:
  - src/art/mcp_server.py (guided_identification, Call 2/3)
  - bugs/BUG-0208-repro/repro.py
---

## Summary

En Retiro y Salamanca la fila de ∇ln dice «ambiguo ⚠» (ADF rechaza, KPSS rechaza) y el
resumen concluye «d = 1 (primera diferencia con consenso)». Variantes reportadas: «⚠ El ADF
sobre ∇log(y) no rechaza» con ADF p=0,031 (Salamanca) o p=0,000 (IPC_ES), y una fila que
concluye «d=0» cuando d=2 es el único orden con consenso de los dos contrastes (IPC_ES).

## Impact

El texto contradice la tabla que tiene al lado; quien lee el resumen no ve la ambigüedad.

## Reproduction

`bugs/BUG-0208-repro/repro.py`, bloque 0210: `guided_identification('Retiro.inp', lam=0)`.

## Root cause

El resumen se escribe con una plantilla que no lee el veredicto de la fila.

## Fix

Que el resumen use el veredicto de la tabla («ambiguo» ⇒ no decir «consenso») y que la frase del ADF lea su propio p.

## Validation

Repro, bloque 0210.

## Resolution (2026-10-06)

**Fix.** The d reported by `describe_unit_root` is unchanged (`recommended_d`,
the ADF decides, BUG-0002). The sentence "Lo que encuentran los contrastes" now
reads that row's verdict instead of a template keyed on d. When the row is not
"estacionaria" it says which test disagrees, with both p-values, "ambigua, sin
consenso", and names the order(s) where both tests agree, or says there are
none. The ADF/KPSS line in `describe_seasonality` reads its own p: "El ADF …
no rechaza (p=…)" only when it does not reject; otherwise "rechaza la raíz
unitaria (p=…), pero el KPSS rechaza la estacionariedad (p=…)".

The repro (block 0210, Retiro) now prints:

    **Lo que encuentran los contrastes**: d = 1 — la primera fila en la que el ADF rechaza la raíz unitaria (p=0.0230), pero el KPSS rechaza la estacionariedad (p=0.0100): fila **ambigua**, **sin consenso**; ningún orden de la tabla tiene el consenso de los dos.

IPC_ES at step 3: "…; el único orden con consenso de los dos contrastes es d=2".

**Validation:** `tests/test_bug_0210_ambiguo_no_es_consenso.py` (crafted
ADF/KPSS tables): the Retiro and IPC_ES cases, the unchanged "con consenso"
sentence, and the seasonality-support line with ADF p=0.031 / p=0.52.
The first four fail on the old code.

Still open for the maintainer: IPC_ES's d=0 at step 2 comes from the ADF-first rule;
only the wording changed.

**Addendum (2026-10-06).** The IPC_ES figures in this report come from
IPC_ES_SA, the *seasonally adjusted* Spanish CPI of P02
(`bugs/BUG-0208-repro/IPC_ES_SA.inp`), not the historical IPC_ES of
BUG-0015. On that series the constant-only ADF rejects at d=0 (p=0.036; with a
trend term p=0.87) because the series is concave: growth slows from 3.3 to 1.6
to 0.7 %/yr. A line explains 91 % of the level, so `policy.decide_d` already
starts at d=1. The ADF port is correct (it matches statsmodels). That ADF and
KPSS contradict each other here is what low power looks like, not the defect.
The defect was that art spoke as if the test had decided: the "Punto de
partida" block used the step-cap template (with the seasonality-bias paragraph,
although the ADF had rejected), step 2 printed "Recomendación ADF+KPSS: d = 0"
under a starting point of d=1, and the summary opened with "d = 0".

Commit 25c7df6 (text only, `decide_d` unchanged) writes this node as evidence.
The new `policy.razon_d()` says which rule set d. With the trend rule the
text says the clear trend and the slowly decaying ACF decide d, the table is
support, and here the ADF has no power (no trend term in its regression);
the step-cap template stays for d ≥ 2. Step 2 shows the d the analysis
actually starts from: "d = 1 (la tabla ADF+KPSS, sola, apuntaría a d=0: es
apoyo, no veredicto)", with the matching call marked as recommended. An
ambiguous row is reported as "sin consenso" and never as stationarity. Tests:
four more in `tests/test_bug_0210_ambiguo_no_es_consenso.py` (trend-rule vs
step-cap text, `razon_d` against `decide_d`, the step-2 line).
