---
id: BUG-0198
title: El identificador no ve el ciclo de la rata almizclera — con la FAP significativa en 2 y 6 y la FAS oscilante, ni el AR(2) ni el AR(6) de Jenkins y Alavi están entre los cinco primeros; propone AR(1), ARMA(1,2) y MA(1)
status: fixed
severity: high
component: identification
found_in: 0.2.3.dev0
fixed_in: 0.2.3.dev0
reported: 2026-09-29
reporter: David / Claude — análisis guiado de la rata almizclera (Jenkins y Alavi 1981), camino a sima
tags:
  - identification
  - suggest_orders
  - cycles
  - annual
references:
  - src/art/model_detection.py::suggest_orders, _effective_orders, _validate_ar, _theoretical_acf_pacf
  - BUG-0192 (la plantilla del MA), BUG-0194 (los AR de orden alto), BUG-0196 (datos anuales)
  - Jenkins y Alavi (1981) §4.2; Chan y Wallis (1978), Applied Statistics 27, 168-175
---

## Summary

Sobre ∇ln de la rata almizclera (anual, 1851–1911, n = 61, banda ±0,251):

    FAS   0.22 −0.29 −0.13 −0.08 −0.17 −0.25 −0.15 −0.00  0.24
    FAP   0.22 −0.36  0.05 −0.19 −0.16 −0.30 −0.21 −0.24  0.07

la FAP es significativa en **2** y **6** y la FAS oscila con periodo de unos 10
años: un ciclo, que pide un AR con raíces complejas. La lista de
`suggest_orders` (código actual, tras BUG-0192/0194):

    AR(1) 0.736 · ARMA(1,2) 0.731 · MA(1) 0.730 · ARMA(1,1) 0.720 · ARMA(2,1) 0.685

y con el código anterior (el proceso MCP sin reiniciar) MA(1) primero,
justificado como «la FAS se corta en lag 1», con la barra del 1 dentro de la
banda. Ni el **AR(2)** (lo que se ve: la FAP se corta en 2) ni el **AR(6)** de
Jenkins y Alavi (1981) —ARIMA(6,1,1), tres pares complejos de periodos 10,3,
4,2 y 2,6 años— aparecen.

Estimados (fue, sin media):

| modelo | σ̂ₐ | ℓ | AIC | BIC | Q(9) | ciclos del AR |
|---|---:|---:|---:|---:|---|---|
| ARIMA(2,1,0) | 33,2 % | −300,69 | 605,38 | 609,60 | p = 0,052 | 4,7 años (d = 0,62) |
| ARIMA(6,1,0) | 29,7 % | −295,22 | 602,45 | 615,11 | p = 0,023 (3 g.l.) | **9,4 · 4,0 · 2,6 años** (d = 0,92/0,86/0,77) |

LR AR(6) frente a AR(2) = 10,9 con 4 g.l. (p ≈ 0,03). El AR(6) reproduce los
periodos de Jenkins y Alavi; el AR(2) sólo ve un ciclo de 4,7 años.

## Impact

Alto. Es un caso clásico de la literatura multivariante (Jenkins 1975; Chan y
Wallis 1978; Jenkins y Alavi 1981) y la puerta de la escalera a sima: el
analista que siga la lista estima un MA(1) o un AR(1) sobre una serie cíclica.
Y no es exclusivo de este caso: cualquier ciclo no estacional (poblaciones,
ciclos económicos en datos anuales) queda fuera, porque el tope es p ≤ 3 y la
apertura de BUG-0194 sólo mira submúltiplos ESTACIONALES.

## Reproduction

```python
import art
from art.mcp_server import _load_ts_model
ts, _ = _load_ts_model(".../ART/Data/cases/MINK_MUSKRAT/MUSKRAT.inp")
for sp in art.suggest_orders(ts, d=1, D=0, lam=0.0, top_n=5):
    print(sp.p, sp.q, sp.P, sp.Q, round(sp.similarity, 3))
# 1 0 0 0 0.736 · 1 2 0 0 0.731 · 0 1 0 0 0.73 · 1 1 0 0 0.72 · 2 1 0 0 0.685
```

`MUSKRAT.inp` sale de `load_data(mink_muskrat.csv, column="muskrat", freq=1,
start_year=1850)`; los recuentos, en
`atsw-gui/engines/drvec/datasets/mauricio/mink_muskrat.csv`. Los modelos
estimados son `MUSKRAT_m01` (AR(2)) y `MUSKRAT_m02` (AR(6)) del mismo caso.

## Root cause

Por determinar: es el objeto de una revisión A FONDO del identificador para la
siguiente versión (decidida el 29-sep-2026). Sospechosos, con lo ya medido:

