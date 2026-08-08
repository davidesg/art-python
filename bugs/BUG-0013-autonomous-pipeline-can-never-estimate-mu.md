---
id: BUG-0013
title: The autonomous pipeline can NEVER estimate mu — run_full builds ModelSpec without it, the policy has no mu logic, and the diagnosis approves the model anyway
status: open
severity: high
component: pipeline
found_in: 0.1.5
fixed_in:
reported: 2026-08-08
reporter: David / IPC-WTI passthrough, 8-country batch
tags:
  - pipeline
  - mu
  - drift
  - silent-failure
  - policy
references:
  - src/art/pipeline.py:643 (`ModelSpec.estimate_mu: bool = False` — the dataclass default)
  - src/art/pipeline.py:744-745 (`run_full`: `ModelSpec(...)` constructed WITHOUT `estimate_mu`)
  - src/art/policy.py (no mu logic anywhere — `decide_orders` and friends never touch it)
  - src/art/mcp_server.py (`build_model` signature: no `estimate_mu` parameter to override with)
  - bugs/BUG-0001-mu-collapse-rescale.md (also mu, but a seeding/rescaling defect; this one is that mu is never asked for)
---

## Summary

`build_model` and `batch_build` cannot produce a model with a mean. Not
"sometimes miss it" — the parameter is never requested, on any series, under
any settings:

1. `ModelSpec.estimate_mu` defaults to `False` (pipeline.py:643).
2. `run_full` constructs the spec without ever setting it (pipeline.py:744-745):
   ```python
   spec = ModelSpec(lam=lam, d=d, D=D, p=p, q=q,
                    n_harmonics=n_harmonics, interventions=list(extra_itvs))
   ```
3. `policy.py` contains no mu decision at all — there is no heuristic that
   could have set it.
4. `build_model` exposes no `estimate_mu` parameter, so the caller cannot
   override it either. Supplying confirmed `lam`/`d` (the ClaudePolicy path)
   does not help: the ModelSpec construction is shared by both paths.

The guided path is fine — `confirm_and_estimate` takes `estimate_mu` and
honours it. The defect is specific to the autonomous pipeline.

**And the diagnosis approves the result.** For IPC_FR the pipeline returned
`Diagnosis final: APROBADA ✓` on a model whose residuals have a mean of 0.11
with sigma 0.19 (n=215, t ≈ 8.5). The diagnosis checks Q, Jarque-Bera and
extreme residuals; none of them looks at whether the residual mean is zero.

## Impact

Every trending series modelled autonomously loses its drift, which then leaks
into the residuals. Price indices are the canonical case, and they are what the
tool is aimed at.

Downstream, in the transfer-function work this was found in, it is worse than a
missing parameter: in the joint model the output's mu absorbs
`gain × input drift` (verified on IPC_ES: mu falls 0.1545 → 0.1403, and
0.52 × 0.027149 = 0.0141 = the drop). With no mu in the univariate `.pre`,
that accounting has nowhere to land and the bridge into `mtram` starts from a
misspecified output.

## Reproduction

Eight monthly CPI indices, 2002-01…2019-12, n=216, from `IPC.xlsx`
(`~/Dropbox/Nivel de Precios y Energia`). Same spec everywhere:
λ=0, d=1, D=0, 5 harmonic pairs + Nyquist, AR(1).

```python
build_model(inp_path=<series>.inp, output_path=..., lam=0, d=1,
            max_rounds=1, run_meg=False)          # -> NO mu, always
confirm_and_estimate(..., lam=0, d=1, D=0, p=1, q=0,
                     n_harmonics=5, estimate_mu=True)   # -> mu below
```

| series  | mû     | s.e.   | t      | pipeline estimated mu? |
|---------|--------|--------|--------|------------------------|
| IPC_UK  | 0.1696 | 0.0142 | **11.94** | no |
| IPC_FR  | 0.1131 | 0.0140 | **8.08**  | no |
| IPC_CA  | 0.1562 | 0.0212 | **7.37**  | no |
| EMU     | 0.1319 | 0.0179 | **7.37**  | no |
| IPC_DE  | 0.1147 | 0.0176 | **6.52**  | no |
| CPI_USA | 0.1743 | 0.0322 | **5.41**  | no |
| IPC_ES  | 0.1545 | 0.0286 | **5.40**  | no |
| IPC_JP  | 0.0213 | 0.0202 | 1.05   | no |

Seven of eight are significant at any conventional level; the pipeline omits mu
in all eight.

**IPC_JP is the control that makes this precise.** Japan is the one series
where `estimate_mu=False` is the RIGHT answer — near-zero inflation over
2002-2019, t=1.05. A working policy would exclude mu there and include it in
the other seven. The pipeline gets Japan right by accident and the rest wrong,
which is exactly the signature of "no decision is being made".

Cost on IPC_FR, same spec otherwise: logL 18.13 → 50.63 (Δ = 32.5 for one
parameter), AIC −14.26 → −75.26.

## Root cause

Two independent gaps that happen to compound:

- **Nothing decides mu.** `policy.py` decides λ, d, D, harmonics, p, q and
  interventions. There is no `decide_mu`. So even a correctly-wired ModelSpec
  would have nothing to wire.
- **Nothing passes mu.** pipeline.py:744-745 omits the field, so it silently
  takes the `False` default rather than failing loudly.

The reason it was not noticed is worth recording, because it is a second
defect in the same area: **`guided_identification` Call 4 asks the mu question
on the wrong residuals.** It reports the mean of the residuals of the m00 — a
model in which mu has ALREADY been fitted — so it reads t ≈ 0 and concludes
`estimate_mu=False`. Observed on IPC_ES: `μ̄=-0.0000, SE=0.0187, t=-0.00 →
No, estimate_mu=False`, on a series whose mu is significant at t=5.40. Any
analyst following that instruction reproduces the pipeline's error by hand.

## Fix

Three pieces, and the third is the one that stops it recurring:

1. **Add a mu decision to the policy.** The test is the drift of the differenced
   series against its standard error — the quantity `guided_identification`
   Call 2 already computes and prints (`w̄ (σ_w̄)` on the figure). `|t| > 2` on
   ∇^d y(λ) is the natural rule and reproduces every row of the table above,
   Japan included.
2. **Pass it through** at pipeline.py:744-745, and expose `estimate_mu` on
   `build_model` (default −1 = let the policy decide, matching how lam/d/p/q
   already work) so a caller can override.
3. **Make the diagnosis see it.** Add the residual-mean check to `diagnose`:
   a model whose residuals have a mean significantly different from zero is not
   clean, whatever Q and JB say. Without this, the pipeline's own loop cannot
   detect the omission, which is why the FR run reported APROBADA.

Also fix the Call-4 mu question to test the drift of the differenced series,
not the mean of residuals that already contain a fitted mu.

## Validation

- Regression over the eight series above: assert mu is estimated for the seven
  with |t| > 2 and NOT for IPC_JP. That single table is both the repro and the
  test — it has a known answer on both sides of the rule.
- Assert `diagnose` returns not-clean on the pre-fix IPC_FR autonomous model
  (residual mean 0.11, sigma 0.19, n=215).
- Guard the no-drift case: a series with genuinely zero drift must not acquire a
  spurious mu, and BUG-0001's rescaling interaction must be re-checked once mu
  starts being switched on automatically — that is the other mu defect, and the
  two touch the same seed (`_mu_seed`, pipeline.py:391).
