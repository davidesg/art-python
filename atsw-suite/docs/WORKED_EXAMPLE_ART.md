# A worked example with `art`: the same series, two objectives

*Spanish national CPI (INE `IPC290751`), monthly, 2002-01…2019-12, 216
observations. Every number below is from the real guided analysis recorded in
`SF_MEG/empirical/cases/ES_CPI/RESULTS.md`; nothing here is illustrative.*

The point of reading both halves is the contrast. **The nodes of the guided
pipeline are the same in both; the criterion at some of them is not**, because
what the model is FOR changes what counts as a good decision. That is the part
of Box-Jenkins-Treadway that is hardest to learn from a manual and easiest to
show on one series.

---

## Part I — the objective is FORECASTING

### Node 1 · The transformation (λ)

**Evidence**: `describe_boxcox` gives the range-mean plot and the gap between
the log and level fits.

**Decision: λ = 0 (logs).** And it is taken on a *theoretical* criterion, not on
the test: this is a number index with an arbitrary base, so its level carries no
information and only relative changes do. Had the test disagreed, the criterion
would still have won.

> Worth stating plainly for a newcomer: the first node is one where the evidence
> supports a decision the theory had already made. Not every node is a contest.

### Node 2 · The order of integration (d)

**Evidence**: ADF and KPSS both lean toward **d = 2**. Shin-Fuller on the AR
side gives `Φ̂₁ᵤ = 37.5`, far above its critical value, with `ρ̂ = 0.40` — nowhere
near a unit root.

**Decision: d = 1**, against two of the three tests.

The reasoning is the one an analyst has to internalise: ADF and KPSS are testing
whether *another* difference is admissible; Shin-Fuller is testing whether the
remaining root is one. A series that is I(1) with strong inertia looks
"insufficiently stationary" to ADF while being plainly not I(2) to a test that
looks at ρ. Over-differencing is not a conservative error — it manufactures a
unit MA root and, as Part I's third model shows, it costs 43 % of forecast
accuracy at two years.

### Node 3 · The seasonality, frequency by frequency

**Evidence**: eleven deterministic components fit — five cos/sin pairs for
f = 1…5, plus the `(−1)ᵗ` alternator for the Nyquist f = 6. `f = 2` dominates
(the Spanish January-February sales pattern). The MEG sweep then asks, per
frequency, deterministic or stochastic.

**Result**: every frequency deterministic except **f = 3**, which comes out
stochastic — but **marginal**: LR = 2.30 against a critical value of 2.07.

**Decision: the frontier is acknowledged, not resolved.** The guided pipeline
does not pretend 2.30 > 2.07 settles it, and this is where an analyst benefits
from an assistant that argues rather than reports: the honest reading is that
the two representations are nearly indistinguishable *by this test*, so the
decision has to be made on other grounds — and Part I ends by making it on
parsimony.

### Node 4 · The confirmatory pair, and a test that says nothing

The MEG works on the MA side. The confirmatory pair runs Shin-Fuller on the AR
side, and it comes out **inconclusive**: the free AR_f collapses to ρ̂ ≈ 0.07
when even a weak deterministic sinusoid would give ρ̂ ≈ 0.43.

**This is expected and it is not a failure.** The AR side lives on the ρ axis;
what separates deterministic from stochastic seasonality is σ_S², a different
axis. A test that cannot see the axis the question lives on will be silent
whatever the answer.

> The teaching point: an inconclusive test is information about the test, not
> about the series. Reading it as evidence for the null is a mistake, and it is
> exactly the kind of thing a guided assistant should say out loud.

### Node 5 · The competing representation, and a tie broken on economics

Built through the guided B2 branch on ∇∇₁₂, the Box-Jenkins airline competitor
needs a regular term. The textbook answer is MA(1). **The decision was AR(1)**,
on the grounds that inflation has inertia and the deterministic model had
already estimated φ ≈ 0.40 for exactly that.

```
(1 − 0.3631·B)(∇∇₁₂ ln y + 0.0145) = (1 − 0.8575·B¹²) aₜ
    (0.0658)          (0.00673)          (0.0586)
σ̂ₐ = 0.2633 %   ℓ = −25.17   AIC = 56.34
```

All three coefficients significant, residuals white, normality fine.

### Node 6 · The verdict, out of sample

Estimate once on 2002-2019, freeze the parameters, roll the origin one month at
a time from 12/2019 and forecast 24 ahead — 54 balanced origins per horizon.

| h | RMSE_D | HSM/D | **SARIMA/D** | de-biased |
|---|--------|-------|--------------|-----------|
| 1 | 0.602 | 1.002 | 1.002 | 0.983 |
| 6 | 1.725 | 0.999 | 1.189 | 1.066 |
| 12 | 2.931 | 0.998 | 1.272 | 1.110 |
| 24 | 4.889 | 0.997 | **1.435** | **1.314** |

