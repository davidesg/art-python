# A worked example with `mtram`: oil into the Spanish CPI

*The pass-through case. Output `IPC_ES`, input WTI, monthly 2002-01…2019-12,
216 observations. Every figure is from the suite's own regression test
(`drtran-python/tests/test_end_to_end_passthrough.py`) and from the runs made
while fixing BUG-8; the oracle column is the independent TASTE implementation.*

The nodes are the ones `drtran/docs/DECISION_NODES.md` defines. What this
document adds is what each one looked like on a real pair, including the two
places where the honest answer was "the program cannot tell you that".

---

## Before any node · the gate

Two `.pre` files arrive from `art` — one per series, each the optimum of its own
univariate specification. `load_pre` checks the crossing before anything else,
and the check is complete rather than indicative:

> With a diagonal structure the exact likelihood **factorises**. So the joint
> diagonal fit must reproduce the SUM of the two univariate log-likelihoods. If
> the transformation, the differencing, the deterministics or the seeds did not
> arrive intact, the identity fails.

Measured here: **−1.50e−07**. And it earns its place — it caught a real error
this year that nothing else could:

| | joint diagonal | sum of univariate | gap |
|---|---|---|---|
| WTI over 2005-2019 (180 obs) | −629.168775 | −629.168775 | **0.000000** |
| WTI over 2005-2019 vs a 2002-2019 output | −681.034215 | −689.960006 | **8.93** |

Both series ended 12/2019, so the alignment check passed — correctly, the dates
really did line up. But one carried 36 months more history, the cast trims to
the common window, and the longer series' `.pre` was therefore the optimum of a
sample that was not being fitted. **`check_operators` now reports the common
window and who has spare history, so this is caught before rather than after.**

> The lesson for an analyst: a gate that only ever says "fine" is decoration.
> This one says "fine" on every legitimate case and fired on the first illegitimate
> one it met.

---

## N0 · Which series is the output

Not a computation. The transfer model is directional: WTI drives the CPI and not
the reverse, and that is economics, not a correlogram. `load_pre` takes the
first path as the output and asks for confirmation, because getting it backwards
produces a perfectly estimable model of nothing.

---

## N1 · The link order `(b, r, s)`

**Evidence**: `identify_link` prewhitens — filters the output through the
INPUT's ARMA — and reads the cross-correlation, with the band that corresponds
to the real overlap.

**Decision here: `b = 0, r = 0, s = 1`.** A contemporaneous response with one
extra lag; no rational denominator. Oil reaches a consumer price index within
the month it moves, through fuel, and the second weight picks up the rest.

Two things worth an analyst's attention at this node:

* **The band is `2/√n` of the OVERLAP, not of either series.** When that band
  and the real overlap disagree, something upstream is wrong — that mismatch was
  the only visible symptom of the misalignment bug that produced a `b = 18`
  proposal in earnest.
* **If the output carries stochastic seasonality and the input does not, this
  node fails silently.** The prewhitening filter carries nothing seasonal, so
  the seasonal component survives it and the CCF comes out structured
  everywhere; the heuristic reads an order off it anyway. That is why the
  univariate work for a transfer model should choose deterministic seasonality
  from the start (`WORKED_EXAMPLE_ART.md`, Part II).

---

## N1b · Do the two operators agree?

A node that did not exist until August 2026, and the one that would have
corrupted the answer in silence.

The transfer relates the **levels**, with the differencing carried by the noise.
So the input must enter differenced by the OUTPUT's operator. `check_operators`
answers before anything is estimated:

```
IPC_ES <- WTI     Delta(1) = 1    operadores IGUALES, nada que hacer
```

Here both series are `d = 1, D = 0`: Δ = 1 and there is nothing to do. Had the
output been the airline variant (`∇∇₁₂`), Δ would be `1 − B¹²` and **Δ(1) = 0**
— the gain annihilated. Measured on this very series: the five airline variants
reported a pass-through of ≈ 0.006 while the three harmonic ones reported
≈ 0.027, and the factor of five was arithmetic, not economics.

> And do NOT divide the gain by Δ(1) to repair it. The law `ν̂(1) = ν(1)·Δ(1)`
> only holds once the fitted `(b, r, s)` has the reach to see where Δ puts its
> weight; the real error is partial and is not knowable from the output.

---

## N5 · The cast

`estimate` uses the **embedded** cast by default: the transfer becomes
off-diagonal VARMA coefficients, nothing is subtracted, and the exact likelihood
does its own pre-sample initialisation — so the reported likelihood is the
likelihood of the data and LR tests and information criteria mean what they say.

When the operators differ the fit is **dispatched** to the subtracting cast,
because the input then needs a second, re-differenced vector and the embedded
cast has one column per series. `estimate` says so when it happens, and warns
that the two casts' likelihoods are not comparable with each other.

Here Δ = 1, so the embedded cast runs and nothing is announced.

---

## N6 · Estimation, and what the transfer bought

```
ω₀ = 0.016402   ω₁ = −0.010748      φ_N = 0.295216   μ = 0.140321
gain ν(1) = 0.027149
```

Against the diagonal rung — the same model with the transfer restricted to zero,
which is the right null because it is nested:

```
diagonal  ℓ = −1744.135582
joint     ℓ = −1704.423918
LR = 79.42 on 2 df
```

The transfer is not decoration. And the gain has an economic reading: a
permanent 1 % move in WTI passes through to about **0.027 %** of the Spanish
CPI level.

**Corroborated independently.** TASTE shares no code with this family and
estimates by unconditional sum of squares with backforecasting rather than exact
ML, so agreement to the low single digits is the most that can be asked:

| | TASTE | drtran | difference |
|---|---|---|---|
| ω₀ | 0.016410 | 0.016402 | 8.0e−06 |
| ω₁ | −0.010790 | −0.010748 | 4.2e−05 |

---

## N6b · Diagnosis, and one number that has to be right

`diagnose` reports residual whiteness, the cross-correlations between residual
and input, normality and extreme residuals.

One detail worth carrying: the degrees-of-freedom correction for a
**per-series** statistic uses that series' parameters, not the joint vector's.
Using all seventeen where three belong turned a p-value of 0.34 into 0.0017 —
the difference between "clean" and "reject", from an arithmetic slip in a
correction nobody looks at.

---

## N7 · Does it earn its keep?

In-sample the transfer model can never fit worse: it has more free parameters,
so a significant ω and a higher likelihood are **necessary and not sufficient**.
The rule in `drtran/docs/FORECAST_DIAGNOSIS.md` is utilitarian:

> A transfer model is kept over its univariate **iff it forecasts better out of
> sample** — recursive origins, parameters fixed, Diebold-Mariano with the HAC
> variance and the HLN correction.

The univariate model is the measuring stick. If the transfer cannot beat it, the
transfer is what needs rethinking, not the stick.

---

## And what the model leaves behind

`write_inp` writes each series back with the JOINTLY estimated values — as
`.inp`, deliberately **not** as `.pre`. A `.pre` asserts "these values are the
optimum of this specification", and a univariate block that was optimised *with
the transfer in the model* is not a fixed point of the univariate operator.
Measured: re-running `fue` on a genuine `.pre` moves the numbers by **0.000000**;
on drtran's jointly-fitted block, by **13.109261**.

That is the whole convention in one measurement, and it is what lets the ladder
be climbed by trusting the files.
