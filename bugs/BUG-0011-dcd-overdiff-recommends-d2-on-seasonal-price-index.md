---
id: BUG-0011
title: dcd_overdiff_regular recommends d+1 on every IPC_ES specification, including the harmonics-only baseline its own docstring prescribes
status: open
severity: medium
component: formal-tests
found_in: 0.1.4
fixed_in:
reported: 2026-08-08
reporter: David / IPC_ES passthrough
tags:
  - dcd
  - over-differencing
  - integration-order
  - observation
references:
  - src/art/formal_tests.py:543-600 (dcd_overdiff_regular)
  - src/art/describe.py:1442-1452 (the "DCD sobre-diferenciación regular" report block)
  - bugs/BUG-0009-… (same routine; different trigger — there Nyquist is reformulated, here ifadf is all zero)
---

## Summary

**Root cause ESTABLISHED 2026-08-08** — see §Root cause below. It is the
deterministic cos/sin harmonics, not the ARMA, and the routine's own
precondition is inverted.

*(Filed originally as an observation without a diagnosis; the measurement below
is unchanged and was reproduced exactly — LR 4.220 and 4.254.)*

On IPC_ES (INE Spanish CPI, 2002-01…2019-12, n=216, λ=0, d=1, D=0, deterministic
seasonality) `dcd_overdiff_regular` returns *"testigo invertible → raíz unitaria
regular genuina → considerar d+1 ✗"* on **every** specification tried, including the
harmonics-only baseline (p=q=0) that the routine's own docstring names as the right
model to run it on. `d=2` on a price index means a quadratic drift in the level, which
is not a defensible reading of this series.

| model | seasonal terms | noise | θ̂ | LR (crit 1.94) | verdict |
|---|---|---|---|---|---|
| `IPC_ES_m00` | 5 pairs + Nyquist | none (p=q=0) | +0.8646 | **18.619** | consider d+1 |
| `IPC_ES_m10` | 5 pairs + Nyquist | AR(1) + μ | +0.9709 | 4.220 | consider d+1 |
| `IPC_ES_m10_podado` | 4 pairs + Nyquist | AR(1) + μ | +0.9708 | 4.254 | consider d+1 |
| `WTI_m10` (control) | none | AR(1) | +0.9981 | 0.000 | d confirmed ✓ |

The LR is *largest* (18.6) on the cleanest baseline, which is the opposite of what the
precondition in the docstring predicts.

`d=1` is well supported for this series independently: ADF/KPSS reach consensus once
seasonality is accounted for, the level is a textbook I(1) index, and Shin-Fuller on
the fitted model gives Φ̂₁ᵤ=37.5 against a 5% critical value of 1.76 (stationary after
one difference). So the DCD verdict contradicts the other formal test in the same
report block.

## Root cause (established 2026-08-08)

The over-differenced candidate keeps the baseline's DETERMINISTIC regressors, and
those compete with the witness. Holding everything else fixed on `IPC_ES_m10` and
varying only what the candidate carries:

| what the candidate keeps | n | θ̂ | LR (crit 1.94) | verdict |
|---|---|---|---|---|
| all deterministics (10 cos/sin + alter) | 11 | 0.9709 | **4.220** | consider d+1 ✗ |
| only the cos/sin pairs | 10 | 0.8669 | **14.956** | consider d+1 ✗ |
| only the `alter` (Nyquist) | 1 | 0.9948 | **0.015** | d confirmed ✓ |
| none | 0 | 0.9898 | **0.193** | d confirmed ✓ |

**Remove the harmonics and the verdict flips.** With only the Nyquist term the LR
is 0.015 — the witness sits on its boundary, exactly as the test intends. The
cos/sin pairs alone push it hardest (14.96).

The ARMA, which the docstring warns about, barely matters. Varying only the AR
order of the candidate:

| AR | 0 | 1 | 2 | 3 | 4 | 6 |
|---|---|---|---|---|---|---|
| θ̂ | 0.8646 | 0.9709 | 0.9636 | 0.9678 | 0.9675 | 0.9693 |
| LR | 18.619 | 4.220 | 5.797 | 4.375 | 4.122 | 3.285 |

