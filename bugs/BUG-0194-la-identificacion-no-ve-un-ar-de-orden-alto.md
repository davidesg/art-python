---
id: BUG-0194
title: La identificación no puede proponer un AR de orden mayor que 3 — p_max=3 y el corte «tres retardos seguidos no significativos» dejan fuera el AR(6) que la FAP pide en una serie mensual con rebajas semestrales
status: fixed
severity: high
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-29
reporter: David — análisis guiado del HICP de España 2002-2019 (P03 de Econometría Aplicada)
tags:
  - identification
  - suggest_orders
  - seasonal
  - ar-order
references:
  - src/art/model_detection.py::suggest_orders (p_max=3, q_max=3, P_max=1, Q_max=1)
  - src/art/model_detection.py::_effective_orders._last_sig
  - BUG-0192 (mismo componente: la plantilla del MA con signo fijo)
---

## Summary

Sobre los residuos de un modelo B1 del HICP de España (∇ln, 11 armónicos, media y
AR(1)₁₂; `HICP_ES_m01`), la FAP tiene barras significativas en **1 (+0,18) y 6
(+0,23)**, con 7 y 8 rozando la banda y el 18 fuera (+0,19): la firma de un AR que
llega al retardo 6 —la onda de las rebajas, dos al año—. `guided_identification`
(Call 4 con `pre_path`) propone ARMA(1,1), MA(1) y AR(1), y nada más. Lo mismo
pasa un paso antes (residuos de m00, sin AR estacional): barra de 0,42 en la FAP del
6 y la lista propone MA(2) y AR(1)₁₂. **Ningún candidato puede recoger el retardo 6.**

## Impact

Alto. En series mensuales de precios la onda de 6 meses es habitual (rebajas,
temporadas), y la identificación la ignora de forma estructural: el analista que
siga la lista reformula a ciegas en los retardos bajos y el 6 sigue en los residuos.
Es además el retardo que distingue una estacionalidad que se mueve en f = 2, así
que la lista esconde justo la evidencia de la decisión estacional.

## Reproduction

```python
art> load_data(hicp_ES_2002_2019.csv, freq=12, start_year=2002)          # HICP ES, Eurostat prc_hicp_minr, I25
art> confirm_and_estimate(lam=0, d=1, D=0, p=0, q=0, n_harmonics=5, estimate_mu=True)   # m00
art> confirm_and_estimate(base_pre_path=m00.pre, P=1, estimate_mu=True)                   # m01
art> guided_identification(lam=0, d=1, D=0, pre_path=m01.pre)
# → ARIMA(1,0,1) 0.919 · (0,0,1) 0.885 · (1,0,0) 0.864      — ningún p > 1
# FAP de los residuos de m01: r₁ = +0,18, r₆ = +0,23 (banda ±0,13)
```

Ficheros: `Econometria Aplicada GD/03-datos/ejemplos/HICP_ES/` (`HICP_ES.inp`,
`HICP_ES_m00.pre`, `HICP_ES_m01.pre`).

## Root cause

Dos límites, y cualquiera de los dos basta:

1. **`suggest_orders(p_max=3, …)`**: el espacio de búsqueda regular acaba en 3. Un
   AR(6) no se evalúa nunca.
2. **`_effective_orders._last_sig`** recorre la FAP y **corta en cuanto encuentra tres
   retardos seguidos dentro de la banda**. Aquí 2, 3, 4 y 5 están dentro (−0,09,
   +0,09, −0,05, +0,05), así que `eff_p` = 1 aunque `p_max` fuera 6 y el retardo 6
   esté claramente fuera. La regla está pensada para no perseguir ruido en retardos
   altos, pero en datos estacionales se come la submúltiplo estacional s/2.

## Fix

Criterio de la escuela (David, 29-sep-2026): **los órdenes altos sólo tienen sentido
en los operadores AR.** En MA el espacio razonable es como mucho **q ≤ 2 en la parte
regular y Q ≤ 1 en la estacional**; órdenes mayores en MA casi no se ven. Propuesta:

