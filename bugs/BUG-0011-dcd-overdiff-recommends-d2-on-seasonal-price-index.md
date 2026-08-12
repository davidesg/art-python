---
id: BUG-0011
title: dcd_overdiff_regular at f=0 uses the BARE null law and FUE's boundary likelihood — both are wrong there, and the paper says so
status: partially fixed — pair reported; the two calibration items remain
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

## RESOLUTION OF THE DIAGNOSIS (2026-08-12) — it is in the paper

After refuting four candidate explanations by measurement (recorded below), the
answer turned out to be documented in `SF_MEG/Borrador/SF_MEG.tex` and in
`SF_MEG/theory_regular_frequency_dcd.md`. **This is not a defect in how the
over-differencing candidate is built. It is two known limitations of the
production estimator, and both bite precisely at f=0.**

### (1) The critical value is the wrong one — resonance at the trend frequency

The paper, §"The realistic model: deterministic components":

> The decay is explained by **resonance**. The dramatic distortions reported by
> Chen and Davis (1995) for a non-zero mean arise because, **at the zero
> frequency, the constant regressor is resonant with the unit root; in our
> experiments at the trend frequency the same mechanism collapses the critical
> values.** At a seasonal frequency, however, the resonant components are exactly
> the harmonics at f, which the MEG annihilates with the unit-root filter.

And the measurement, same section: at the trend frequency **with the full
regressor set the pile-up is 0.927**, against 0.6575 bare.

`dcd_overdiff_regular` returns `freq=None`, which selects the **bare** s=1 law —
crit 1.00/1.94/4.41. That law is derived for a witness with no deterministic
regressors. At f=0 with a mean and eleven harmonics in the model, the null
distribution is not that one, and the paper measured how far off it is.

**This is what the design of the MEG avoids at the seasonal frequencies and
cannot avoid at f=0**: there the resonant regressor is the mean, and the extra ∇
does annihilate it — which is why the candidate drops μ — but the harmonics
remain, and at f=0 they are not annihilated by anything.

### (2) FUE's likelihood is unreliable exactly at the boundary

The paper's appendix, "Note on the exact likelihood near the boundary":

> A profile of the production estimator (FUE) against the exact likelihood …
> agrees throughout the interior r<1 but exhibits an **erratic upward jump
> exactly at the non-invertible boundary r=1**; this inflates the apparent
> pile-up and distorts the tail. … **This also implies that the MEG decision, as
> currently computed by the production software, should be revisited with the
> exact boundary likelihood.**

The LR is `2[ℓ(θ̂) − ℓ(θ=1)]`. The free fit lands in the interior (θ̂ = 0.9709),
where FUE is fine; **the constrained fit sits exactly on the boundary**, where it
is not. So one of the two terms is computed by an estimator the paper says is
distorted there.

That resolves the anomaly measured below: on IPC_ES the four log-likelihoods are

```
base with μ            ℓ =  −7.4026
free candidate         ℓ =  −7.9250   θ̂ = 0.9709
candidate at θ=1       ℓ = −10.0351   ← neither of the two values it could be
base without μ         ℓ = −18.0299
```

Under θ=1 the over-differenced model is `∇N = a + c`, so ℓ(θ=1) should equal the
once-differenced model with a free constant (−7.40) or with none (−18.03). It is
neither. A boundary value that is too LOW inflates the LR — which is the observed
direction.

**And it predicts exactly the pattern that was measured:** the artefact can only
bite when θ̂ < 1. When the estimate piles up at 1.0000 the free and constrained
fits are the same computation and the distortion cancels. That is why the
simulated I(1) case gives LR = −0.0000 with θ̂ = 1.0000 exactly, and IPC_ES gives
4.22 with θ̂ = 0.9709.

### Consequence for this report

The verdict «considera d+1» on IPC_ES is not the test failing to isolate f=0. It
is the LR being compared against a null law that does not hold for this model, and
computed with a boundary likelihood the paper has already flagged. Both are listed
as **Pending** in `theory_regular_frequency_dcd.md` §7 — this report is their
empirical manifestation at f=0.

