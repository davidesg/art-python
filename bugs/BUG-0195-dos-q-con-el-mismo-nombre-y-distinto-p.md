---
id: BUG-0195
title: Dos Ljung-Box con el mismo rótulo «Q(39)» y veredictos opuestos — el escaneo de anómalos no descuenta los parámetros ARMA (p = 0,179, «pasa») y la diagnosis sí (p = 0,043, «falla») pero lo rotula por el retardo, no por los grados de libertad
status: fixed
severity: high
component: diagnosis
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-29
reporter: David — análisis guiado del HICP de España 2002-2019 (P03)
tags:
  - ljung-box
  - degrees-of-freedom
  - diagnosis
  - presentation
references:
  - src/art/describe.py (escaneo pre-identificación, ~l. 3326-3336 y 3537-3541)
  - src/art/diagnosis.py (~l. 795-797: ljung_box(..., df_correction=n_arma))
  - src/art/identification.py (~l. 214-220, 509: la figura rotula Q(df))
---

## Summary

Sobre el mismo modelo (`HICP_ES_m02`: AR(6) + AR(1)₁₂ + 11 armónicos + μ; 7
parámetros ARMA), una misma salida de `confirm_and_estimate` da:

| Dónde | Rótulo | Estadístico | p | Veredicto |
|---|---|---:|---:|---|
| Diagnosis | «Q(39)=46.95» | 46,95 | **0,0428** | ✗ falla |
| Escaneo de anómalos | «Q(39) = 47.0 … (Ljung-Box, la misma que la figura de diagnosis)» | 47,0 | **0,179** | ✓ «pasa» |
| Figura de diagnosis | «Q(32) = 47.0» | 47,0 | — | — |

χ²₃₂(46,95) → p = 0,0428; χ²₃₉(46,95) → p = 0,1789. **La correcta es la de la
diagnosis**: 39 retardos menos 7 parámetros ARMA = 32 grados de libertad, que es lo
que rotula la figura. Pero la diagnosis escribe «Q(39)» (el retardo) y el escaneo
calcula y rotula «Q(39)» con 39 g.l. (sin descontar nada) y además afirma ser «la
misma que la figura».

## Impact

Alto. El escaneo dice «la Q ya pasa, así que esto mide cuánto se mueve, no un
problema que arreglar» sobre un modelo cuya Q rechaza al 5 %, y con ello
desaconseja actuar. Con 7 parámetros la diferencia de p es de 0,04 a 0,18: cruza el
umbral. Y el lector ve dos «Q(39)» con p distintos sin forma de saber cuál vale. El
error crece con el número de parámetros: justo en los modelos más ricos, donde la
decisión de parar o seguir es más fina.

## Reproduction

```
art> confirm_and_estimate(inp=HICP_ES_m01.pre, base_pre_path=HICP_ES_m01.pre,
                          lam=0, d=1, D=0, p=6, q=0, P=1, estimate_mu=True)
# Diagnosis: «Ruido blanco (Q): ✗ Q(39)=46.95, p=0.0428»
# Escaneo:   «Q(39) = 47.0 (p=0.179) — pasa (Ljung-Box, la misma que la figura…)»
# Figura:    «Q(32) = 47.0»
```

Ficheros: `Econometria Aplicada GD/03-datos/ejemplos/HICP_ES/`.

## Root cause

- `describe.py`, escaneo pre-identificación: `_lb(w_std, [_k])` sin
  `df_correction` ⇒ p con `_k` g.l.; y el texto rotula `Q({q_lag})` añadiendo «la
  misma que la figura de diagnosis», que no lo es.
- `diagnosis.py`: `ljung_box(r, q_check_lags, df_correction=n_arma)` ⇒ p bien
  calculado, pero el informe rotula `Q(<retardo>)`.
- `identification.py` (figura): rotula `Q({ljung_box_df})`, con el retardo menos
  los parámetros — la única de las tres que dice lo que calcula.

## Fix

- Un solo cálculo de la Q de residuos, con `df_correction = nº de parámetros ARMA`,
  compartido por la diagnosis, el escaneo y la figura.
- Un solo rótulo que diga las dos cosas: «Q(39 retardos, 32 g.l.) = 46,95, p =
  0,043».
- El escaneo no debe decir «pasa» ni orientar la decisión con un p distinto del de
  la diagnosis; si lo necesita, que reutilice el de la diagnosis.

## Validation

- `HICP_ES_m02`: las tres salidas deben dar p = 0,043 y el mismo veredicto.
- Un modelo sin ARMA (p = q = P = Q = 0): los g.l. coinciden con el retardo y nada
  cambia.
- Test: escaneo y diagnosis devuelven el mismo p sobre el mismo `.pre`.

## Resolution (2026-09-29)

- `diagnosis._q_lags_and_df`: the lags and the ARMA parameters discounted,
  in one place; `diagnosis.q_decisive(model)` gives the Q that decides (3f+3)
  as the diagnosis computes it: (lag, df, statistic, p).
- The scan of a model's residuals (`describe_prelim_scan(..., q_model=m)`,
  from the three call sites that scan residuals) publishes THAT Q; without a
  model (the series before identification) it says that df = lags.
- One label everywhere: «Q(39 retardos, 32 g.l.)» in the diagnosis and the
  scan, «Q(39 lags, 32 df)» in the figures; `DiagnosisResult.q_df_correction`
  carries the discount and the summary table shows df per lag.

**Validation:** `tests/test_bug_0195_una_sola_q_de_residuos.py`. HICP_ES_m02:
diagnosis and scan both Q(39 retardos, 32 g.l.) = 46.95, p = 0.043, RECHAZA.
