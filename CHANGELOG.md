# Changelog — art-tseries / atsw

This monorepo ships **art-tseries** (Box-Jenkins-Treadway toolkit + MCP server, at
the repo root) and **atsw** (the umbrella meta-package, in `atsw-suite/`). See
`bugs/` for the full reports. Release tags: `art-v*` (art-tseries), `atsw-v*` (atsw).

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
