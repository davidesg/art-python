# A worked example with `sima`: the same pair, simultaneously

*Bivariate VAR of `(Δln WTI, Δln CPI)` for the United States, Spain, France and
Germany. Monthly, 2002:03–2019:12, 214 observations, exact maximum likelihood.
Figures from the pass-through study (`Nivel de Precios y Energia/Energy_Prices`),
whose IRFs and variance decompositions were produced with this engine.*

Read it against `WORKED_EXAMPLE_MTRAM.md`, which models **the same two series**.
That document fits a transfer: oil drives the CPI, one direction, decided a
priori. This one fits both equations at once and lets the data speak about
both — and pays for that with an identifying assumption the data cannot settle.
**Which of the two is right depends on what you are willing to assume, and that
is the decision this example exists to make visible.**

---

## Node 1 · Why a VARMA and not a transfer

A transfer model asserts exogeneity: WTI moves the CPI and nothing in the CPI
moves WTI. For oil against a national price index that is defensible — Spain
does not set the world oil price — and when it holds, the transfer is the
sharper instrument, because it spends no parameters on an equation you already
believe is trivial.

The VARMA gives that up deliberately. It estimates both equations, so it can be
asked questions the transfer cannot answer: **how much of the variance of
inflation is attributable to oil**, and what the response looks like when the
two innovations are contemporaneously correlated — which, here, they very much
are.

---

## Node 2 · The order, per country, and one accepted failure

| country | order | why |
|---|---|---|
| Spain, France | VAR(1) | adequate |
| United States | VAR(2) | required |
| **Germany** | VAR(1) | **shows residual autocorrelation, kept for comparability** |

The German row is the interesting one and it is recorded honestly in the study:
a diagnostic that fails, a model retained anyway, and the reason stated. That is
a legitimate decision — comparability across four countries has value — but it
is a decision, not a result, and reporting it as such is the difference between
a defensible study and a tidy one.

> An analyst should take from this that "the diagnosis failed" does not always
> mean "change the model". It means the cost has to be named.

---

> **Reproducing these numbers.** The study **deseasonalises** before fitting
> (`Model(..., deseason="auto")`). It matters more than it sounds: on the Spanish
> pair, leaving the seasonality in moves the contemporaneous correlation from
> **0.51 to 0.23** and halves the pass-through coefficient — and the variance
> decomposition below is driven by that correlation. Measured in
> `COMPARISON_STATSMODELS.md`.

## Node 3 · The estimates

The CPI equation, per country:

| country | order | μ_CPI | φ_WTI,1 | φ_CPI,1 | φ_WTI,2 | φ_CPI,2 | corr |
|---|---|---|---|---|---|---|---|
| US | 2 | 0.1751*** | 0.0133*** | 0.2695*** | 0.0002 | −0.1402* | **0.54** |
| Spain | 1 | 0.1549*** | 0.0099*** | 0.2317*** | — | — | **0.51** |
| France | 1 | 0.1132*** | 0.0096*** | −0.1277* | — | — | 0.36 |
| Germany | 1 | 0.1149*** | 0.0033 | 0.0341 | — | — | 0.39 |

Two readings worth making explicit:

* **The pass-through lag is significant everywhere but Germany**, where it is
  only marginal — consistent with the German row of the previous table, and with
  the FEVD below.
* **Inflation persistence is not a constant of nature**: 0.23–0.27 in the US and
  Spain, *negative* in France, essentially zero in Germany. A univariate analyst
  who assumed φ ≈ 0.4 everywhere because Spain had it would be wrong in three
  countries out of four.

---

## Node 4 · The identifying assumption — the node the transfer does not have

The structural shocks come from a Cholesky factorisation `Σ_u = P P'`, and
Cholesky requires an **ordering**. The study places **WTI first**: an oil shock
may move domestic inflation within the month, an inflation shock may not move
the world oil price contemporaneously.

That is an economic argument, and a good one. But it is an *assumption*, and the
study says plainly what depends on it:

> the contemporaneous correlation "is the main driver of the differences in
> variance decompositions under alternative orderings"

With correlations of **0.51 (Spain)** and **0.54 (US)**, more than a quarter of
the contemporaneous variance is shared, and how it is attributed is decided by
the ordering rather than by the data. **The right practice is to report the
alternative ordering as a robustness check, not to pick one silently.**

> This is the single most important thing to understand about a VARMA that a
> transfer model never asks you: the impulse responses and the variance
> decomposition are conditional on an assumption the likelihood cannot test.

---

## Node 5 · What the model is for — the variance decomposition

Share of CPI forecast error variance attributable to the oil shock:

| country | h = 1 | h = 2 | h = 20 |
|---|---|---|---|
| United States | 29.0 % | 45.9 % | **47.2 %** |
| Spain | 26.4 % | 38.0 % | **40.4 %** |
| France | 12.7 % | 24.8 % | 25.3 % |
| Germany | 15.1 % | 16.5 % | 16.6 % |

The heterogeneity is the result. Oil explains nearly half of US and 40 % of
Spanish inflation variance in the long run, and a sixth of Germany's. The
study's reading — heavier energy weight in the basket and lighter fuel taxation
in the US and Spain; energy taxes, nuclear and renewable shares, and
administered prices damping it in France and Germany — is economics brought to
the numbers, not read off them.

Impulse responses: a one-standard-deviation WTI shock is about 8.2–8.3
percentage points, the contemporaneous CPI impact ranges from 0.06 pp (France)
to 0.13 pp (US), and the responses die out within 4–6 months.

---

## Node 6 · Comparing the two models of the same pair — carefully

It is tempting to check `sima`'s numbers against `mtram`'s on Spain. Doing it
carelessly is a trap worth walking through.

`mtram` reports a gain of **ν(1) = 0.027149** for `IPC_ES ← WTI`. `sima`'s
Spanish VAR(1) implies a long-run cumulative response of
`φ_WTI,1 / (1 − φ_CPI,1) = 0.0099 / 0.7683 ≈ 0.0129`. Those differ by a factor
of about two, and **that is not evidence that one of them is wrong**, because
the two are not models of the same thing:

* the VAR is fitted on `Δln × 100` with **no seasonal treatment**, while the
  transfer model's output carries **eleven deterministic harmonics**;
* the samples differ (214 from 2002:03 against 216 from 2002:01);
* and the quantities are defined differently — one is a long-run multiplier of a
  transfer function, the other a cumulative response implied by an AR
  polynomial.

**The honest comparison between a transfer model and a VARMA of the same data is
out of sample**, by the rule in `drtran/docs/FORECAST_DIAGNOSIS.md`, not by
lining up coefficients that happen to have similar names. Reconciling those two
numbers properly is open work, and it is the sort of thing worth doing before
either figure is quoted as *the* pass-through.

---

## What this example is meant to leave behind

The transfer model and the VARMA are not competitors where one wins. They answer
different questions and demand different assumptions:

| | `mtram` (transfer) | `sima` (VARMA) |
|---|---|---|
| assumes | exogeneity of the input | an ordering for the contemporaneous effects |
| gives you | the gain, the mean lag, the dynamic shape | variance decomposition, IRFs, both equations |
| the assumption is | defended a priori and testable in principle | untestable by the likelihood, hence reported as a robustness check |

Choosing between them is a decision about what you are prepared to assume — and
that decision belongs to the analyst, which is exactly why an assistant that
argues both sides is worth having at this node.
