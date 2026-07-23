# Changelog — art-tseries / atsw

This monorepo ships **art-tseries** (Box-Jenkins-Treadway toolkit + MCP server, at
the repo root) and **atsw** (the umbrella meta-package, in `atsw-suite/`). See
`bugs/` for the full reports. Release tags: `art-v*` (art-tseries), `atsw-v*` (atsw).

## atsw 1.0.4 — 2026-07-23

- Pins bumped to **fue>=0.1.8** and **art-tseries>=0.1.3** so `pip install atsw`
  pulls the rescaling/forecast fixes and the naming/language pass.
- Description reworked: **"A Time Series Workshop"** — the fue + pyfug + ART suite,
  with the MCP server surfaced for discoverability.

## art-tseries 0.1.3 — 2026-07-23

Requires **fue>=0.1.8**. Rescaling made a single source of truth, seasonal-seed fix,
and a naming/language pass for the (English-majority) audience.

- **Rescaling P1 — `refactor` as single source of truth**
  (`docs/RESCALING_ARCHITECTURE.md`). No file/function hardcodes `100`: `_make_model`
  sets `model.refactor`; `_mu_seed(refactor)` seeds on the already-rescaled series;
  `_build_arma_on_model` forwards the base refactor; `_write_inp` writes
  `model.refactor`. Invariant `in-memory forecast == .pre round-trip forecast` now
  holds (`tests/test_rescaling_invariant.py`).
- **BUG-0006** (seed): the seasonal-AR seed was Yule-Walker'd on the
  harmonic-*containing* differenced series (positive `r(12)`), giving a positive Φ
  seed against the noise's negative Φ → spurious optimum for the US AR(2)×AR(2). Now
  the deterministic harmonics (+ Nyquist alter) are regressed out first; the seed is
  taken on the residual noise. Removes the per-country seed workaround.
- **BUG-0005** (seasonal package): the deterministic seasonal block (harmonic pairs +
  Nyquist alter) is now gated on a `seasonal` flag instead of `n_harmonics>0`, so
  low-frequency seasonal models are handled correctly.
- **Naming:** ART is now glossed **"A Real-Time Time-Series Analysis"** (Box-Jenkins-
  Treadway methodology retained in the description/README body). No package, module,
  or repo rename.
- **Seasonality routes** renamed from the school labels to the working hypothesis:
  **B1 — Deterministic seasonality** (D=0, harmonics), **B2 — Stochastic seasonality**
  (D=1, seasonal differencing).
- **Language:** the MCP server now instructs the assistant to **always respond in the
  user's language** (default English); user-facing route labels are in English.

## art-tseries 0.1.2 — 2026-07-19

Requires **fue>=0.1.7**. Fixes found reviewing the *Joseph's Cycles* models
(`Cycles/bugs_art_fue.md`); an in-repo bug tracker (`art.bugs` + `art-bug`) was
added, mirroring fue's.

- **BUG-0001** (inp-builder): an untransformed series fit with AR(p)+mean came back
  with μ≈0 and a spurious near-unit AR root absorbing the level, because the `.inp`
  hard-coded a ×100 rescaling while μ was seeded at 0. Added `_mu_seed()` =
  `refactor·mean(∇^d∇_s^D BoxCox_λ(y))` and pass it from `_make_model` /
  `_build_arma_on_model`. Validated: GE (λ=1) μ=126.15, GEP (λ=0) μ=6.7555.
- **BUG-0002** (identification): `recommended_d` required the strict consensus
  (ADF rejects AND KPSS doesn't), so a KPSS rejection over-differenced even when
  ADF rejected the unit root decisively. Now ADF governs: smallest d where ADF
  rejects. GEP d2→0, GE d1→0.
- **BUG-0003** (mcp-tools): `estimate_and_diagnose` gained an opt-in `output_path`
  that persists the `.pre`/`.out` trio via `_persist_pre_out` (previously only
  `confirm_and_estimate`, which carried BUG-0001).
- **BUG-0004** (roots): delta-method SEs for a complex AR(2) factor's damping and
  period in `ar_factorization` (ported from `caracterizar_operadores.car_ar2`,
  matching ABTreadway-Dperar2.xls). `d ± SE`, `per ± SE` when the 2×2 coefficient
  covariance is available.

## atsw 1.0.3 — 2026-07-19

- Floor the suite to the fixed engine/toolkit: `fue>=0.1.7`, `art-tseries>=0.1.2`
  (keeps `pyfug>=2.0`).

## Infrastructure — 2026-07-19

- Both packages now publish to PyPI via **trusted publishing** (OIDC) from GitHub
  Actions: `publish-art.yml` (tag `art-v*`) and `publish-atsw.yml` (tag `atsw-v*`).
  Build-only in the publish job (no install-smoke-test — a suite dependency may be
  unpublished at coordinated-release time).
