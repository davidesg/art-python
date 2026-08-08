---
id: BUG-0009
title: dcd_overdiff_regular overwrites the Nyquist witness (both are regular MA(1) but measure opposite roots) and reports a spurious d+1
status: open
severity: medium
component: formal-tests
found_in: 0.1.3
fixed_in:
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
