---
id: BUG-0012
title: ifadf differencing factors are rendered OUTSIDE the μ parenthesis, so the printed equation is not the model that was fitted
status: open
severity: medium
component: describe/equation
found_in: 0.1.5
fixed_in:
reported: 2026-08-08
reporter: David / IPC_ES passthrough
tags:
  - equation
  - display
  - ifadf
  - meg
  - mu
references:
  - src/art/describe.py:999-1000 (`_add_ifadf_blocks(left_blocks, model.ifadf)` — appended to the AR block list)
  - src/art/describe.py:971-992 (`_add_ifadf_blocks`: docstring itself calls them "individual factors of ∇_freq")
  - src/art/describe.py:1021-1033 (the comment stating the invariant this breaks, and `nt_label` construction)
  - src/art/describe.py:741-751 (`_diff_str`: builds ∇ and ∇_s only — ifadf factors never reach it)
---

## Summary

When a seasonal unit root is active (`ifadf[f]=1`, the model `meg_reformulate`
builds), the equation renderer prints the differencing factor **outside** the
parenthesis that carries μ:

```
  (2)  (1 − 0.4074·B) (1 + B + B²)_f=4 (∇Nₜ − 0.4642) = (1 + B + 0.9678·B²)_f=4 aₜ
```

Read literally that is `A_f(B)·(∇Nₜ − μ)`, whose mean is `A_f(1)·(m − μ)`. With
m = 0.1545 and μ̂ = 0.4642 that is `3 × (−0.3097) = −0.929 ≠ 0` — the printed
equation is not mean-zero, so it is not the model that was fitted.

The fitted model is `(A_f(B)∇Nₜ − μ)`: μ is the mean of the **fully differenced**
variable, and `ifadf` is part of the differencing. Its mean is
`A_f(1)·m − μ = 0.4635 − 0.4642 ≈ 0`. Correct form:

```
  (2)  (1 − 0.4074·B) ((1 + B + B²)_f=4 ∇Nₜ − 0.4642) = (1 + B + 0.9678·B²)_f=4 aₜ
```

**The estimation is correct.** This is a rendering defect only.

## Impact

The printed equation is the artifact the analyst reads, quotes and carries into
a report — and `confirm_and_estimate` instructs Claude to show the block
VERBATIM, so nothing downstream corrects it. Two concrete harms:

1. **μ is misread as a drift.** In the f=4 model above, μ̂ = 0.4642 %/month reads
   as 5.6 %/year for a series whose actual drift is 1.86 %/year. The parenthesis
   placement is what invites the misreading: with μ next to ∇Nₜ it looks like
   the mean of ∇Nₜ, which is 0.1545.
2. **It cost a false bug report.** Working this case, the assistant measured the
   μ scaling across three frequencies, concluded the mean was handled
   inconsistently between the regular AR factor and the seasonal one, and was
   about to file it. David caught it: μ is the mean of the differenced variable
   and `ifadf` IS differencing, so the scaling is the definition working. The
   rendering is what made the correct behaviour look like a defect.

Only affects models with `ifadf` active — i.e. every model reached through
`meg_reformulate` / the MEG stochastic-seasonality route.

## Reproduction

Series: IPC_ES (INE, 2002-01…2019-12, n=216), λ=0, d=1, 5 harmonic pairs +
Nyquist, AR(1), μ estimated. Baseline `IPC_ES_m10.pre`: φ=0.4027, μ=0.1545
(sample mean of ∇ln·100 = 0.1601).

```python
meg_reformulate(inp_path=<m10.pre>, base_pre_path=<m10.pre>,
                freq=f, output_path=..., with_witness=True)
```

The interior-frequency operator is `1 − 2cos(ω_f)B + B²` with ω_f = 2πf/s, so
its gain at B=1 is `A_f(1) = 2 − 2cos(ω_f)`. μ̂ tracks it exactly:

| f | ω_f  | A_f(1) | predicted μ = A_f(1)·0.1545 | observed μ̂ |
|---|------|--------|------------------------------|-------------|
| 2 | π/3  | 1      | 0.1545                       | 0.1544      |
| 3 | π/2  | 2      | 0.3090                       | 0.3104      |
| 4 | 2π/3 | 3      | 0.4635                       | 0.4642      |