Two conclusions, and the second is the one that teaches:

1. **D and the frequency-selective S forecast identically** — the ratio is 1.00
   at every horizon. The f = 3 witness sits at ≈ −1, so the stochastic seasonal
   almost cancels and the two share a forecast function. **D is retained by
   parsimony, NOT because it forecasts better.** Saying that correctly matters:
   an earlier draft of the note claimed D won, and that was an artifact of
   forecasting with the non-invertible representation.

2. **The blunt ∇₁₂ degrades monotonically, to +43 % at two years** — and
   **the Diebold-Mariano test is not significant at any horizon** (p 0.16–0.78).
   Fifty-four overlapping 24-step origins are not enough power. So the case
   against the airline **rests on the structural argument, not on the number**:
   ∇₁₂ over-differences frequencies that are deterministic, and the persistently
   significant mean it needs is a symptom of that, not a virtue.

> This is the honest shape of an empirical conclusion, and it is worth an
> analyst seeing it once: a difference that is economically large and
> statistically undemonstrated, reported as exactly that.

---

## Part II — the objective is a TRANSFER MODEL

Now the same series is not the end product. It is going to be the **output of a
transfer model** whose input is the oil price (WTI), estimated in `mtram`. Same
data, same evidence at every node — and two of the decisions change.

### What does NOT change

Nodes 1 and 2. λ = 0 and d = 1 are properties of the series and of what it
measures; no downstream use alters them.

### Node 3 changes: prefer DETERMINISTIC seasonality, and know why

In Part I the frontier at f = 3 was resolved by parsimony and it could have gone
either way. Here it cannot.

The identification of a transfer model **prewhitens**: it filters the output
through the INPUT's ARMA and reads the cross-correlation. WTI carries nothing
seasonal. So if the output keeps a *stochastic* seasonal component, the filter
does not remove it, the filtered series is still non-stationary at that
frequency, and the CCF does not come out empty — **it comes out with structure
everywhere, and the heuristic reads a delay and an order off it anyway**.

That is a silent failure: a plausible-looking `(b, r, s)` obtained from a
contaminated correlogram. Deterministic seasonality has no such effect, because
subtracting fixed harmonics leaves nothing behind to survive the filter.

> This is not a workaround. The Box-Jenkins-Treadway tradition specifies
> seasonality as provisionally deterministic anyway and only afterwards resolves
> it frequency by frequency. An analyst heading for `mtram` should choose it at
> the start: re-doing it later costs far more.

### Node 3b, new: the operators must AGREE with the input's

This node does not exist in Part I, and it is the one that would have silently
corrupted the answer until 2026-08.

The transfer relates the **levels**, with the differencing carried by the noise.
So the input has to enter differenced by the OUTPUT's operator. When the two
operators agree, that is the input's own column and nothing has to happen. When
they differ, what gets fitted is not ν(B) but **ν(B)·Δ(B)**, with
Δ = op_output / op_input, and the reported gain is wrong by **Δ(1)**.

For this pair:

| model of ES_CPI | operator | vs WTI's `∇` | consequence |
|---|---|---|---|
| the Part I model (`d=1, D=0`, harmonics) | `∇` | **Δ(1) = 1** | nothing to do |
| the airline variant (`d=1, D=1`) | `∇∇₁₂` | **Δ(1) = 0** | gain **annihilated** |

Measured, on this very series: eight variants of ES_CPI give a gain of
**0.0264–0.0274** once the dispatch is in place. Before it, the five airline
variants said the pass-through was **≈ 0.006** while the three harmonic ones
said **≈ 0.027** — a factor of five that an analyst would have attributed to
economics and that was arithmetic.

`mtram`'s `check_operators` answers this before anything is estimated, and it
costs one call.

### Node 6 changes: the verdict is no longer about this model

In Part I the univariate model was judged on its own forecasts. Here it is
judged on whether the transfer model built on top of it earns its place:

- the **diagonal gate** — with a diagonal structure the exact likelihood
  factorises, so the joint fit must reproduce the sum of the univariate ones. It
  is a complete check that the crossing preserved everything, and it is cheap
  enough to run first;
- the **likelihood-ratio test** of the transfer against that diagonal rung;
- and the rule from `FORECAST_DIAGNOSIS.md`: a transfer model is kept over its
  univariate **iff** it forecasts better out of sample.

The univariate model is, in Treadway's phrase, the **measuring stick**. If the
transfer model cannot beat it, the transfer model is what needs rethinking.

---

## What the two halves are meant to leave behind

Same series, same evidence, same nodes — and at nodes 3 and 6 the right decision
depends on what the model is for. A guided assistant is worth having precisely
there: not to compute the tests, which any program does, but to say *which
question this node is answering right now* and *why this criterion and not the
other one*. Every decision above is defensible, and none of them is automatic.
