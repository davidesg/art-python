---
id: BUG-0001
title: Rescaling ×100 + μ seeded at 0 collapses the mean to ~0 and grows a spurious near-unit AR root
status: open
severity: high
component: inp-builder
found_in: 0.1.1
reported: 2026-07-09
reporter: D. E. Guerrero
tags:
  - mean
  - rescaling
  - identification
  - degenerate-fit
references:
  - src/art/pipeline.py:70-71 (.inp writer, "0 100.00" rescaling)
  - src/art/pipeline.py:274-275 (.inp writer, "0 100.00" rescaling)
  - src/art/pipeline.py:439 (mu=0.0, estimate_mu=...)
  - src/art/pipeline.py:534 (mu=0.0, estimate_mu=...)
  - /home/david/Dropbox/Cycles/bugs_art_fue.md (BUG #1)
---

## Summary

When ART builds an `.inp` for an untransformed annual series (λ=1, no harmonics)
and estimates an AR(p)+mean, the model comes back with **μ ≈ 0** instead of the
sample mean, and the AR operator grows a **near-unit real root** that absorbs the
un-subtracted level. The fit is degenerate but passes diagnosis with no warning.
Two constructor decisions combine to cause it: the `.inp` writer hard-codes the
rescaling factor to **100**, and `_make_model` seeds **μ = 0** regardless of the
sample mean.

## Impact

Silent, wrong "estimated" models for any untransformed (or even log) series whose
level is far from zero and which is fit with a mean. Observed on the Geneva
precipitation series:

| Model  | via                        | rescale | μ init | μ fitted   | real AR root       | logℓ     |
|--------|----------------------------|---------|--------|------------|--------------------|----------|
| GE_m20 | confirm_and_estimate AR(2) | 100     | 0      | −0.00006   | 0.995 (near-unit)  | −2234.6  |
| GE_m70 | confirm_and_estimate AR(7) | 100     | 0      |  0.00008   | 0.999 (near-unit)  | −2208.7  |
| GE.2   | hand `.inp` AR(7)          | 1.00    | 126.11 | 126.381    | 0.889 (correct)    | −1057.9  |

The user must currently hand-build `.inp` files (μ seeded at the mean, rescale
1.00) to get the correct fit, so the guided pipeline is not trustworthy for these
series. **Not limited to λ=1 nor to AR order ≥2:** GEP (log, λ=0, AR(1)) also
collapsed (μ≈0.002 vs the true ~6.756, AR(1)=0.9992) purely from the ×100
rescaling. Root cause is the **rescaling ×100**, not the AR order or λ.

## Reproduction

```
create_inp(data=<248 Geneva precip. days>, freq=1, start_year=1768, name="GE_days")
  → writes GEfull.inp with "reescaling factor = 100.00" and "mu = 0.000000 1"
confirm_and_estimate(inp=GEfull.inp, lam=1, d=0, D=0, p=2, q=0,
                     n_harmonics=0, estimate_mu=True)
  → μ ≈ 0, AR factorises to a near-unit real root (0.995)
```

Contrast that fixes it: (a) the same `.inp` with rescale 1.00, or (b) μ seeded at
the sample mean — either alone converges to μ≈126.4 and root 0.889.

## Root cause

1. **Rescaling hard-coded to 100.** `src/art/pipeline.py:70-71` and `:274-275`
   emit `" 0 100.00"` for the "reescaling factor" field of every `.inp`. For an
   untransformed, harmonic-free series the ×100 rescaling adds nothing and
   **deforms the conditioning** of the ML problem along the level ↔ near-unit-root
   direction.
2. **μ always seeded at 0.** `src/art/pipeline.py:439` and `:534` build the model
   with `mu=0.0` without consulting the sample mean.

Together, the exact-ML surface is nearly flat along level ↔ near-unit AR root, and
the optimizer settles in the degenerate optimum (μ≈0, near-integrated AR).

## Fix

Any one of these breaks the collapse; (1)+(2) together are recommended:

1. **Do not rescale by 100 by default** — write `1.00`, or expose the factor and
   default it to neutral for untransformed/harmonic-free series (generalise: make
   rescaling μ-neutral in all cases, not only λ=1).
2. **Seed μ at the process mean** when `estimate_mu=True`: use
   `mean(∇^d ∇_s^D y(λ))` in `_make_model` instead of `0.0` (≈ sample mean for
   d=0; ≈0 for d≥1, harmless).
3. **Diagnostic guard:** if, after `estimate_mu=True`, the fitted μ ≈ 0 on a
   clearly non-zero-mean series and/or Σφ_AR ≈ 1, warn of a possible mean
   collapse / spurious near-unit root.

## Validation

Re-estimate AR(2)+mean and AR(7)+mean on GEfull with the fix and confirm μ≈126.4
(not ≈0), the real AR root ≈0.889 (not ≈0.995/0.999), and agreement with the
hand-built GE.2/GE.3 (logℓ, σ, cycle factors) up to the rescaling constant in
logℓ. Add a regression test asserting the fitted μ is within a tolerance of the
sample mean for a high-level untransformed series.