The first AR term absorbs a lot (18.6 → 4.2) and after that it plateaus: θ̂ never
approaches +1 and the LR never drops below the critical value. So the residual
is not unmodelled autocorrelation.

### The precondition is inverted

The docstring prescribes:

> *"Best run on the deterministic/seasonal baseline (harmonics, no competing
> regular ARMA), so the witness — the sole regular MA — isolates f=0."*

It names the wrong competitor. The harmonics are what break the test and the
ARMA is what the docstring warns about. That is why the LR was **largest on the
cleanest baseline** (`IPC_ES_m00`: harmonics, no ARMA at all, LR = 18.6) — the
opposite of what the precondition predicts, and the observation this report was
filed to record.

Mechanism, stated as a hypothesis to check before fixing: the witness must reach
θ = +1 to cancel the extra ∇, and 10 free deterministic regressors can absorb
part of what that cancellation would otherwise have to do. The witness stops
short, and the DCD reads "invertible" as "the extra unit root is genuine".

### What this does NOT settle

Whether the fix is to drop the deterministics from the candidate, to re-express
them under the extra ∇, or to test on a different baseline altogether. Note that
∇ of a sinusoid is a sinusoid at the same frequency, so the regressors span the
same space and simply rescaling them *should* have been harmless — that it is
not is the part still unexplained, and it should be understood before anything
is changed. Related: BUG-0009 is the same family (a witness sharing a slot with
something that measures a different frequency).

## Impact

Medium and directional, as in BUG-0009: it fabricates a recommendation to
over-difference. Two aggravating factors, both already noted in BUG-0009:

* The verdict prints ✗ but `describe.py` still closes with *"Los contrastes formales no
  detectan problemas. El modelo es adecuado."* — raised and swallowed in one report.
* In an autonomous run nothing stops the recommendation from being acted on.

Distinct from BUG-0009 in trigger: there the model has a reformulated Nyquist
(`ifadf[s/2]=1`) whose witness gets overwritten. Here `ifadf` is **all zero** and no
frequency has been reformulated, so that mechanism cannot apply.

## Reproduction

```python
import fue
from art.formal_tests import dcd_overdiff_regular
for f in ("IPC_ES_m00.pre", "IPC_ES_m10.pre", "WTI_m10.pre"):
    _, m = fue.inp.load(f); m.fit()
    r = dcd_overdiff_regular(m)
    print(f, r.coef_free, r.lr)
```

`IPC_ES_m10.pre` is available in `bugs/BUG-0010-repro/`; the other two are in the
IPC_ES case work directory.

## Root cause

Not established. Candidate directions, none verified:

1. The deterministic seasonal package is carried into the d+1 candidate unchanged.
   Differencing again changes what the harmonics have to represent; if the candidate
   keeps fitting them on the over-differenced scale, the witness may be absorbing
   misspecification rather than the MA root it is meant to measure. The WTI control has
   no seasonal terms and behaves correctly, and the LR grows as the noise model shrinks
   (18.6 with no ARMA, 4.2 with AR(1)) — consistent with "something other than the
   witness is soaking up the extra difference", but far from conclusive.
2. Interaction with μ: the candidate sets `mu0=0, estimate_mu=False`, and IPC_ES has a
   strongly significant drift (μ̂=0.1545, t=5.4) that WTI does not (t=0.87).
3. A wrong-boundary contrast of the same family as BUG-0009 §12.

Direction 2 is the cheapest to test and should be tried first: re-run the control on a
non-seasonal series *with* a significant drift.

## Fix

None proposed — diagnosis required first.

## Validation

Once the cause is known: assert `d confirmed` on `IPC_ES_m00.pre` and `IPC_ES_m10.pre`,
whose integration order is established independently (Shin-Fuller Φ̂₁ᵤ=37.5, ADF/KPSS
consensus at d=1).
