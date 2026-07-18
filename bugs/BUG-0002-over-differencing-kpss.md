---
id: BUG-0002
title: guided_identification over-specifies d — KPSS overrides a strong ADF rejection of the unit root
status: open
severity: medium
component: identification
found_in: 0.1.1
reported: 2026-07-09
reporter: D. E. Guerrero
tags:
  - identification
  - differencing
  - adf
  - kpss
references:
  - src/art/identification.py:290 (consensus verdict)
  - src/art/identification.py:345 (recommended_d)
  - /home/david/Dropbox/Cycles/bugs_art_fue.md (BUG #2)
---

## Summary

In `guided_identification` the recommended differencing order `d` is chosen by an
ADF+KPSS "consensus" that in practice **prioritises KPSS**: if KPSS rejects
stationarity it raises `d` until KPSS stops rejecting, even when ADF rejects the
unit root overwhelmingly at d=0. On bounded/mean-reverting climate series this
over-differences and induces spurious near-unit MA roots.

## Impact

Mis-identified models for mean-reverting series (counts, quantities), where
d=0 is correct and KPSS only reflects low-frequency persistence:

- **GEP (log):** ADF at d=0 gives t=−8.90, p=0.0000 (overwhelming rejection of a
  unit root) — yet `d=2` was recommended (double over-differencing).
- **GE days:** ADF at d=0 p=0.011 (rejects) — yet `d=1` recommended.

Over-differencing a bounded series introduces spurious MA unit roots and distorts
the whole downstream identification.

## Reproduction

Run `guided_identification` (step 2) on GEP (log-precipitation, mean-reverting)
and on GE days. Inspect the ADF statistic at d=0 versus the recommended d.

## Root cause

`recommended_d` (`src/art/identification.py:345`) and the consensus verdict
(`:290`) let KPSS escalate `d` without vetoing on a decisive ADF rejection. There
is no rule that a strong ADF rejection of the unit root should cap `d` at 0.

## Fix

When ADF rejects with margin (e.g. |t_ADF| well beyond the critical value), **do
not** escalate `d` on KPSS alone; at most flag "low-frequency persistence
(possible near-unit root) — confirm with Shin–Fuller after estimating". Never
recommend d≥1 under a strongly significant ADF, and never d=2 unless both tests
agree on the once-differenced series.

## Validation

Regression cases: GEP (log) → recommend d=0 (not 2); GE days → d=0 (not 1); a
genuine unit-root series (ADF fails to reject, KPSS rejects) → still d=1. Assert
`recommended_d` returns 0 whenever ADF p-value ≪ 0.05 at d=0.
