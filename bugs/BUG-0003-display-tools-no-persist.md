---
id: BUG-0003
title: Clean estimation display-tools do not persist .pre/.out (only confirm_and_estimate does, and it carries BUG-0001)
status: fixed
severity: medium
component: mcp-tools
found_in: 0.1.1
fixed_in: 0.1.2
reported: 2026-07-09
reporter: D. E. Guerrero
tags:
  - mcp-tools
  - workflow
  - persistence
references:
  - src/art/mcp_server.py:611 (model_equation_display)
  - src/art/mcp_server.py:643 (estimate_and_diagnose)
  - src/art/mcp_server.py:3544 (get_out_report)
  - src/art/mcp_server.py:915 (ar_factorization)
  - src/art/mcp_server.py:1875 (confirm_and_estimate)
  - /home/david/Dropbox/Cycles/bugs_art_fue.md (ISSUE #4)
---

## Summary

The project requires every modelling decision to have its trio of files:
`.inp` (specified) + `.out` (fue results) + `.pre` (= `.inp` with estimated
parameters, to seed the next step). Only `confirm_and_estimate` writes the trio —
but it suffers BUG-0001 (mean collapse). The "clean" estimation tools
(`model_equation_display`, `estimate_and_diagnose`, `get_out_report`), which
re-fit correctly from a well-seeded `.inp`, **only print to screen** and write no
`.pre`/`.out`. So a correctly-estimated model has no persisted artefacts.

## Impact

Models estimated via the correct (clean) path leave no `.pre`/`.out`, breaking the
seed-the-next-step workflow. The user currently runs a hand-rolled script
(`_load_fitted(inp)` → `m.write_pre` / `m.write_out`) to persist them.

## Reproduction

Estimate a well-seeded `.inp` with `estimate_and_diagnose` (or
`model_equation_display`): the fit is correct but no `.pre`/`.out` appears; only
`confirm_and_estimate` writes files, and it re-introduces the ×100 rescaling / μ=0
collapse of BUG-0001.

## Root cause

The clean display-tools do not call the persistence path (`m.write_pre` /
`m.write_out`) that `confirm_and_estimate` uses; they only render output.

## Fix

**Applied** in 0.1.2 (`src/art/mcp_server.py`).  Added a shared helper
`_persist_pre_out(m, output_path)` that writes `.pre` (=.inp with the estimated
parameters) and `.out` (ASCII results) via `m.write_pre` / `m.write_out`, and gave
`estimate_and_diagnose` an opt-in `output_path` parameter that calls it after the
fit.  The source `.inp` already holds the spec, so the clean path now yields the
full trio.  Because μ-collapse (BUG-0001) is fixed at the builder level, the
persisted model no longer carries the ×100/μ=0 degeneracy.  `output_path=""`
(default) keeps the old screen-only behaviour.

## Validation

- `estimate_and_diagnose(inp, output_path=out)` on `RIPC.1` writes `out.pre` and
  `out.out`, and the response note reports "Guardado …".
- `estimate_and_diagnose(inp)` with no `output_path` writes nothing (note absent) —
  backward compatible.
- Regression test `tests/test_bug_0003_persist_pre_out.py`; existing
  estimate/confirm mcp tests still pass.
