---
id: BUG-0006
title: Seasonal-AR seed is contaminated by the deterministic harmonics (wrong sign); combined with fue's platform-fragile optimizer it sends the US-CPI AR(2)×AR(2) fit to a spurious optimum (Windows)
status: fixed
severity: medium
component: pipeline
found_in: 0.1.2
fixed_in: 0.1.3
reported: 2026-07-22
reporter: mtgp2 (DVR / GP-Note replication)
tags:
  - initial-values
  - convergence
  - multimodal-likelihood
  - seasonal-ar
  - degenerate-fit
  - platform-dependent
  - regression
references:
  - bugs/BUG-0006-repro/ (self-contained repro: US_CPI.pre + repro.py)
  - src/art/pipeline.py (_make_model / _arma_starts: ARMA seed on the differenced series)
  - tests/test_bug_0006_seasonal_seed.py (regression test for the seed sign)
  - fue optimizer (spurious basin on Windows; correct on Linux — a fue robustness issue, see below)
  - cases/DVR_validation/validate_all.py (consumer workaround: per-country ar0/ars0 seeds)
  - Garcia-Hiernaux, Gonzalez-Perez & Guerrero (2026), Econ. Modelling 157, Table 2 (US CPI)
---

## Summary

Fitting the US CPI model of the paper's Table 2 — `log`, `d=1`, `(2,1,0)×(2,0,0)_12`
with 5 Fourier harmonics + alternator and a mean — through
`art.pipeline._make_model(...).fit()` returns a **spurious local optimum on Windows**
(the reporter's platform): the mean collapses to `μ = −0.144`, `σ_a` jumps `0.261 →
0.305`, the log-likelihood is ~52 lower, **yet the fit reports `converged=True`,
`ifault=0` with no diagnostic**. Two independent defects combine:

1. **(ART, the proximate cause — FIXED)** `_make_model` seeded the seasonal AR with
   the **wrong sign**. It computed the Yule-Walker seed on the differenced series
   *before removing the deterministic harmonics*; a series with deterministic
   seasonality has **positive** seasonal autocorrelation (the pattern repeats every
   `s`), so the seasonal-AR seed came out **+0.25**, while the residual NOISE's
   seasonal AR — which is what the model actually estimates — is **negative**
   (`Φ ≈ (−0.11, −0.09)`, complex conjugate roots).
2. **(fue, the amplifier — open)** given that wrong-sign seed, fue's C optimizer is
   **platform-fragile** on this multimodal AR(2)×AR(2) surface: it escapes the wrong
   basin on Linux but **not on Windows**, and reports success on the absurd optimum
   with no guard.

## Impact

Silent, wrong "estimated" US model on Windows: it is the paper's Table 2 US row, and
it breaks the replication and everything downstream of the US residuals (the DVR, the
GARCH/GJR robustness, the Beveridge–Nelson decomposition). Because `converged=True` /
`ifault=0`, it passes with no warning. The other seven economies (Eurozone, Spain,
France, Germany, Japan, UK, Canada) are unaffected — their seasonal AR is absent or
positive, or the surface is unimodal.

## Reproduction

Self-contained repro in [`BUG-0006-repro/`](BUG-0006-repro/): the US CPI series
(monthly, 2002:01–2026:05, n=293) is embedded in `US_CPI.pre`; run `python repro.py`.

**Platform-dependent** (this is itself the fue finding):

| build                                   | default (old +seed) | verdict          |
|-----------------------------------------|---------------------|------------------|
| **Windows** — fue 0.1.7 wheel (MSVC/vcpkg) | μ=−0.144, σ=0.305, AIC=−2511 | **SPURIOUS** (converged=True) |
| **Linux** — fue 0.1.7 wheel (manylinux)    | μ=+0.0021, σ=0.261, AIC=−2613 | correct (Table 2) |
| **Linux** — fue 0.1.7 editable (source)    | μ=+0.0021, σ=0.261, AIC=−2613 | correct (Table 2) |

Same C **source**, same seed, same data → the outcome depends on the **build/platform**.
Verified in an isolated venv with the exact PyPI stack (`fue==0.1.7`,
`art-tseries==0.1.2`) on Linux: correct. The reporter's Windows wheel: spurious.

## Root cause

**(1) ART — the seed sign.** `_make_model` → `_arma_starts(resid, …)` seeds the
seasonal AR by Yule-Walker on `resid = ∇^d∇_s^D BoxCox(y)`. For a `D=0` model
(deterministic harmonics), that series still contains the seasonal pattern. Measured
on US CPI:

| series seeded on | r(12) | YW seasonal-AR seed |
|---|---|---|
| `∇log(CPI)` **with** harmonics (old) | **+0.317** | **[+0.253, +0.203]**  ← wrong sign |
| noise **after** removing harmonics   | −0.037 | [−0.04, −0.08]  ← correct sign (≈ Table 2) |

A wrong-sign seasonal-AR seed starts the multimodal fit in the wrong basin.

**(2) fue — the optimizer.** From that seed, fue's C optimizer (`qnewtopt`/BFGS)
lands in a different basin **depending on the build**: the Windows wheel (MSVC `/O2`
+ vcpkg GSL + MSVC CRT `libm`) and the Linux wheel (GCC `-O2` + system GSL + glibc
`libm`) evaluate the log-likelihood with last-ULP differences (FP reordering / FMA
contraction / transcendental functions), and on this multimodal surface those decide
the basin. fue then reports `converged=True` on an absurd optimum (`μ̂` orders of
magnitude off the sample drift) with **no diagnostic** — dangerous regardless of
platform. (No `long double` is involved; it is compiler/libm FP semantics.)

## Fix

**ART (applied, 0.1.3).** In `_make_model`, for `D=0` seasonal models, regress the
same deterministic terms the model will carry — constant + cos/sin pairs
`k=1..n_harm` + Nyquist alternator — out of the differenced series **before** the
Yule-Walker/Hannan-Rissanen seeds, and seed on the residual noise. The seed then
carries the sign of the noise. Verified: the US seasonal-AR seed is now `[−0.04,
−0.08]` (was `[+0.25, +0.20]`) and the regular-AR seed `[0.59, −0.18]` (≈ Table 2);
guarded, with a fallback if the regression is degenerate. Regression test:
`tests/test_bug_0006_seasonal_seed.py`.

**fue (recommended, open — a separate fue bug).** A correct seed makes this case
robust, but the underlying fue fragility remains: a strongly-multimodal spec could
still diverge on some build. fue should (a) **guard against absurd optima** — reject
/ warn instead of `converged=True` when `μ̂` is many sample-std from the differenced
mean, or the fit is materially worse than the seed; and (b) offer a **multi-start**
for seasonal-AR blocks so the best basin wins on any platform.

**Consumer workaround (`validate_all.py`, still valid):** per-country starting values
for the multimodal spec (`"USA": ar0=[0.60,-0.17], ars0=[-0.11,-0.09]`).

## Validation

With the fix, `_make_model` seeds the US seasonal AR negative and the regular AR at
the Table-2 values; on Linux the fit is unchanged (already correct, `σ_a=0.261`,
`μ̂=0.0021`, `AIC=−2613`), and the correct-sign seed is expected to fix the Windows
basin too (to be confirmed on a Windows wheel). New tests
`tests/test_bug_0006_seasonal_seed.py` guard the seed sign (seasonal-AR seed negative
when the noise is, despite positive deterministic seasonality). Full ART suite green
before and after. The residual fue robustness (guard + multi-start) is tracked as a
fue-side follow-up.
