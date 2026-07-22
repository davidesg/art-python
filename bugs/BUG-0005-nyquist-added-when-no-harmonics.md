---
id: BUG-0005
title: Nyquist alter harmonic is added even when n_harmonics=0 (non-seasonal series get a spurious deterministic)
status: fixed
severity: medium
component: pipeline
found_in: 0.1.2
fixed_in: 0.1.3
reported: 2026-07-22
reporter: D. E. Guerrero
tags:
  - pipeline
  - harmonics
  - seasonality
references:
  - drtran passthrough example (WTI input model)
---

## Summary

`confirm_and_estimate(..., D=0, n_harmonics=0)` still injects the Nyquist
harmonic `alter` = (−1)ᵗ into the model. `n_harmonics=0` is the guided flow's
signal for "no seasonal deterministics" (the `decision="A"` / no-seasonality
branch), so a **non-seasonal** monthly/quarterly series ends up with a spurious,
almost always insignificant, Nyquist deterministic term.

## Impact

Any series identified as non-seasonal (HAC joint test not significant → D=0,
n_harmonics=0) gets an extra (−1)ᵗ regressor. User-visible effects:
- the model equation shows a bogus `± c·(−1)ᵗ` term (in the case that surfaced
  this, WTI crude oil: `− 0.1258·(−1)ᵗ`, t = −0.58, clearly insignificant);
- one wasted degree of freedom (AIC/BIC/ℓ slightly off);
- it diverges from the intended pure ARIMA(p,1,q) specification and from any
  reference model, which for a non-seasonal series has no seasonal terms at all.

Not catastrophic (the term is estimated free and usually near zero), but wrong,
and it forces the analyst to hand-edit the `.pre` to recover the clean model.

## Reproduction

```python
confirm_and_estimate(
    inp_path="WTI.inp",     # a non-seasonal monthly series (freq=12)
    output_path="WTI.inp",
    lam=0.0, d=1, D=0, p=1, q=0,
    n_harmonics=0,          # analyst decided: no seasonality
    estimate_mu=False,
)
# → model contains an `alter` deterministic:  − 0.1258 (−1)ᵗ
```

## Root cause

`src/art/pipeline.py`, `_make_model`, D=0 branch. The cos/sin pairs are correctly
gated by `n_harm = min(n_harmonics, max_pairs)`, but the Nyquist `alter` was
appended unconditionally for any seasonal period (`if freq >= 2:`).

The deeper cause is that **`n_harmonics` is a lossy encoding of the seasonality
decision.** `policy.decide_seasonal_structure` returns the decision (`"A"` no
seasonality / `"B1"` deterministic / `"B2"` multiplicative) but only propagates
`n_harmonics = max(freq//2−1, 0) if decision != "A" else 0`. So `n_harmonics=0`
means **two incompatible things**: (1) decision `"A"` — no seasonality; and (2)
decision `"B1"` at **freq=2** (semi-annual), where the only seasonal harmonic IS
the Nyquist and there are zero cos/sin pairs. The builder cannot tell them apart
from `n_harmonics`, so it added the alter based on `freq>=2` alone — injecting a
spurious alter into non-seasonal ARIMA models. A first patch gating the alter on
`n_harmonics>0` fixes case (1) but silently breaks case (2); the existing tests
missed both because neither the non-seasonal count nor the freq=2 case was covered.

## Fix

Gate the **whole deterministic seasonal package** (cos/sin pairs + Nyquist alter)
on an explicit `seasonal` flag threaded to `_make_model` — never on `n_harmonics`,
which is ambiguous. When `seasonal is None` it defaults to `n_harmonics>0` (correct
for the common freq>=4 case); callers that know the decision pass it explicitly
(`seasonal = decision != "A"`), which covers freq=2.

```python
def _make_model(..., n_harmonics, ..., seasonal: bool | None = None):
    if D == 0:
        if seasonal is None:
            seasonal = n_harmonics > 0
        itvs = []
        if seasonal:
            for k in range(1, min(n_harmonics, freq//2 - 1) + 1):
                itvs += [cos_k, sin_k]
            if freq >= 2:
                itvs.append(alter)          # Nyquist, part of the package
```

Threaded through `ModelSpec.seasonal` (autonomous path, `build_and_fit`) and the
`confirm_and_estimate(..., seasonal=None)` tool (guided path). Applied in
`src/art/pipeline.py` and `src/art/mcp_server.py`. The earlier `freq=2` caveat is
now **resolved**: a semi-annual seasonal series passes `seasonal=True` and gets the
alter.

## Validation

Surfaced building the drtran pass-through example (oil → Spanish CPI). WTI crude is
non-seasonal (HAC F=1.27, p=0.25); `n_harmonics=0` now gives a pure ARIMA(1,1,0),
`(1 − 0.2992·B)∇ln WTI = a` (mean 0), matching the reference univariate
(φ_X = 0.299193) and passing the formal tests. Regression tests added in
`tests/test_bug_0005_nyquist.py` (5 cases) closing the test gap that let this
through twice:
- non-seasonal monthly (`n_harmonics=0`) → **zero** seasonal deterministics (the bug);
- `seasonal=False` forces zero even with `n_harmonics>0`;
- seasonal monthly → 5 pairs + alter = 11;
- **semi-annual seasonal (freq=2, `seasonal=True`) → the alter ALONE** (the case the
  `n_harmonics>0` patch would have broken);
- quarterly seasonal → 1 pair + alter = 3.

Full ART suite: 457 passed before, unchanged after; the affected seasonal/pipeline
subset (113 tests) passes with the refactor.
