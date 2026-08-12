---
id: BUG-0014
title: The .pre contract is not honoured when adding ARMA — base_pre_path is unreachable from the instructions, and mu is discarded even when it is used
status: fixed
severity: high
component: pipeline
found_in: 0.1.5
fixed_in: 0.1.11 (unreleased)
reported: 2026-08-08
reporter: David / passthrough IPC_ES
tags:
  - pre-contract
  - pipeline
  - mu
  - ladder
references:
  - src/art/pipeline.py:423-480 (_build_arma_on_model)
  - src/art/pipeline.py:391-420 (_mu_seed)
  - src/art/mcp_server.py (confirm_and_estimate, base_pre_path)
  - drtran-python/docs/LADDER_AS_OPTIMISATION.md (the .inp/.out/.pre convention)
  - BUG-0013 (the autonomous pipeline can never estimate mu — compounds this)
---

## Summary

The ladder convention is that each rung's output is the next rung's input: a
`.pre` is an `.inp` with the estimates as new initial values, and the next
iteration starts from it. In art's own flow the deterministic model (harmonics,
plus mu if added) is estimated first and *then* ARMA structure is added. That
second step is supposed to start from the first one's `.pre`.

It does not, on two independent counts.

### (a) `base_pre_path` is unreachable in practice

`confirm_and_estimate(base_pre_path=…)` exists and does the right thing.
`pipeline.py:430` states its purpose exactly:

> *"Used by confirm_and_estimate(base_pre_path=...) to add ARMA to a model that
> already has its outlier interventions estimated."*

But `_INSTRUCTIONS` — what Claude actually reads — mentions `base_pre_path`
**zero times**. The guided protocol tells Claude to estimate the reference model
(`<serie>_ref.inp`) and then to estimate the chosen ARMA model, and never says
to chain the second to the first. So the capability is present and the routing
is absent, and in practice the ARMA model is rebuilt from the raw `.inp`.

This is the same shape as the AR(1)/MA(1) tie-break (fixed 2026-08-08) and
BUG-0004 in drtran: the mechanism is there, nothing sends anyone to it.

### (b) Even when it IS used, mu is discarded

`_build_arma_on_model` inherits the deterministic estimates and re-derives the
mean, inside the same constructor:

```python
interventions=list(m_base.interventions or []),        # inherited
mu=_mu_seed(m_base.series, m_base.boxlam, m_base.d,    # RE-DERIVED
            m_base.D, estimate_mu, m_base.refactor),
```

Measured on `IPC_ES_m10` fitted with `estimate_mu=True` (base mu = 0.154475):

| call | mu inherited | = base? | deterministics | = base? |
|---|---|---|---|---|
| `_build_arma_on_model(p=1, estimate_mu=False)` | **0.000000** | no | −0.1610, −0.1663, 0.2893 | **yes** |
| `_build_arma_on_model(p=1, estimate_mu=True)`  | **0.160088** | no | −0.1610, −0.1663, 0.2893 | **yes** |

With `estimate_mu=False` the estimated drift is not merely re-seeded, it is
**thrown away**: 0.154475 → 0. With `estimate_mu=True` it is re-derived from the
series (0.160088) instead of carried (0.154475).

One class of estimate is inherited and the other is not, in the same function.
Whatever the intent, that is not the `.pre` contract.

## Resolution (2026-08-12)

Both counts, together with BUG-0013 as this report required.

**(b) mu is carried.** `_build_arma_on_model`'s `estimate_mu` is now three-state:
`None` (the default) inherits the base's `estimate_mu` AND its estimated `mu0`;
`True`/`False` force the choice, with `_mu_seed` used only when a base with no
mean is asked for one. Measured on the reported case `ES_CPI_m10.pre`
(base `mu0 = 0.154472`, `estimate_mu=True`, 11 deterministics):

| call | mu | = base? | deterministics |
|---|---|---|---|
| `_build_arma_on_model(p=1)` (inherits) | **0.154472** | **yes** | 11, identical |
| `_build_arma_on_model(p=1, estimate_mu=True)` | **0.154472** | **yes** | 11, identical |
| `_build_arma_on_model(p=1, estimate_mu=False)` | 0.000000 | forced off | 11, identical |

Previously the first row gave 0.000000 (discarded) and the second 0.160085
(re-derived). The asymmetry this report identified — one class of estimate
inherited, the other not, in the same constructor — is gone.

**(a) It is now routed.** `base_pre_path` went from **0 mentions in
`_INSTRUCTIONS` to 4**. Stage 2 of the guided protocol now states that the ARMA
step chains from the reference model's `.pre`, and says why: a `.pre` is an
optimum in re-runnable form, so chaining inherits harmonics, interventions and
the mean instead of re-solving them. Call 4's suggested invocation passed the
`.pre` as `inp_path`, which is `confirm_and_estimate`'s *fresh* mode and
rebuilds from scratch; it now passes `base_pre_path` as well.

Tests: `tests/test_bug_0013_mu_inheritance.py` — `_build_arma_on_model(m,…).mu0
== m.mu0` for a base fitted with a free mean, that a base without one does not
acquire one, and that the explicit argument still overrides in both directions.
The report notes none of these existed; each fails against the pre-fix code.

## Impact

High, and it compounds with BUG-0013. The autonomous pipeline never sets
`estimate_mu` at all, so every ARMA iteration of a trending series starts from
mu = 0 and the drift leaks into the residuals. Price indices are the canonical
case and the target of the tool.

Downstream in `mtram` it is worse than a lost parameter: in the joint model the
output's mu absorbs `gain × input drift` (verified on IPC_ES: mu falls
0.1545 → 0.1403, and 0.52 × 0.027149 = 0.0141 = the drop). With no mu in the
univariate `.pre`, that accounting has nowhere to land.

## Reproduction

```python
import fue
from art.pipeline import _build_arma_on_model
ts, m = fue.load('IPC_ES_m10.pre')
m.estimate_mu = True; m.fit()
print(m.mu0)                                            # 0.154475
print(_build_arma_on_model(m, p=1, q=0).mu0)            # 0.000000  <-- discarded
print(_build_arma_on_model(m, p=1, q=0,
                           estimate_mu=True).mu0)       # 0.160088  <-- re-derived
```

## Fix

Two, independent:

1. **Route to it.** Say in the instructions that the ARMA step chains from the
   reference model's `.pre` via `base_pre_path`. That is a documentation change
   and it is what makes the existing machinery reachable.
2. **Carry mu like everything else.** `_build_arma_on_model` should inherit
   `m_base.mu0` and `m_base.estimate_mu` when the base has them, and fall back
   to `_mu_seed` only when the base carries no mean. Re-deriving a parameter
   that was already estimated is precisely what the `.pre` convention exists to
   avoid.

Neither is safe to apply while BUG-0013 stands: with the autonomous pipeline
unable to set `estimate_mu`, fixing (2) alone changes nothing for it, and fixing
(1) alone would chain a `.pre` that has no mean in it. The three want doing
together.

## Validation

Assert that `_build_arma_on_model(m, …).mu0 == m.mu0` whenever `m` was fitted
with a free mean, and that a guided run which estimates the reference model and
then adds ARMA reaches the same mu as a direct fit. Neither test exists today.
