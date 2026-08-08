---
id: BUG-0010
title: Pruning a non-significant harmonic pair silently voids the ENTIRE MEG sweep, and the report then closes with "el modelo es adecuado"
status: open
severity: high
component: formal-tests
found_in: 0.1.4
fixed_in:
reported: 2026-08-08
reporter: David / IPC_ES passthrough
tags:
  - meg
  - seasonality
  - harmonics
  - silent-failure
  - guidance
references:
  - src/art/formal_tests.py:1136-1137 (`meg`: the up-front `_check_reformulable` loop over ALL frequencies)
  - src/art/formal_tests.py:806-812 (`_check_reformulable`: raises when f has no cos/sin)
  - src/art/describe.py:1409-1410 (`describe_formal_tests`: `_try(lambda: meg(model), [])`)
  - src/art/describe.py:1507 (the `elif run_meg and not _meg_suitable(model)` branch that never fires)
  - src/art/full_report.py:569-573 (`_meg_suitable`: true if ANY cos/sin/alter is present)
  - src/art/describe.py:1364-1368 (over-parametrisation note appended next to "procede a DCD, MEG", unordered)
  - src/art/mcp_server.py:1274-1277 (`test_seasonal_simplification` docstring: "safely remove those harmonics and refit" — MEG unmentioned)
  - bugs/BUG-0010-repro/ (two IPC_ES .pre + repro.py: same series, one harmonic pair of difference)
---

## Summary

Drop one non-significant harmonic pair from a model and the MEG does not lose that
frequency — it loses **every** frequency. `meg()` validates all requested frequencies
before computing any of them, so the pruned frequency's `ValueError` aborts the sweep;
`describe_formal_tests` calls it inside `_try(..., [])`, which turns the exception into
an empty list; and `_meg_suitable()` is still true (the model does still have cos/sin
terms), so the *"MEG no aplica"* branch never fires either. The MEG section disappears
from the report **without a single word**, and the recommendation line becomes

> Los contrastes formales no detectan problemas. El modelo es adecuado.

On the case that surfaced this (IPC_ES), the verdict thrown away was `freq=3:
**stochastic**` — a reformulation the analyst is instead told is unnecessary.

## Impact