The paper's own empirical section is this very model — Spanish CPI, 2002–2019,
n=216, logs, d=1, AR(1), eleven deterministics — and states that
Φ̂₁ᵤ = 37.5 "confirms that a single regular difference suffices". So d=1 is the
paper's answer for this series, and the DCD reading is the one to correct.

### DONE (2026-08-12) — item 3, the pair is reported

`describe_formal_tests` now emits a **«Par confirmatorio en f=0»** block whenever
both arms ran, states each side's verdict, and — when they disagree — labels it as
the quasi-cancellation diagnostic instead of letting the DCD line stand alone. On
IPC_ES:

```
**Par confirmatorio en f=0** — dos contrastes con nulas opuestas
- lado AR (Shin-Fuller, H₀: ρ=1): d basta ✓
- lado MA (DCD sobrediferenciación, H₀: θ=1): raíz genuina → d+1

  ⚠ DISCREPAN, y eso es el diagnóstico. Con θ̂=+0.9709 el testigo está a
  0.0291 de la frontera: es la banda de cuasi-cancelación … Los dos tienen razón.
  En esa banda las representaciones son equivalentes en previsión …
  No leas «considerar d+1» como una conclusión.
```

And the recommendation, which is what the assistant acts on, no longer says
*"Considera aumentar d en 1"*: it says the pair is in the band, that d must NOT be
changed on this evidence, and that the decision is parsimony or out-of-sample
forecasts.

The two caveats from the paper are printed with it, and only when they can bite:
the critical value is the BARE s=1 law while the model carries deterministic
regressors resonant with the f=0 unit root (pile-up 0.927 vs 0.6575), and θ̂ < 1
means ℓ(θ=1) is evaluated exactly where FUE's profile jumps.

`data["f0_pair"]` carries the whole thing for the MCP layer.

Tests: `tests/test_f0_confirmatory_pair.py`, 6 tests, all six failing against the
previous code — including the control that a series where the pair AGREES gets no
band warning (simulated I(1), θ̂ = 1.0000, LR ≈ 0).

### Still open — the two calibration items

### What the fix has to be

1. **Use the exact boundary likelihood for ℓ(r=1)**, as the appendix prescribes.
   The implementation exists: `research/sf_meg/dcd_mc.py` (banded Cholesky,
   continuous at the boundary). The DCD decision at f=0 should not use FUE's
   profile at r=1.
2. **Use the resonance-corrected critical value at f=0**, not the bare 1.94, when
   the model carries deterministic regressors. `research/sf_meg/deterministic_effect.py`
   is where that was measured.
3. **Report the pair, not the single verdict.** §"The two tests compared":
   disagreement between Shin-Fuller and the DCD *is* the quasi-cancellation
   diagnostic, not a contradiction to be resolved by picking one. On IPC_ES
   SF gives 37.5 and the DCD 4.22 — the pair is telling the analyst where they
   are, and the report should say so instead of emitting «considera d+1» alone.

Item 3 is already listed as pending in `theory_regular_frequency_dcd.md` §7
("Pair reporting") and is the cheapest of the three.

## Investigation 2026-08-12 — four explanations refuted, one mechanism measured

The bug stays OPEN. This section records what was ruled out, because each of
these looked plausible and none of them survives measurement, and a later reader
should not spend the time again.

### Refuted

**(1) Not the optimiser's starting point.** The candidate inherits the
baseline's harmonic coefficients, which are fitted for the undifferenced
problem, so a bad start was the obvious suspect. Re-seeding every harmonic to
zero gives θ̂ = 0.9709 and LR = 4.220 — identical to four decimals. Starting the
witness at 0.999 or at 0.50 instead of 0.85: identical again. The optimiser
converges to the same point from every start tried.

**(2) Not free parameters competing with the witness.** This was the hypothesis
this report proposed — ten free deterministic coefficients absorbing part of
what θ→+1 would otherwise have to do. Fixing all eleven deterministics at their
baseline values gives **LR = 4.212** against 4.220 free. Their fitted amplitudes
also barely move between baseline and candidate (mean |ω| 0.1380 → 0.1375, ratio
1.00). It is the PRESENCE of the regressors that matters, not their freedom.

