---
id: BUG-0007
title: update_and_forecast rebuilds the model without refactor: mu is read 100x off scale and the forecast level explodes
status: fixed
severity: high
component: mcp-tools
found_in: 0.1.3
fixed_in: 0.1.3
reported: 2026-07-23
reporter: David / SF_MEG FR_CPI
tags:
  - forecast
  - fuf
  - rescaling
  - explosion
references:
  - src/art/mcp_server.py:3196-3212 (update_and_forecast -> _fue.Model(...) without refactor)
  - fue src/fue/model.py (Model.__init__ default refactor=1.0)
  - fue BUG-0004 (same user-visible signature: mis-scaled mu0 -> runaway level)
  - bugs/BUG-0007-repro/ (FR_CPI.fuf.inp + repro.py: self-contained reproduction)
---

## Summary

`update_and_forecast` appends the new observations and then **rebuilds the model from
scratch** with `_fue.Model(ts_new, ar=…, ma=…, …, mu=m_old.mu0, boxlam=m_old.boxlam)`.
The field list omits **`refactor`**, whose default in `fue.Model.__init__` is `1.0`,
while every model coming out of a fuf file carries `refactor = 100.0` (ART's ×100
conditioning). The mean `mu0` is stored in the rescaled space, so the rebuilt model
reads it as if it were 100× larger in the level recursion: **the forecast level runs
away**. FR_CPI (index ≈ 107) forecasts `78.57` at h=1 and `1031.97` at h=24 (+122%
year-on-year). No warning is emitted — the tracking table above it is correct, which
makes the output look trustworthy.

## Impact

Silent and catastrophic for the *forecast → append actuals → re-forecast* loop, i.e.
the whole point of the fuf flow (`sps_dashboard`, any recurring monitoring built on
`update_and_forecast`).

Scope is sharp: **only models with a mean**. With `mu0 = 0` there is no drift term to
mis-scale and the forecast is correct — which is why it can hide for a long time. In
the SF_MEG FR_CPI case the two models carrying μ (the deterministic baseline D,
μ=0.1055; the HSM, μ=0.7843) both exploded, while the airline SARIMA (μ=0, no mean)
came out perfect at the same origin, on the same call sequence.

Not hit by `generate_forecast` (it forecasts from the loaded/fitted model without
rebuilding) nor by code that swaps the series in place on an already-built model
(`model.series = fue.TimeSeries.from_array(...)`, as `sps/forecast_compare.py` does) —
both preserve `refactor`.

## Reproduction

Self-contained in `bugs/BUG-0007-repro/` (`FR_CPI.fuf.inp` + `repro.py`), which rebuilds
the model exactly as `update_and_forecast` does, with and without `refactor`:

```
python repro.py

Model.__init__ refactor default = 1.0
fuf model: refactor = 100.0   mu0 = 0.105514

  as update_and_forecast does (no refactor)  refactor=  1.0 -> h=1    78.57  h=12   303.09  h=24  1031.97
  + refactor=m_old.refactor                  refactor=100.0 -> h=1   106.73  h=12   108.69  h=24   110.13
  actual                                                     -> h=1   107.30  h=12   113.42  h=24   117.50
```

Through the MCP tool the same thing looks like this (FR_CPI, origin 12/2021, 24 actuals
appended to a horizon-24 fuf written at 12/2019):

| # | Fecha | Previsión | Δ% interanual |
|---|-------|-----------|---------------|
| 1 | 01/2022 | 78.5712 | −28.27% |
| 12 | 12/2022 | 303.0894 | +104.09% |
| 24 | 12/2023 | 1031.9679 | +122.52% |

## Root cause

`src/art/mcp_server.py:3196`, in `update_and_forecast`:

```python
m_new = _fue.Model(
    ts_new,
    ar=m_old.ar, ar_free=m_old.ar_free,
    …
    mu=m_old.mu0, estimate_mu=m_old.estimate_mu,
    boxlam=m_old.boxlam,
)                      # <- refactor not passed; defaults to 1.0
```

`mu0` is expressed in the ×100 rescaled space that `refactor=100.0` defines. Rebuilding
with `refactor=1.0` keeps the number and changes its meaning — the same class of defect
as fue BUG-0004 (there the stale seed carried the ×100 μ into a `refactor=1` model;
here a correct μ is dropped into a `refactor=1` rebuild). Hand-copying a field list is
the underlying fragility: any attribute added to `fue.Model` is silently lost here.

## Fix

Minimal: pass it through.

```python
    boxlam=m_old.boxlam, refactor=m_old.refactor,
```

Better (removes the whole class of bug): stop rebuilding. Deep-copy `m_old` and replace
the series, which is what preserves every attribute by construction:

```python
m_new = copy.deepcopy(m_old)
m_new.series = ts_new
```

## Validation

- `bugs/BUG-0007-repro/repro.py` must print the same level for both constructions.
- Regression test: build any fuf with `mu != 0` and `refactor=100`, append observations,
  and assert the updated h=1 forecast stays within a few % of the last observation
  (the explosion is orders of magnitude, so the bound can be loose).
- Cross-check against the series-swap path (`model.series = …`), which is unaffected and
  gives 106.73 / 108.69 / 110.13 for the repro case.
