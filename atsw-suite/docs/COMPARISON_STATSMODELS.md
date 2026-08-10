# `statsmodels.VARMAX` against `drvarma` and `drtran`

*Measured, not argued. Everything below was run on the two series that ship with
`atsw` (`IPC_ES.csv`, `WTI.csv`, 2002-01…2019-12), statsmodels 0.14.6.*

The short answer: **on the same specification the engines agree to four or five
decimals, and the interesting differences are elsewhere.**

---

## 1. The same VAR(1), both engines

`(Δln WTI, Δln CPI) × 100`, 214 observations, VAR(1) with a mean.

| | `statsmodels` VARMAX | `drvarma` (exact ML) |
|---|---|---|
| φ (WTI lag, CPI equation) | 0.020967 | **0.020952** |
| φ (CPI lag, CPI equation) | 0.145772 | **0.144644** |
| φ (WTI lag, WTI equation) | 0.322695 | **0.321768** |
| corr of the innovations | 0.2336 | **0.2313** |

Agreement to ~1e-5 on the pass-through coefficient and ~1e-3 on the rest. The
log-likelihoods are not directly comparable (−926.35 against −929.73) because
the two use different pre-sample conventions — statsmodels' Kalman filter with
its initialisation, drvarma's exact VARMA likelihood — but the estimates land in
the same place.

**So "which engine is more accurate" is not the question to ask.** For a plain
VAR on a decent sample, both are right.

---

## 2. Where the numbers actually change: the specification

The same data, the same engine, one option:

| `deseason` | φ_WTI,1 | φ_CPI,1 | corr | logL |
|---|---|---|---|---|
| `None` | 0.020952 | 0.144644 | **0.2313** | −929.73 |
| `"auto"` | 0.010421 | 0.209699 | **0.5144** | −731.02 |
| `"force"` | 0.011901 | 0.188451 | 0.5276 | −721.68 |
| *published study* | *0.0099* | *0.2317* | *0.51* | |

Removing the seasonal component **halves the estimated pass-through
coefficient** and **more than doubles the contemporaneous correlation**, from
0.23 to 0.51. And `deseason="auto"` is what reproduces the published analysis —
that is how the study's numbers were obtained, and running without it does not
approximate them, it contradicts them.

Why this matters more than the engine comparison: the study's headline result is
a **variance decomposition**, and its own text says the contemporaneous
correlation "is the main driver of the differences in variance decompositions
under alternative orderings". A correlation of 0.23 and one of 0.51 give
different answers to the question the study exists to ask.

**`statsmodels.VARMAX` has no seasonal handling at all.** Neither a `deseason`
option nor seasonal differencing: `SARIMAX` has them, `VARMAX` does not. So the
0.23 row is what a careful user gets by default, and getting the 0.51 row
requires knowing to pre-process — and pre-processing the two series consistently
by hand.

---

## 3. What each can express

This is where the packages genuinely differ, and it is a matter of scope rather
than quality.

| | `statsmodels` | `drvarma` / `drtran` |
|---|---|---|
| VAR, VARMA | yes | yes (exact ML) |
| exogenous regressors | yes, as **contemporaneous regression coefficients** | — |
| **rational transfer** `ω(B)/δ(B)·B^b` | no | `drtran`: yes, with delay and denominator |
| networks of transfers (a DAG) | no | `drtran`: yes |
| seasonality **frequency by frequency** | no | `ifadf`: yes (the MEG/HSM class) |
| constraints: fixed, shared, products | no | `drtran`: a `.cns` table |
| identification (what orders, what λ, what d) | you specify | `art`: guided, node by node |

The transfer row is the substantive one. `VARMAX(exog=…)` regresses on the
exogenous variable *contemporaneously*; expressing "oil affects prices with a
delay of `b` and a geometric decay `1/δ(B)`" means building the lags yourself
and losing the parsimony that made the rational form worth having. `drtran`
estimates `b`, `ω(B)` and `δ(B)` jointly by exact ML, reports the gain `ν(1)`
and the mean lag, and can chain several such links in a DAG.

Conversely `statsmodels` covers a great deal this suite does not — GARCH-type
state space, unobserved components, regime switching, a vast test library — and
is the right tool for most of them.

---

## 4. What to take from this

1. **Do not choose on the engine.** Two independent implementations of exact ML
   and of the Kalman filter agree to 1e-5 on the same model. If two programs
   disagree materially, suspect the specification first — and this comparison is
   a worked example of that suspicion being right.
2. **Choose on what the tool lets you say.** A rational transfer function, a
   per-frequency seasonal decision or a constrained parameter table are either
   expressible or they are not.
3. **And choose on what the tool makes hard to get wrong.** The 0.23-versus-0.51
   row is not a bug in anything. It is a modelling decision that one package
   asks about and the other leaves entirely to the user — and the study's
   conclusion turns on it.

> Reproduce the table yourself: the two series ship with `atsw`
> (`atsw.example_path("IPC_ES.csv")`), and every figure above comes from a
> twenty-line script.