**(3) Not a bias from deterministic seasonality as such.** Simulated I(1) with
drift plus a known deterministic seasonal, fitted with the correct model (5
harmonic pairs + μ + AR(1)), six samples at each of four seasonal amplitudes
(0, 0.25, 0.65, 1.5):

```
amplitud   θ̂ medio   LR medio   LR máx   falsos d+1
    0.00    0.9986      0.002    0.012      0/6
    0.25    0.9986      0.002    0.012      0/6
    0.65    0.9986      0.002    0.012      0/6
    1.50    0.9986      0.002    0.012      0/6
```

Zero false positives at every amplitude, LR flat at 0.002. **Deterministic
harmonics in the model do not inflate this test.**

**(4) Not the stochastic-seasonality misspecification.** IPC_ES has a stochastic
frequency (the MEG calls f=3 stochastic, LR 2.31 > 2.07), so an obvious
candidate was that a fixed harmonic fitted to a wandering amplitude leaves a
non-stationary seasonal residual the regular witness then has to absorb — the
model being inadequate, and the regular test reporting it. Reformulating that
frequency does not move the verdict:

| model | θ̂ | LR |
|---|---|---|
| m10, all deterministic | 0.9709 | 4.220 |
| m10 with f=3 stochastic (the one the MEG flags) | 0.9707 | **4.251** |
| m10 with f=2 stochastic | 0.9711 | 4.142 |
| m10 with f=4 stochastic | 0.9710 | 4.197 |

### What IS measured

**The effect tracks the amplitude of the LARGEST harmonic, and it peaks at the
FITTED value.** Scaling only the f=2 pair of IPC_ES, coefficients held fixed:

| scale | amplitude | θ̂ | LR |
|---|---|---|---|
| 0.00 | 0.0000 | 0.9898 | 0.193 |
| 0.25 | 0.1614 | 0.9836 | 0.978 |
| 0.50 | 0.3229 | 0.9756 | 3.052 |
| **1.00** | **0.6457** | **0.9518** | **9.389** |
| 1.50 | 0.9686 | 0.9766 | 2.799 |
| 2.00 | 1.2915 | 0.9905 | 0.147 |

Not monotone. The maximum sits exactly at the fitted amplitude and the LR
collapses on both sides — which is a strong hint and not yet an explanation.

**And the frequency is a red herring.** This report's original reading, and the
first one taken here, was that f=2 is special: it is the unique frequency where
|1 − e^{−iω}| = 1, so differencing neither amplifies nor attenuates it. That is
true and irrelevant. Run per-frequency on three series, what moves the LR is the
LARGEST harmonic:

| series | no deterministics | largest pair alone | which f | its amplitude |
|---|---|---|---|---|
| IPC_ES | 0.193 | **9.395** | f=2 | 0.6457 |
| Chile | 21.817 | **26.066** | f=1 | 0.4235 |
| Colombia | 6.819 | **27.365** | f=1 | 1.6806 |

f=2 is simply IPC_ES's largest (0.6457 against 0.2314 for the next). In Chile
and Colombia it is f=1, and f=1 is what moves the verdict there.

Note also that Chile and Colombia are I(2), so *"d+1"* is the correct answer for
them with or without the deterministics. The defect only bites where d is
genuinely 1.

### One route attempted and discarded, with its trap

The natural next measurement is to extract the model's own noise
`N = ln(y)·100 − D̂`, test it as a standalone series with no deterministics, and
see which of the two rows it agrees with. **Do not rebuild `D̂` by hand.** A
reconstruction as `Σ ω_k cos(2πkt/12) + Σ ω_k sin(…)` — the obvious one, at
either scaling — does not reproduce the model: fitting AR(1)+μ on that "noise"
gives φ = −0.154 or 0.187 against the model's 0.4027, and μ = 15.9 or 0.226
against 0.1545. The deterministic component is not that expression, so any
verdict computed on it is about a different series. This route needs fue's own
`D̂`, not a hand rebuild.

### Where that leaves it

The mechanism is neither optimisation, nor parameter competition, nor a general
bias from seasonal deterministics, nor the known seasonal misspecification. It
is specific to the largest harmonic and maximal at its fitted amplitude. The
next measurement to make is the one above, done properly — the model's own
deterministic component, from fue — and the question it answers is whether the
two rows of the original table are testing the same series at all.

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