1. **La justificación de cada candidato** no mira si la barra que invoca está
   fuera de la banda («la FAS se corta en 1» con r₁ = 0,22 dentro).
2. **Plantillas fijas y similitud**: un AR(2) con coeficientes representativos
   positivos (0,5/(i+1)) no tiene raíces complejas y no reproduce un ciclo; la
   similitud compara valores, no la forma oscilante (BUG-0192 fue el signo del
   MA; aquí es la forma del AR).
3. **El espacio de órdenes**: p ≤ 3 y la apertura de BUG-0194 restringida a
   submúltiplos estacionales; en datos anuales (BUG-0196) no hay ninguno.
4. **La persistencia** como riesgo al abrirlo (el IPC de Chile, I(2), mostró
   que una plantilla ajustada favorece AR altos en series infradiferenciadas).

## Fix

A decidir en la revisión: una regla y una presentación que digan lo que el
correlograma muestra; un patrón cíclico (FAS oscilante, FAP con barras en 2 y
más allá) que proponga un AR con raíces complejas y remita a
`ar_factorization`; ciclos no estacionales como caso propio; datos anuales
como caso propio (BUG-0196); y un banco de casos con respuesta conocida (serie
G, IPC de España, HICP_ES_m01, rata almizclera y visón, IPC I(2) de la tesis),
con el identificador del C (ART_18) como referencia.

## Validation

- Rata almizclera: el AR(2) y un AR de orden alto (6, como Jenkins y Alavi)
  entre los primeros candidatos.
- El banco de casos conocido, sin regresiones (BUG-0192, 0194 y los de la
  tesis).

## Resolution (2026-09-30)

**Root cause, measured.** The port had replaced ART_18's coefficient search by
one «representative» template per order (φᵢ = 0.5/(i+1) …), on the belief that
the pattern does not depend on the coefficients. The representative AR(2),
1 − 0.5B − 0.25B², has REAL roots and cannot oscillate: an AR(2) with complex
roots never looked like its own correlogram. On a bench of simulated series it
came first in 1 of 12 (behind the AR(1)); on the muskrat neither the AR(2) nor
the AR(6) was listed. The C itself carries a second defect, on its own 18.2
plan (§1.3) and not yet fixed there: its stationarity guard rescales any AR
with Σ|φ| ≥ 0.99 to 0.95 (Hannan-Rissanen at 0.95 → 0.90), which flattens the
typical complex AR(2), φ = (1.0, −0.5), a stationary one.

**Fix (option B, decided with the analyst):**

- The templates are SEARCHED again, as in ART_18: Yule-Walker on the empirical
  ACF for a pure AR (every order; the seasonal AR at the seasonal lags); for
  models with an MA, the best of the C's grid (coarse 0.30, refined 0.10) and
  the candidate's own coefficients (Hannan-Rissanen refined by conditional
  least squares).
- `_contract` replaces the C's guard: only a polynomial outside the unit
  circle is pulled in, by cᵢρⁱ, which keeps the roots' angle — the period.
- `_acf_teorica.psi_weights` runs the C's recursion with `scipy.signal.lfilter`
  (identical to 1e-17, ~150× faster), which makes the search affordable.
- The ORDER is the pattern's (the school's reading). Within 0.04 of the best
  similarity: fewer parameters first; at equal count a pure model (AR or MA at
  each level) before a mixed one; then the lower AICc. The AICc of every
  candidate (conditional, common start) and its Akaike weight are
  information; they rank nothing else. Ranking by AICc — the C's
  `rank_shortlist_by_fit` — was measured and rejected: on the difference taken
  once it rewards models that absorb what the formal tests must decide (the
  thesis' I(2) CPIs: an ARMA(1,2) with φ ≈ 1 and an MA root near 1, and the MEG
  verdict changed).
- The C's mixed cells (ARMA p ≤ 3, q ≤ 2 by Hannan-Rissanen and AICc, best
  four) join the candidates: the cut-off gates read pure models only.
- BUG-0194's isolated high AR keeps its place in the list.

**Validation:** `tests/test_bug_0198_el_ar2_con_raices_complejas.py`. Bench
(first place): complex AR(2) 12/12 (monthly, period 6, annual), AR(1), real
AR(2), MA(1) and negative MA(1) 16/16, ARMA(1,1) 0/4 (listed 2nd–4th: the
price of pure before mixed), the muskrat's AR(2) first. Series G's airline
first; the Spanish CPI's airline first and the AR(1)×SMA second; the thesis'
Colombian and Chilean CPIs unchanged. The ARMA(1,2) the AICc prefers on the
muskrat (exact AIC 37.75, as Jenkins and Alavi's ARIMA(6,1,1), against 43.55
of the AR(2)) has an MA root at 0.91: an over-differencing signal (Chan and
Wallis' deterministic trend) for the DCD, not an order.
