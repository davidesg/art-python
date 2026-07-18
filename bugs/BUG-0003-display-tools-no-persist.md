---
id: BUG-0003
title: Clean estimation display-tools do not persist .pre/.out (only confirm_and_estimate does, and it carries BUG-0001)
status: open
severity: medium
component: mcp-tools
found_in: 0.1.1
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

Give `estimate_and_diagnose` (and optionally `model_equation_display`) an
`output_path`/flag to write `.pre` and `.out` exactly like `confirm_and_estimate`
(`m.write_pre` / `m.write_out`), **without** the ×100 rescaling or μ=0 seeding
(see BUG-0001). Then the clean path yields the full trio directly.

## Validation

After the fix, `estimate_and_diagnose(inp, output_path=...)` on a hand-seeded GE/GEP
`.inp` writes `.pre`+`.out` whose logℓ matches the screen output and the
hand-rolled `_load_fitted` artefacts.
