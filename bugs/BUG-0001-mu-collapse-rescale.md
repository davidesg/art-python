---
id: BUG-0001
title: Rescaling ×100 + μ seeded at 0 collapses the mean to ~0 and grows a spurious near-unit AR root
status: fixed
severity: high
component: inp-builder
found_in: 0.1.1
fixed_in: 0.1.2
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

**Applied** in 0.1.2 via **fix (2): seed μ at the process mean.**

Confirmed against fue that the optimiser estimates μ on `refactor · BoxCox_λ(data)`
after differencing (`fue_api.c`: `DataMat = refactor · transform(data)`, then
differenced), and that **both** `.inp` writers hard-code `refactor = 100` and
estimation reads the written `.inp` back (`_load_fitted`). So the operative scale
is always ×100 and the μ seed must live in it.

- New helper `_mu_seed(ts, lam, d, D, estimate_mu)` in `src/art/pipeline.py`
  returns `_RESCALE_FACTOR · mean(∇^d ∇_s^D BoxCox_λ(y))` when μ is estimated
  (0 otherwise). For d=0 this is the (rescaled) level mean; for d≥1 it is ≈0.
- `_make_model` and `_build_arma_on_model` now pass `mu=_mu_seed(...)` instead of
  `mu=0.0`.
- The ×100 factor is now the single module constant `_RESCALE_FACTOR`, used both
  by the `.inp` writers and the seed, so the two can never drift.

The rescaling is deliberately **kept** (not set to 1.00): it conditions the
tiny differenced-log values of the monthly CPI series ART is primarily built for,
and seeding μ correctly fixes the collapse without that risk. A post-fit
diagnostic guard (fix 3) remains a possible follow-up.

## Validation

Fresh AR(p)+mean on the very series from the report, with the fix
(`_make_model → _write_inp → _load_fitted`):

| Series        | λ | p | μ (orig. units) | sample mean | AR root(s)        | before (bug)          |
|---------------|---|---|-----------------|-------------|-------------------|-----------------------|
| GE (Geneva)   | 1 | 2 | **126.15**      | 126.13      | 0.578, 0.356      | μ≈0, root 0.995       |
| GEP (log mm)  | 0 | 1 | **6.7555**      | 6.7557      | AR(1)=0.169       | μ≈0.002, AR(1)=0.9992 |

μ lands on the sample mean (was ≈0), the spurious near-unit root is gone, and both
match the user's hand-corrected references (GE.2/GE.3; GEP μ=6.7555, AR=0.1695).

Regression test `tests/test_bug_0001_mu_collapse.py`: `_mu_seed` equals
`refactor·mean` for λ=1 and λ=0 and is 0 for `estimate_mu=False` / ≈0 for d≥1;
an AR(2)+mean fit on a synthetic high-level series returns μ within 5 % of the
sample mean and Σφ < 0.9 (no near-unit root).
