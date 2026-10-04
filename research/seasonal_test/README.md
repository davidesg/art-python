# BUG-0206 — size and power of the tests of deterministic seasonality

Which test should art and drvarma share to decide whether a monthly series has
a deterministic seasonal pattern? The test runs on the regular differences w
of the (log) series, with art's design: an intercept plus the 11 differenced
harmonics.

## Design

- **Candidates** (`candidates.py`):
  - `hac_art`: art's HAC F as it is. It reproduces `detect_seasonality`
    to 1e-10.
  - `hac_hc1`: the same with the n/(n−k) factor.
  - `ewc`: equal-weighted cosine HAC with fixed-b F critical values
    (Lazarus, Lewis, Stock and Watson 2018).
  - `fgls`: prewhitening / feasible GLS. An AR(p) on the OLS residuals, p
    by AIC up to 6; w and X filtered with it; OLS F on the result.
  - `ols`: the plain OLS F (drvarma's and the C's).
  - `lr`: the LR of the harmonics inside the ARMA model, fitted with fue
    (art's engine) using the TRUE orders. It is an oracle: the best a
    model-based test can do.
- **Dynamics of w** (`study.py`):
  - white noise;
  - AR(1), φ = +0.6, −0.6, +0.9;
  - AR(2) with real roots, and with complex roots whose spectral peak is
    AT a seasonal frequency (period 6) or BETWEEN two (period 9);
  - two AR(3);
  - MA(1), θ = +0.5, −0.5, +0.9;
  - two ARMA(1,1) and two ARMA(2,1).

  Under H0 there is also a seasonal AR, which is stochastic seasonality.
- **Sample sizes:** n = 120, 216, 400.
- **Size:** 2000 replications (400 for the LR).
- **Power:**
  - the pattern is put in the level, so w carries its difference;
  - amplitude 0.1–0.4 × sd(w);
  - two shapes: the annual cycle alone, or spread over all the harmonics;
  - 500 replications (200 for the LR);
  - common random numbers across amplitudes.
- **Size-adjusted power:** each test's own 95% quantile under H0 in that
  cell, so an oversized test does not look powerful for that reason.

Tables: `results_n120.md`, `results_n216.md`, `results_n400.md`
(`python report.py --n N`). The raw draws (`results/*.npz`, 23 MB) are not
kept in git; `python study.py` rebuilds them in about 22 minutes on 4 cores.

## Results

**Size.** Rejection rate at 5% over the 16 ARMA dynamics and 3 sizes, 48
cells per test:

| test | worst | median | cells > 0.075 | mean raw power | mean size-adj. power |
|---|---|---|---|---|---|
| hac_art | 0.290 | 0.086 | 25/48 | 0.660 | 0.611 |
| hac_hc1 | 0.246 | 0.068 | 21/48 | 0.632 | 0.611 |
| ewc | **0.065** | 0.048 | **0/48** | 0.464 | 0.469 |
| fgls | 0.102 | 0.062 | 7/48 | **0.694** | **0.674** |
| ols | 0.202 | 0.052 | 21/48 | 0.546 | 0.552 |
| lr (oracle) | 0.102 | 0.064 | 13/48 | 0.703 | 0.680 |

- **`hac_art`** is not only oversized. Its size swings from 0% to 29% with
  the dynamics:
  - 28% on white noise at n=120, 18% at n=216;
  - 29% on an ARMA(2,1) with a spectral peak at a seasonal frequency;
  - 0.1% on an AR(1) with φ=+0.9.

  The HC1 factor barely moves it. The problem is the Bartlett estimator with
  11 restrictions, not the missing factor.
- **`ols`**, the drvarma/C test, is right only under white noise. With
  dynamics it ranges from 0% to 20%: 18–19% when the AR has its peak at a
  seasonal frequency, 13% with φ=−0.6.
- **`ewc`** keeps its size in every cell (3–6.5%), but it pays in power.
- **`fgls`** stays at 4.4–8% except on the nearly non-invertible MA(1)
  (θ=0.9): 10% at n=120, 9% at n=216. A larger AR order (12, 13) makes
  that worse, not better: the long AR soaks up part of the seasonal
  pattern.
- **`lr`** (oracle) is at 4–9.5%. The χ²(11) approximation is a little
  generous at n=120.

**Power** (size-adjusted, mean over the 16 dynamics and both shapes):

| n | amplitude | hac_art | ewc | fgls | ols | lr (oracle) |
|---|---|---|---|---|---|---|
| 120 | 0.2 | 0.31 | 0.22 | **0.46** | 0.22 | 0.47 |
| 216 | 0.1 | 0.20 | 0.13 | **0.31** | 0.11 | 0.32 |
| 216 | 0.2 | 0.56 | 0.34 | **0.63** | 0.40 | 0.65 |
| 400 | 0.2 | 0.77 | 0.65 | **0.81** | 0.69 | 0.81 |

`fgls` tracks the oracle LR in every dynamic (the per-dynamic tables are in
`results_n*.md`). It does so without knowing the orders, at the cost of an
AR fit. `ewc` loses about a third of the power at n ≤ 216.

**Stochastic seasonality** (seasonal AR, Φ=0.5) is not the H0 a
deterministic test is built for. Every test rejects it 43–95% of the time.
Telling a stochastic pattern from a deterministic one is the job of the
seasonal-difference decision (D), not of this test.

## Conclusion (for the analyst's decision)

1. **`fgls`** (prewhitening with an AR by AIC, p ≤ 6, then the F) is the
   best compromise. Its power equals the oracle LR's and its size is near
   5% except on a nearly non-invertible MA. It is the shared mechanism the
   study points to for art and drvarma.
2. **`ewc`** is the alternative if size must be held at any cost. It costs
   about a third of the power in samples of 10–18 years.
3. **`hac_art` and `ols` should both go.** The first is oversized and its
   size depends on the dynamics. The second, drvarma's, is right only
   under white noise.
