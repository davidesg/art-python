---
id: BUG-0212
title: El escaneo latente de anómalos se contradice: «distorsión leve, ACF_max=0 %» y «SÍ cambian la identificación… NO fijes p y q»; «distorsión fuerte» por retardos dentro de banda; cambios de veredicto por cruces mínimos de banda
status: fixed
severity: medium
component: calibracion
found_in: 0.2.3.dev0 @a33b893
fixed_in: 0.2.3.dev0
reported: 2026-10-06
reporter: David / Claude — resolución de la P02 de Econometría Aplicada (UCM) con art en modo autónomo, 15 series y cuatro analistas
tags:
  - anomalos
  - calibracion
  - contradiccion
references:
  - src/art/calibracion.py
  - src/art/mcp_server.py (escaneo latente en confirm_and_estimate, residual_outlier_scan)
---

## Summary

- «distorsión leve/moderada (ACF_max=0 %)» junto a «SÍ cambian la identificación… NO fijes p
  y q todavía», en modelos ya adecuados (IPC_ES MA(1); Latina, Carabanchel, Moncloa, Retiro).
- «Distorsión fuerte… ACF_max=38 %» por retardos dentro de banda (Villaverde).
- «cambia de veredicto» por cruces mínimos: r5 de 0,157 a 0,118 con banda ±0,136 (IPC_ES); r12
  de 0,161 a 0,143 con banda ±0,146 (Salamanca).
- `residual_outlier_scan` (IPC_ES): «distorsión leve, razonable pasar a ARMA» y «cambia la
  identificación, interviene antes» en la misma salida.

## Impact

En la P02 empujó a los cuatro analistas a considerar intervenciones que el alcance prohibía; un alumno las tomaría.

## Reproduction

`confirm_and_estimate` del MA(1) de `solucion/IPC_ES` (∇ln con μ) en modo autónomo; `residual_outlier_scan` sobre su `.pre`.

## Root cause

El veredicto «cambia la identificación» se dispara por cualquier cruce de banda, sin margen, y es independiente de la medida de distorsión que se imprime al lado.

## Fix

Un margen para el cruce (p. ej. que la barra pase de claramente fuera a claramente dentro) y que el veredicto sea coherente con ACF_max; en modelos adecuados, no ordenar «no fijes p y q».

## Validation

Los casos citados dan un solo mensaje coherente.

## Resolution (2026-10-06)

**Fix.** A band crossing now needs a margin: a lag changes verdict only from
|r| > 1.25·band to |r| < 0.75·band (or back), at least one standard error of
r(k) (1/√n, half the band) across the edge (`MARGEN_CRUCE = 0.25`). Smaller
crossings are named as marginal and decide nothing.
The calibration decides on the lags that identify the model: the regular
lags 1–12 (capped by n/4) and, when there is seasonality, s, 2s and 3s, each
capped by n/4 (decision of David, 6-oct-2026). "There is seasonality" comes
from the scanned model (D ≥ 1, seasonal AR/MA, harmonics or ifadf). Without a
model it comes from the D passed in, or else from the identification step's
`detect_seasonality`. A lag outside the window, like Villaverde m07's k=28
(ACF_max 97 %), never decides, and the verdict names the window («retardos
1–12 y 24, 36»). `describe_prelim_scan`
now calibrates with the same omitted points and reconciles its level with that
calibration: "cambia" is never "leve", "no cambia" is never "fuerte". Its
band is 2/√n like the calibration's (it was 1.96/√n). The latent line in
`confirm_and_estimate` reads that single verdict. With ARMA already estimated
it no longer orders "NO fijes p y q": a fabricated residual spike asks for no
order, a masked one points to `residual_outlier_scan`.

On the P02 files: IPC_ES_SA MA(1) gives one message ("leve", no lag changes,
r(5) named as marginal), in the latent line and in `residual_outlier_scan`.
Moncloa AR(4) and Villaverde m02/m05/m06 stop saying "SÍ cambian".
Villaverde m07 goes from "fuerte, ACF_max=97 %" to "moderada: la magnitud
es grande, pero ningún retardo de 1 a 12 cambia" (the 97 % is lag 28).

**Validation:** `tests/test_bug_0212_el_escaneo_latente_no_se_contradice.py`:
- the IPC_ES_SA, Salamanca and RATIO crossings no longer flip, a clear one
  still does, and the margin equals one standard error;
- `nivel_coherente` over the whole table;
- on 40 synthetic series, "fuerte" ⇒ cambia, "leve" ⇒ no cambia, and the
  scan agrees with the calibration table;
- the latent line with ARMA (fabricated, masked, no change) never says
  "NO fijes p y q";
- `residual_outlier_scan` gives one verdict;
- a clear flip at lag 24 decides on a monthly seasonal model and not on a
  non-seasonal one; lag 28 never decides.
The old code cannot import the test.

**Nota (2026-10-06).** El «IPC_ES» de este informe es IPC_ES_SA, el IPC de España *desestacionalizado* de la P02 (`bugs/BUG-0208-repro/IPC_ES_SA.inp`), no el IPC_ES histórico de BUG-0015.