**High, and worse than the plumbing suggests, because the natural workflow walks
straight into it.** The over-parametrisation note in `describe_diagnosis` ("Considera
eliminar el parámetro menos significativo de cada par") is appended to the very same
recommendation string that says "Procede a los contrastes formales (DCD, MEG)", with no
ordering between them; `test_seasonal_simplification`'s docstring says to pass the
harmonics with |t| ≤ 2 and "safely remove those harmonics and refit", and never
mentions the MEG. Nothing in the pipeline documentation (`mcp_server.py` ETAPA 3 → 4)
states that seasonal-harmonic pruning must come **after** the MEG. So an assistant
following the tool's own advice prunes first, and the MEG silently stops existing.

**The ordering is not a preference — pruning by t-ratio pre-judges the MEG's
hypothesis.** The MEG's null model *is* the deterministic harmonic at f, so a
frequency with no cos/sin has nothing to contrast. And the pruning criterion is not
neutral with respect to the question being asked: a fixed-coefficient harmonic fitted
to a frequency whose amplitude wanders averages toward zero, so a **low t-ratio at f is
evidence FOR stochastic seasonality at f**, not evidence that f is absent. Pruning by
significance therefore removes preferentially the frequencies the MEG most needs to
examine, under the maintained hypothesis (deterministic) that the MEG exists to test.

IPC_ES shows the two criteria are close to orthogonal, in both directions at once:

| f | harmonic \|t\| (cos, sin) | MEG LR (crit 2.07) | MEG verdict |
|---|---|---|---|
| 3 | **5.4, 2.1** — most significant pair | **2.313** | **stochastic** |
| 5 | **0.29, 1.27** — the pruning candidate | 1.771 — 2nd highest | deterministic |

f=5, the pair a significance filter deletes first, carries the second-strongest
evidence of stochasticity in the model. f=3, which no filter would touch, is the one
that is actually stochastic.

Anything downstream that assumes deterministic seasonality inherits the error silently.
The case here is a transfer-function build (`mtram`/drtran): the WTI input has no
seasonality, so its prewhitening filter carries no seasonal factor, and an output left
stochastic at f=3 stays non-stationary at that frequency after filtering — the CCF then
shows structure everywhere and the contiguous-block heuristic reads an order off it
anyway.

## Reproduction

`bugs/BUG-0010-repro/` — two IPC_ES models (INE Spanish CPI, 2002-01…2019-12, n=216,
λ=0, d=1, D=0, AR(1) + μ, deterministic seasonality). They differ **only** in whether
the f=5 cos/sin pair is present.

```
$ cd bugs/BUG-0010-repro && python repro.py

PART 1 — the symptom: dropping f=5 removes every MEG verdict, not just f=5's

FULL    5 harmonic pairs + Nyquist (pre-MEG baseline)
    cos/sin harmonics present: f = [1, 2, 3, 4, 5]        _meg_suitable = True
    describe_formal_tests -> MEG section present: True
      - freq=1: coef=-0.9897, LR=0.024 (crít 5%=2.07) → **deterministic**
      - freq=2: coef=-0.9886, LR=0.024 (crít 5%=2.07) → **deterministic**
      - freq=3: coef=-0.9539, LR=2.313 (crít 5%=2.07) → **stochastic**
      - freq=4: coef=-0.9678, LR=0.914 (crít 5%=2.07) → **deterministic**
      - freq=5: coef=-0.9647, LR=1.771 (crít 5%=2.07) → **deterministic**
      - freq=6: coef=-1.0000, LR=-0.000 (crít 5%=1.94) → **deterministic**
    recommendation: Reformulación necesaria:

PRUNED  f=5 dropped for |t| < 2, everything else identical
    cos/sin harmonics present: f = [1, 2, 3, 4]        _meg_suitable = True
    describe_formal_tests -> MEG section present: False
    recommendation: Los contrastes formales no detectan problemas. El modelo es adecuado.

PART 2 — the mechanism: the up-front validation loop is all-or-nothing

  meg(model)                 -> ValueError: the baseline has no cos/sin harmonics at f=5 ...
  meg(model, frequencies=[1,2,3,4,6])  -> the testable frequencies alone:
      freq=1  LR=  0.022   deterministic
      freq=2  LR=  0.019   deterministic
      freq=3  LR=  2.229   stochastic
      freq=4  LR=  0.862   deterministic
      freq=6  LR= -0.000   deterministic
```

The controlled part is PART 1: same series, same λ, d, D, same noise model, one
harmonic pair of difference — and a *stochastic* verdict at an untouched frequency
becomes a clean bill of health. PART 2 shows the four surviving frequencies were
computable all along.

## Root cause

Three layers, each individually defensible, jointly silent.

1. **`formal_tests.py:1136-1137` — validation is all-or-nothing.**

   ```python
   for f in frequencies:            # f = 1 … s//2
       _check_reformulable(model, f, s)
   ```

   Every frequency is checked before any is computed, so one unreformulable frequency
   aborts the whole sweep. `_check_reformulable` itself is correct: without the
   deterministic harmonic at f there is no null model to contrast.

2. **`describe.py:1409-1410` — the exception is swallowed.**

   ```python
   meg_res = _try(lambda: meg(model), []) if run_meg and _meg_suitable(model) else []
   ```

   `_try` returns `[]` on any exception, making "raised" indistinguishable from "not
   requested". The actionable message `_check_reformulable` took care to write is
   discarded.

3. **`describe.py:1507` — the fallback notice cannot fire.** The `elif run_meg and not
   _meg_suitable(model)` branch prints *"MEG no aplica"*, but `_meg_suitable` only asks
   whether **any** cos/sin/alter exists (`full_report.py:569-573`). A model pruned at
   one frequency is still "suitable", so neither the results nor the notice is printed.

The `sf_res is None and not dcd_res and ... and not meg_res` guard at `describe.py:1512`
doesn't catch it either, since Shin-Fuller and DCD did run.

## Fix

**Code — make the sweep per-frequency and never silent:**

```python
# formal_tests.meg: drop the up-front loop; validate inside the per-frequency loop
results, skipped = [], []
for f in frequencies:
    try:
        _check_reformulable(model, f, s)
    except ValueError as e:
        skipped.append((f, str(e)))
        continue
    ...
```

and return the skips alongside the results so `describe_formal_tests` can print, per
frequency, either a verdict or *why there isn't one*. Replace the blanket
`_try(lambda: meg(model), [])` with a handler that surfaces the message; a MEG that
cannot run must say so, since its absence is currently read as "nothing to report".

**Guidance — state the ordering wherever pruning is offered:**

* `describe.py:1364-1368`: when the high-correlation pair involves seasonal cos/sin
  terms, the note must not say "elimina el menos significativo" unconditionally — it
  should say the seasonal pruning comes **after** the MEG.
* `test_seasonal_simplification` / `seasonal_param_analysis` docstrings: state the
  precondition, that the MEG has already run on the all-deterministic baseline, and
  why a low t-ratio is not evidence of absence at that frequency.
* `mcp_server.py` pipeline (ETAPA 3 → ETAPA 4): make explicit that the simplification
  of the *deterministic seasonal* parameters belongs after ETAPA 4's MEG, even though
  formal tests are otherwise run on parsimonious models. The general rule — test on a
  parsimoniously parametrised model — does not extend to the parameters that *are* the
  hypothesis under test.

## Validation

Regression test: on `IPC_ES_m10.pre` and `IPC_ES_m10_podado.pre`, assert that
`describe_formal_tests(..., run_meg=True)` reports the f=3 **stochastic** verdict in
BOTH, and that the pruned model additionally reports f=5 as skipped-with-reason rather
than omitted. Current code fails both halves: the pruned model reports no MEG at all
and recommends nothing. The repro files are ~4.6 KB each and self-contained, so they
can be promoted into `tests/` directly.

Related: BUG-0009 (same `formal_tests` area; a verdict raised as ✗ and simultaneously
swallowed by the closing "el modelo es adecuado" line — the same failure of the report
layer to carry a negative result through to the recommendation).
