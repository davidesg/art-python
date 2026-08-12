---
id: BUG-0009
title: dcd_overdiff_regular overwrites the Nyquist witness (both are regular MA(1) but measure opposite roots) and reports a spurious d+1
status: fixed
severity: medium
component: formal-tests
found_in: 0.1.3
fixed_in: 0.1.11 (unreleased)
reported: 2026-07-24
reporter: David / SF_MEG NL_CPI
tags:
  - dcd
  - nyquist
  - over-differencing
  - integration-order
  - meg
references:
  - src/art/formal_tests.py:543-600 (dcd_overdiff_regular; `mc.ma = [[float(witness_init)]]`)
  - src/art/describe.py:1442-1452 (the "DCD sobre-diferenciación regular" report block)
  - bugs/BUG-0009-repro/ (three .pre + repro.py: self-contained, controlled reproduction)
  - SF_MEG empirical/ART_MCP_ISSUES.md §12 (same root confusion in formal_tests: the
    Nyquist witness is contrasted against H₀ θ=+1 instead of θ=−1)
  - SF_MEG empirical/cases/NL_CPI/DECISIONS.md D3 (the case where this surfaced)
---

## Summary

`dcd_overdiff_regular` builds its over-differenced candidate by **commandeering the
regular-MA slot**:

```python
mc.ma = [[float(witness_init)]]      # "replace any existing regular MA"
```

That slot is not always free. When the **Nyquist frequency f = s/2 has been
reformulated to stochastic**, `meg_reformulate` stores the Nyquist witness
`(1 + λ_{s/2}B)` there — because it, too, is a regular MA(1) polynomial. The two are
the same *shape* but measure **opposite roots**:

| | factor imposed | root | witness tends to | frequency |
|---|---|---|---|---|
| regular difference `d` | `(1 − B)` | B = **+1** | θ → **+1** | 0 |
| `ifadf[s/2]` | `(1 + B)` | B = **−1** | θ → **−1** | s/2 |

So the assignment silently **deletes a witness belonging to a different frequency**,
while `mc.ifadf[s/2] = 1` survives untouched. The candidate model is left with an
**uncancelled `(1 + B)` seasonal unit root**, and the f=0 witness — now the only
regular MA — has to absorb it. θ̂ is dragged off +1, the LR clears the critical value,
and the report concludes *"testigo invertible → raíz unitaria regular genuina →
considerar d+1 ✗"* on a model whose `d` is correct.

Note the category error underneath: **f = s/2 is not governed by `d` at all.** Its
integration order is `ifadf[s/2]`; `d` is the order at frequency zero. A test that
confirms the *regular* integration order should never disturb the seasonal one.

## Resolution (2026-08-12)

Each frequency now carries its own witness and they are never shared.

When the Nyquist frequency is stochastic (`ifadf[s/2] = 1`) the baseline's own
regular MA is **not competition** — it is what cancels `(1 + B)` — so it is kept
and the f=0 witness is appended in a slot of its own. Where there is no
collision the behaviour is byte-identical to before.

There is a second reason this is the right shape, and it is the opposite of what
the original design feared. The docstring replaced any existing regular MA so
that the witness, being the sole one, would "isolate f=0": a free regular MA left
to itself can drift negative, and its root then points at B = −1, measuring the
Nyquist frequency instead. But when Nyquist already has its own witness pinned to
θ = −1, the f=0 witness is no longer tempted there. **Keeping it makes the
isolation better, not worse.**

### Measured, and the direction is not the one this report predicted

| model | LR before | LR after |
|---|---|---|
| Nyquist deterministic (`ifadf` all zero) | 4.220 | **4.220** — identical |
| Nyquist stochastic (`ifadf[6] = 1`) | **1.859** | **4.257** |

This report predicted that the deleted witness would drag θ̂ off +1 and produce a
spurious *d+1*. On this case it did the opposite: the orphaned `(1 + B)` pulled
the f=0 witness towards −1, θ̂ moved from 0.9709 to 0.9787 and the LR fell BELOW
the critical value, so the old code reported *d confirmed*.

The direction was incidental. **The defect is that the verdict moved at all**,
and that is the right way to state it: reformulating f = 6 to stochastic does not
change `d`, so a test of the regular order must return the same answer either
way. Before the fix it swung 4.220 → 1.859; after it, 4.220 → 4.257. That
invariance is what the regression test asserts, not the verdict.

Both post-fix figures sit above the critical value, which is BUG-0011 — the
deterministic harmonics competing with the witness — and is untouched here. The
two defects share a family and a routine, and they are now separable: this one is
about the SLOT, that one about the REGRESSORS.

### The category error, stated

`f = s/2` is not governed by `d` at all. Its integration order is `ifadf[s/2]`;
`d` is the order at frequency zero. A test that confirms the REGULAR order must
never disturb the SEASONAL one — and in the `(1 − θB)` convention the two
witnesses are heading for opposite boundaries, θ = +1 to cancel `(1 − B)` and
θ = −1 to cancel `(1 + B)`, which is exactly why sharing a slot could never work.

