---
id: BUG-0002
title: guided_identification over-specifies d — KPSS overrides a strong ADF rejection of the unit root
status: fixed
severity: medium
component: identification
found_in: 0.1.1
fixed_in: 0.1.2
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

**Applied** in 0.1.2 (`src/art/identification.py`, `recommended_d`).  ADF directly
tests the unit root, so its rejection is decisive evidence that a (further)
difference is not needed.  `recommended_d` now picks the **smallest d at which ADF
rejects, regardless of KPSS**; only if ADF never rejects does it fall back to the
strict consensus verdict `'stationary'`, then to the last d tested.  This never
recommends d≥1 while ADF is significant at a lower d, and reaches d=2 only when ADF
fails to reject at both d=0 and d=1.  (The recommendation is a starting value; the
formal test on the estimated model is Shin-Fuller.)

## Validation

Real series, `unit_root_tests` + `recommended_d`:
- **GEP (log):** ADF p=0.0000 at d=0 (KPSS also rejects) → **d=0** (was 2).
- **GE days:** ADF p=0.011 at d=0 (KPSS also rejects) → **d=0** (was 1).

Regression test `tests/test_bug_0002_over_differencing.py`: decisive ADF rejection
with KPSS also rejecting → d=0; marginal ADF rejection (p≈0.011) → d=0; genuine
unit root (ADF fails at d=0, rejects at d=1) → d=1; I(2) only when ADF fails at
both d=0 and d=1; empty → 0.  Existing unit-root/identification/policy suite: 61
passed.
