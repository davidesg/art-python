---
id: BUG-0016
title: decide_d takes the ADF+KPSS consensus straight, so a seasonal series jumps from d=0 to d=2 in one step — with the seasonality that contaminated the tests already detected three lines earlier and ignored
status: open
severity: high
component: policy
found_in: 0.1.5
fixed_in:
reported: 2026-08-08
reporter: David / IPC-WTI passthrough, 8-country batch
tags:
  - policy
  - integration-order
  - over-differencing
  - seasonality
  - autonomous
references:
  - src/art/policy.py:56-61 (`decide_d`: `return int(unit_root_data["recommended_d"])`, nothing else)
  - src/art/pipeline.py:731-736 (`run_full`: seasonality decided FIRST, then `decide_d` which never sees it)
  - bugs/BUG-0002-over-differencing-kpss.md (fixed in the guided path; the autonomous one kept the behaviour)
  - bugs/BUG-0011-dcd-overdiff-recommends-d2-on-seasonal-price-index.md (same contamination, different test)
  - bugs/BUG-0016-repro/
---

## Summary

`policy.decide_d` is the whole decision:

```python
def decide_d(unit_root_data: dict) -> int:
    return int(unit_root_data.get("recommended_d", 1))
```

No cap, no reference to the seasonal structure. And `run_full`
(pipeline.py:731-736) has already answered the seasonal question by the time it
asks:

```python
seas = describe_seasonality(ts)
D, decision, n_harmonics = pol.decide_seasonal_structure(seas.data, ts.freq)
urt  = describe_unit_root(ts, lam=lam)      # ADF+KPSS with the seasonality IN
d    = pol.decide_d(urt.data)               # and it never sees D
```

So the pipeline can go from `d=0` to `d=2` in one move, on a series it has just
declared seasonal, using tests that the seasonality contaminated.

## Why this is a methodological defect and not a tuning question

Two rules of the school are broken at once.

**One decision at a time.** Box-Jenkins moves `d` by a single step and re-reads
the plot. Going 0 → 2 in one jump is not a step, it is a conclusion. The level
plot of a CPI index says "at least d=1" by itself; whether a SECOND difference
is warranted is a separate question, and it is asked on the once-differenced
series, not on the level.

**Seasonality contaminates the unit-root tests, so it is settled first.** The
ADF regression carries no seasonal terms, so a strong seasonal pattern goes to
its residual variance, inflates the standard error of the coefficient and biases
it towards NOT rejecting the unit root — which reads as "difference again".
Seasonality itself is normally read on a roughly CENTRED series, which is exactly
why the guided path runs its HAC test on ∇y(λ) and not on the level.

Over-differencing a price index is not a venial error: it injects an MA unit root
at −1, and in a transfer function it destroys the interpretation of the gain.

## Reproduction

```
python3 bugs/BUG-0016-repro/repro.py       # exits 1 while the bug is live
```

Eight monthly CPI indices, 2002-01…2019-12, n=216, λ=0 throughout (the index
rule — see BUG-0015), ranked by the strength of their seasonality:

```
   series      F-HAC   seasonal?   D  harm   recommended_d   decide_d
   IPC_ES        90.1        True   0     5               2          2   <-- OVER-DIFFERENCED
   IPC_UK        57.7        True   0     5               2          2   <-- OVER-DIFFERENCED
   EMU           45.4        True   0     5               1          1
   IPC_DE        34.5        True   0     5               1          1
   IPC_FR        33.3        True   0     5               1          1
   CPI_USA       14.3        True   0     5               1          1
   IPC_JP        12.9        True   0     5               1          1
   IPC_CA        10.9        True   0     5               1          1
```

**The two that over-difference are exactly the top two of the seasonality
ranking**, with a clean break at F-HAC ≈ 50. That is the contamination, measured:
the stronger the seasonal pattern, the harder ADF finds it to reject. All eight
already carry `seasonal_detected = True` and a full harmonic package (D=0, 5
pairs) decided BEFORE `decide_d` is called.

Independently confirmed through the full pipeline: `batch_build` returns `d=2`
for IPC_UK. The guided path returns `d=1` for both ES and UK, on the same data.

### The interaction with BUG-0015, which must not be missed

IPC_ES comes back from `build_model` with `d=1` **only because the policy chose
λ=1 for it** (BUG-0015). With the index rule applied — λ=0, which is correct —
ES over-differences too. **Fix the index rule alone and this bug fires on more
series than it does today**, and will look like a regression of the fix. They
have to move together.

## Fix

`decide_d` needs two things it does not have:

1. **The seasonal decision.** Pass `D` / `seasonal_detected` in, and cap `d` at 1
   whenever seasonality is present and untreated. That is the ordering rule the
   guided path already follows.
2. **A step limit.** Never advance `d` by more than one from the current value in
   a single decision. If the tests say 2 on an undifferenced series, that is
   evidence to take `d=1` and ask again, not to take 2.

The deeper fix is the same one BUG-0015 asks for: the unit-root evidence should
be computed on a series whose seasonality has been accounted for, so the tests
are not being asked a question their regression cannot represent. Running the
ADF with the harmonics that `decide_seasonal_structure` just chose would be the
cheap version.

Note this is the autonomous twin of BUG-0002, which was fixed in
`guided_identification` and left in the policy, and it is the same contamination
BUG-0011 documents for the DCD — three symptoms, one cause: **unit-root
statistics are being read off a series that still contains its seasonality.**

## Validation

- `bugs/BUG-0016-repro/repro.py` must return 0: no series over-differences.
- Run it with the BUG-0015 fix in place as well — that is the configuration that
  exercises the most series, and the one where a partial fix regresses.
- Guard the other direction: a genuinely I(2) series must still be allowed to
  reach `d=2`, by two successive single steps, not by a cap that forbids it.
