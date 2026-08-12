---
id: BUG-0016
title: decide_d takes the ADF+KPSS consensus straight, so a seasonal series jumps from d=0 to d=2 in one step — with the seasonality that contaminated the tests already detected three lines earlier and ignored
status: fixed
severity: high
component: policy
found_in: 0.1.5
fixed_in: 0.1.11 (unreleased)
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

## Resolution (2026-08-12) — junto con BUG-0015, como este informe exigía

`decide_d(unit_root_data, seasonal=None, current_d=0, max_step=None)`. Con
estacionalidad detectada y sin tratar, **d se topa en 1**; `run_full` le pasa
ahora la decisión estacional que ya había tomado tres líneas antes.

### El tope va en la POLÍTICA, no en la evidencia

`recommended_d` sigue reportando lo que los tests hallaron. En la tabla del repro
se ve el diseño:

```
   series      F-HAC   seasonal?   D  harm   recommended_d   decide_d
   IPC_ES        90.1        True   0     5               2          1
   IPC_UK        57.7        True   0     5               2          1
   EMU           45.4        True   0     5               1          1
   ...
```

Se sugirió 2, se topó a 1, y **se ve que se topó**. Si el tope viviera dentro del
estadístico, la evidencia mentiría sobre lo que halló.

### One step at a time, and why it is the method rather than an option

`max_step` defaults to **1**: d never advances by more than one in a single
decision, seasonality or not. The first implementation left this off by default,
on the argument that capping a non-seasonal series would silently
under-difference a genuine I(2) to fix a defect it does not have. That argument
is wrong, and the correction is worth recording because it is the substance of
the rule rather than a tuning choice.

*The question asked from the level is not "how many differences?"* It is "is at
least one regular difference needed?". Seasonality is normally read on a series
already differenced once, so from d=0 the question of whether a SECOND difference
is warranted has never been put. A series may well be I(2) — but that is not what
the test at d=0 examined, least of all on a series that may carry seasonality.
Jumping 0 → 2 is not answering quickly; it is answering a question nobody asked.

*Take the obvious step first.* If d=1 is the obvious reading, d=2 is not
reachable from d=0 in one move. And this cuts both ways: low power can equally
leave the test failing to call for a difference at all, but a series that trends
and may be seasonal is a reason to doubt the test rather than to believe it, and
the obvious step remains d=1. Nominal series in economics and finance are almost
always d=1, and occasionally d=2.

**Nothing is lost by starting low, and that is what settles the objection.** ADF,
KPSS and the plot are tools of INITIAL SPECIFICATION, sound as such and not asked
to be the last word. The real contrast on the order of integration comes at the
END of the process, on a model that is adequate and correctly specified —
`dcd_overdiff_regular` and Shin-Fuller — which is exactly where this flow already
puts them. Capping at identification does not under-difference in silence; it
defers the question to where it can be answered properly, instead of settling it
with an instrument that cannot yet see.

From `current_d=1` the second difference is reachable, because by then the
question has been asked.

The "deeper fix" this report mentions — running the ADF with the harmonics that
`decide_seasonal_structure` has just chosen, so the test is not asked a question
its regression cannot represent — remains open and is the right medium-term
route.

### La interacción se confirmó

Este informe avisaba: *«arregla la regla índice sola y este bug dispara en más
series»*. Cierto — con λ=0, IPC_ES pasa a sobrediferenciar. Por eso se movieron
juntos, y la tabla de las ocho series es la comprobación conjunta.

Tests: `tests/test_bug_0015_0016_policy_domain_and_d_cap.py`. Contra el código
previo fallan 20 de 23.

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