### Calibration checked first

Before touching anything, the test was verified on the case with a known answer:
a random walk with drift, `∇w_t − μ = a_t`, no harmonics and no ARMA, 25 samples
at μ=0.15 and σ=0.25. False-positive rate **1/25 = 4 %** against a nominal 5 %,
and θ̂ lands exactly on the boundary in 12 of the 25. The machinery of the test is
sound; both this defect and BUG-0011 are about what else the candidate carries.

Tests: `tests/test_bug_0009_witness_slot_collision.py`, 5 tests. Two fail against
the previous code — the slot and the invariance — and the other three are guards
that must keep passing either way.

## Impact

Medium. Silent and directional: it does not crash, it **fabricates a recommendation to
over-difference**, and it only fires on models where Nyquist has been reformulated —
i.e. exactly the MEG models the seasonal branch exists to produce. In an autonomous
run this pushes the analyst toward d=2, which on a price index means a quadratic drift
in the level.

Aggravated by two neighbouring issues:

* The verdict is printed as ✗ but `describe.py` still closes the report with *"Los
  contrastes formales no detectan problemas. El modelo es adecuado."* — so the false
  alarm is simultaneously raised and swallowed (SF_MEG `ART_MCP_ISSUES.md` §13).
* Same-family confusion in `formal_tests`: the Nyquist witness is also routed to the
  **regular** DCD and contrasted against `H₀: θ=1` when its boundary is θ=−1, yielding
  `LR = 715` on a θ̂ = −0.9758 that is sitting *on* its boundary (§12).

## Reproduction

`bugs/BUG-0009-repro/` — three NL_CPI models (CBS national CPI, 2002-01…2019-12,
n=216, λ=0, d=1, D=0) that differ **only** in which frequencies were reformulated:

```
$ cd bugs/BUG-0009-repro && python repro.py

PART 1 — the symptom: the verdict flips when, and only when, f=6 is reformulated
D    baseline, nothing reformulated
    model.ma = []                          ifadf[6] = 0
    theta = +1.0000   LR =  -0.000   ->  d confirmed
S23  f=2,3 reformulated  (no Nyquist)
    model.ma = []                          ifadf[6] = 0
    theta = +1.0000   LR =  -0.000   ->  d confirmed
S236 f=2,3,6 reformulated (WITH Nyquist)
    model.ma = [[-0.9757662283488461]]     ifadf[6] = 1
    theta = +0.7295   LR =   4.211   ->  consider d+1  <-- WRONG

PART 2 — the mechanism: preserving the Nyquist witness restores theta = +1
  current  mc.ma = [[0.85]]   -> candidate ma = [[0.7295]]            theta_f0 = +0.7295
  proposed keep + append      -> candidate ma = [[-0.9763], [1.0]]    theta_f0 = +1.0000
```

The controlled part is the S23/S236 contrast: same series, same `d`, same λ, one
reformulated frequency of difference — and the verdict on `d` flips.

## Root cause

`src/art/formal_tests.py`, `dcd_overdiff_regular`:

```python
mc.ma = [[float(witness_init)]]
mc.ma_free = [[True]]
```

The docstring states the precondition — *"Best run on the deterministic/seasonal
baseline (harmonics, no competing regular ARMA), so the witness — the sole regular MA —
isolates f=0"* — but nothing **enforces or restores** it. On a Nyquist-reformulated
model the precondition is violated by construction, and the replacement makes it worse
than a competing ARMA term would: it removes the factor that was cancelling an imposed
unit root, so the misspecification the witness absorbs is a full seasonal unit root.

## Fix

Preserve the existing regular MA operators and **append** the f=0 witness, taking the
witness as the last factor:

```python
prev = [list(op) for op in mc.ma]
mc.ma      = prev + [[float(witness_init)]]
mc.ma_free = [[True] * len(op) for op in prev] + [[True]]
mc.fit()
theta_hat  = _extract_ma_param(mc, len(prev))     # witness is LAST, not index 0
```

Verified in PART 2 of the repro: θ̂ returns to **+1.0000**, LR ≈ 0, *d confirmed* —
matching D and S23 exactly.

Two guards worth adding alongside:

1. If `ifadf[s/2] == 1` and the regular-MA slot is empty, the Nyquist witness is
   missing altogether — the model is malformed for this test; warn rather than
   silently proceed.
2. Distinguish the two witnesses explicitly (by which unit factor they cancel) rather
   than by slot position, which would also fix §12's wrong-boundary contrast. Sharing
   `m.ma` is a `fue` storage detail, not a statement that the factors are comparable.

## Validation

Regression test: assert that `dcd_overdiff_regular` returns the **same verdict** on
`NL_CPI_S23.pre` and `NL_CPI_S236.pre` (both `d confirmed`, LR < 1.94), since the two
differ only in a seasonal frequency and `d` is identical. The current code fails it;
the proposed fix passes. The repro files are small (≈4.6 KB each) and self-contained,
so they can be promoted into `tests/` directly.