- AR regular: `p_max` hasta `s/2` en datos estacionales (6 en mensual, 2 en
  trimestral), manteniendo 3 en no estacionales.
- MA: `q_max = 2`, `Q_max = 1` —más estrecho que hoy (`q_max = 3`)—.
- `_last_sig` para la FAP: no cortar antes de mirar los retardos s/2 (y sus
  múltiplos que caigan dentro de `p_max`); si uno de ellos es significativo, `eff_p`
  llega hasta él.
- El candidato de orden alto se propone como **polinomio completo** (sin ceros
  impuestos, BUG-0095) y la salida remite a `ar_factorization` para leer qué
  factor esconde (aquí, previsiblemente, un par de periodo ≈ 6 meses).

## Validation

- HICP de España, residuos de m01: un AR(6) (o AR(p) con p ≥ 6) debe aparecer en la
  lista.
- El airline (serie G) y los casos dorados del proyecto no deben cambiar de primer
  candidato.
- Test de regresión: FAP sintética con barras sólo en 1 y s/2 ⇒ `eff_p` = s/2.

## Resolution (2026-09-29)

**Three limits, not two.** Besides `p_max = 3` and the cut on three quiet
lags, the representative AR template 0.5/(i+1) (the C's high-order
fallback) is NOT STATIONARY for p >= 4 — it sums to 1.04 at p = 4 and 1.225
at p = 6 — so `_theoretical_acf_pacf` returned None and the candidate
vanished in silence. No AR of order 4 or more could ever enter the list, in
the port or (by the same formula) in the C.

**Fix**, with the school's criterion:
- `p_max` defaults to max(3, s/2): 6 in monthly data, 3 in quarterly and
  annual (s/2 = 2 would have lowered today's 3 in quarterly data). MA:
  `q_max = 2`, `Q_max = 1`.
- `_effective_orders`: the regular AR search stays at 3 as before; an AR of
  order s/2 (or a multiple within `p_max`) enters ONLY when the PACF bar at
  s/2 is significant and ISOLATED — every lag from 4 to s/2 − 1 inside the
  band —, which is this report's pattern. Decided after measuring the
  alternative: letting every AR up to s/2 compete made an AR(6) win on
  Chile's ∇ln CPI (an I(2) series; PACF significant at 1, 2, 3, 5, 6, ACF
  0.62 … 0.43 at lag 12), where the high order is persistence, not a wave:
  the AR(6) absorbed part of the unit root and the final DCD's evidence for
  d + 1 fell from LR 88.1 to 9.1. With the isolation rule Chile's lane is as
  before. With no significant bar the search opens to 3, not to `p_max`.
- Generalised on the analyst's remark: with HYBRID seasonality and only a
  regular AR specified, a high-order AR can show at any badly represented
  seasonal frequency, not only at f = 2. Every submultiple s/k >= 4 within
  `p_max` is looked at with the same isolation rule (monthly: 6, f = 2, and
  4, f = 3; quarterly: none). The listing says so and points to
  `ar_factorization` (the frequency of the factor) and to the MEG, which is
  what settles the specification of that frequency.
- For a complete AR of order >= 4 the template is the AR(p) of Yule-Walker
  on the empirical ACF (what an AR(p) looks like on these data), with the
  representative one scaled to sum 0.8 as fallback if that is not stationary.
  Decided on the evidence: on the residuals of HICP_ES_m01, AR(6) similarity
  0.767 with Yule-Walker against 0.473 with the scaled template. Orders <= 3
  are unchanged.
- A high-order candidate is shown as the complete polynomial, and the listing
  points to `ar_factorization` to read what factor it hides.

**Validation:** `tests/test_bug_0194_la_identificacion_ve_un_ar_de_orden_alto.py`
(including a block of significant lags that must NOT open the high order),
and `tests/test_thesis_i2_chile_colombia.py` unchanged.
HICP_ES_m01 residuals: ARMA(1,1) 0.919, MA(1) 0.885, AR(1) 0.864, **AR(6)
0.767**, ARMA(6,1) 0.528. Series G and Spain's CPI keep their first
candidates (BUG-0192's tests).