Three different gains, three matches (worst error 0.45 %, from φ and the
harmonics re-estimating slightly in each fit). Implied drift is invariant:
0.4642/3 = 0.1547.

The rendered equation is wrong in all three; only the f=2 case (gain 1) happens
to look right, because there `A_f(1)·(m−μ) = (m−μ)` and μ̂ = m coincidentally
makes both readings agree. **f=2 is therefore useless as a test case** — use
f=3 or f=4.

## Root cause

`describe.py:999-1000` appends the ifadf factors to `left_blocks`:

```python
if getattr(model, "ifadf", None):
    _add_ifadf_blocks(left_blocks, model.ifadf)
```

`left_blocks` is the AR block list, emitted at 1044-1045 *before* `nt_label`,
i.e. outside the parenthesis. But `_add_ifadf_blocks` is documented (971-972)
as *"Add fixed individual factors of **∇_freq** (ifadf)"* — the code names them
as differencing and then places them where AR factors go.

The invariant is stated explicitly twelve lines below, at 1021-1023:

```python
# ∇ is placed INSIDE the Nₜ term so that μ is the mean of the
# differenced process (∇Nₜ), not of the non-stationary level Nₜ.
# Correct form: (1−φB)(∇Nₜ − μ) = aₜ
```

That is exactly right, and exactly what the ifadf path violates. The reason it
was missed is that `_diff_str()` (741-751) — which builds the string that goes
inside the parenthesis — only knows about `d` and `D`. The per-frequency
factors of ∇_s never reach it.

Note the two are mutually exclusive in practice: `ifadf` decomposes ∇_s into
individual frequency factors, so a model has either `D=1` (whole ∇_s, handled
correctly) or `ifadf` flags (handled incorrectly). That is why the defect
survived: the D=1 route it was written for is fine.

## Fix

Move the ifadf factors inside the μ parenthesis, alongside ∇ and ∇_s. The
smallest change that respects the existing structure is to build them into the
`nt_core` string rather than into `left_blocks` — i.e. have `_add_ifadf_blocks`
(or a string-returning sibling) feed `_diff_str()`'s output at 1018/1024:

```python
nt_core = f"{diff_s}{ifadf_s}Nₜ" if (diff_s or ifadf_s) else "Nₜ"
```

with `ifadf_s` the concatenated factor strings. Then `nt_label` at 1026 wraps
the whole differenced variable, and 1028-1033 still work for the no-μ case.

Two details to preserve:
- ifadf factors carry no SE (they are fixed), so the `nt_se` padding logic at
  1037-1042 is unaffected — it keys off `mu_pfx_len`, which grows with the
  longer prefix and must be recomputed from the new `nt_core`.
- the LINE_WRAP=72 path (1049-1092) measures `lhs_items`; moving several
  factors from `left_blocks` into a single `nt_label` makes one item much wider,
  so the `separate_lhs` branch will trigger more often. Check the wrapped
  output, not just the single-line case.

Leave the ordering `∇ ∇_s <ifadf factors>` so it reads outermost-first, matching
how the operators compose.

## Validation

- Regression on the three IPC_ES models above: assert the rendered LHS contains
  `((1 + B + B²)_f=4 ∇Nₜ − 0.4642)` and not `(1 + B + B²)_f=4 (∇Nₜ − 0.4642)`.
- **Mean-zero invariant as a test, not an eyeball**: parse the rendered
  equation, evaluate every LHS operator at B=1, and assert the implied mean of
  the printed expression is ~0. This catches the whole class, not just ifadf.
- Cover the Nyquist case (`ifadf[s/2]`, factor `1 + B`, gain 2) and the f=0 case
  (`ifadf[0]`, factor `1 − B`, gain 0 — μ is not identified there; check what
  the fitter does before asserting anything about the display).
- Guard the `D=1` and plain-`d` paths against regression: they are currently
  correct and the fix touches the string they share.
