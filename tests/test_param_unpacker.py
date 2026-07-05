"""Characterization tests for parameter extraction (ART ↔ fue canonical unpacker).

Safety net for the planned §1 refactor (ART_MCP_REVIEW.md): today the four
`_extract_*` helpers in formal_tests.py each re-derive the position of a coefficient
in the flat `model.params` vector, duplicating fue's packing convention. These tests
pin the CONTRACT — every ART extractor must agree with fue's single canonical unpacker
`fue.forecast._reconstruct_params` (with the documented MA_f invertibility flip) — so the
refactor that consolidates them onto that unpacker cannot silently change behaviour.

They also regression-pin the three defects fixed in the jul-2026 session:
  - `_make_model(D=0, P>=1)` must build a FREE seasonal AR (was silently dropped).
  - the MA_f witness must be REPORTED invertible (was the non-invertible root).

Self-contained: synthetic monthly series, no external fixtures.
"""
import numpy as np
import pytest
import fue
from fue.forecast import _reconstruct_params

from art.pipeline import _make_model
from art.formal_tests import (
    _extract_ar_params,
    _extract_ma_param,
    _extract_ma_f_param,
    _extract_ar_factor_coefs,
    reformulate_stochastic,
    _check_reformulable,
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

def _syn_ts(n=180, seed=0):
    """A log-CPI-like monthly series: drift + stochastic level + seasonal + noise."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    seas = (0.30 * np.cos(2 * np.pi * t / 12) + 0.20 * np.sin(2 * np.pi * t / 12)
            + 0.10 * np.cos(2 * np.pi * 3 * t / 12)
            + 0.08 * np.sin(2 * np.pi * 5 * t / 12))
    level = 0.002 * t + 0.02 * np.cumsum(rng.standard_normal(n))
    y = 100.0 * np.exp(level + 0.01 * seas + 0.003 * rng.standard_normal(n))
    return fue.TimeSeries.from_array(y, freq=12, start=(2000, 1), name="SYN")


def _fit(model):
    model._result = None
    model.fit()
    return model


def _inv(c):
    """Invertible representation of a fixed-freq MA(2) coef (mirror cast_us [4])."""
    return 1.0 / c if c < -1.0 else c


def _free_flat(factors, free_lists):
    """Flatten a fue component (list of factors) to its free scalars, in order."""
    out = []
    for i, fac in enumerate(factors or []):
        free = free_lists[i] if free_lists and i < len(free_lists) else [True] * len(fac)
        out += [fac[j] for j in range(len(fac)) if free[j]]
    return out


# --------------------------------------------------------------------------- #
# Regular AR
# --------------------------------------------------------------------------- #

def test_extract_ar_params_matches_fue():
    ts = _syn_ts()
    m = _fit(_make_model(ts, lam=0.0, d=1, D=1, p=2, q=0, n_harmonics=0))  # regular AR(2), no harmonics
    rc = _reconstruct_params(m, m.params)
    expected = _free_flat(rc[2], m.ar_free)          # rc[2] = ar_est
    got = _extract_ar_params(m)
    assert got == pytest.approx(expected, abs=1e-12)
    assert len(got) == 2


def test_extract_ar_factor_coefs_matches_fue():
    ts = _syn_ts()
    m = _fit(_make_model(ts, lam=0.0, d=1, D=1, p=2, q=0, n_harmonics=0))
    rc = _reconstruct_params(m, m.params)
    got = _extract_ar_factor_coefs(m, 0)
    expected = tuple(_free_flat([rc[2][0]], [m.ar_free[0]]))
    assert got == pytest.approx(expected, abs=1e-12)


# --------------------------------------------------------------------------- #
# Regular MA
# --------------------------------------------------------------------------- #

def test_extract_ma_param_matches_fue():
    ts = _syn_ts()
    m = _fit(_make_model(ts, lam=0.0, d=1, D=1, p=0, q=1, n_harmonics=0))  # regular MA(1)
    rc = _reconstruct_params(m, m.params)                   # rc[4] = ma_est
    got = _extract_ma_param(m, 0)
    assert got == pytest.approx(rc[4][0][0], abs=1e-12)


# --------------------------------------------------------------------------- #
# Fixed-frequency MA_f witness — invertibility flip contract
# --------------------------------------------------------------------------- #

def _reformulated_witness_model(freq=3):
    ts = _syn_ts()
    base = _fit(_make_model(ts, lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=6))
    mS = reformulate_stochastic(base, freq=freq, s=12, with_witness=True)
    return _fit(mS)


def test_fit_normalizes_ma_f_to_invertible():
    """§C: fue.Model.fit stores the MA_f witness in the INVERTIBLE root (|·| ≤ 1),
    so the reflection lives in one place (fue) — ART reads it without a flip."""
    m = _reformulated_witness_model(freq=3)
    rc = _reconstruct_params(m, m.params)          # rc[7] = ma_f_coefs, already invertible
    free_idx = [i for i, ff in enumerate(m.ma_f) if ff.free]
    assert free_idx, "expected a free MA_f witness"
    i = free_idx[0]
    assert abs(rc[7][i]) <= 1.0 + 1e-9, "fit must store the invertible MA_f root"
    got = _extract_ma_f_param(m, i)
    assert got == pytest.approx(rc[7][i], abs=1e-12)   # ART reads it straight, no flip
    assert got == pytest.approx(_inv(rc[7][i]), abs=1e-12)  # flip is a no-op now
    assert abs(got) <= 1.0 + 1e-9


# --------------------------------------------------------------------------- #
# Regression pins — the jul-2026 session bugs
# --------------------------------------------------------------------------- #

def test_make_model_d0_builds_free_seasonal_ar():
    """D=0 with P>=1 must build a FREE seasonal AR (was silently dropped)."""
    ts = _syn_ts()
    m = _make_model(ts, lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=6, P=1)
    assert m.ar_s and len(m.ar_s) == 1, "seasonal AR not built under D=0"
    assert m.ar_s_free and m.ar_s_free[0] == [True], "seasonal AR must be free"
    # YW-initialised (not the old constant 0.0): a stationary start in (-1, 1).
    assert -1.0 < float(m.ar_s[0][0]) < 1.0


def test_make_model_d0_pure_harmonics_has_no_seasonal_ar():
    """Guard the other direction: P=0 keeps ar_s empty (no behaviour change)."""
    ts = _syn_ts()
    m = _make_model(ts, lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=6, P=0)
    assert not m.ar_s


def test_model_equation_reads_coefs_from_canonical_component():
    """§1-remaining: model_equation must source each coef from its named component,
    not a global positional cursor. Regression for the AR_f-before-MA desync: the flat
    vector packs (…MA, MA_s, AR_f, MA_f…) but the display renders AR_f before MA, so the
    old cursor read AR_f's value from MA's slot (and vice-versa)."""
    import fue
    from fue.model import Model, FixedFreqFactor
    from art.describe import model_equation
    ts = _syn_ts(n=160, seed=1)
    m = _fit(Model(ts, d=1, D=0,
                   ar_f=[FixedFreqFactor(freq=3.0, coef=-0.5, free=True)],
                   ma=[[-0.3]], ma_free=[[True]]))
    rc = _reconstruct_params(m, m.params)
    ar_f_s = f"{abs(rc[6][0]):.4f}"       # AR_f magnitude, rendered on the LHS (AR side)
    ma_s   = f"{abs(rc[4][0][0]):.4f}"    # MA magnitude, rendered on the RHS (MA side)
    eq = model_equation(ts, m)
    assert ar_f_s in eq and ma_s in eq and ar_f_s != ma_s
    # AR_f block precedes the MA block; under the old cursor the values were swapped.
    assert eq.index(ar_f_s) < eq.index(ma_s)


# --------------------------------------------------------------------------- #
# Baseline guards (§3) — reformulation/MEG entry points
# --------------------------------------------------------------------------- #

def _harmonic_baseline(n_harmonics=6):
    ts = _syn_ts()
    return _fit(_make_model(ts, lam=0.0, d=1, D=0, p=0, q=0,
                            n_harmonics=n_harmonics, estimate_mu=True))


def test_guard_rejects_out_of_range_freq():
    m = _harmonic_baseline()
    with pytest.raises(ValueError, match="out of range"):
        _check_reformulable(m, 7, 12)
    with pytest.raises(ValueError):
        _check_reformulable(m, 0, 12)


def test_guard_rejects_already_stochastic():
    m = _harmonic_baseline()
    m.ifadf = list(m.ifadf or [0] * 7)
    m.ifadf[5] = 1
    with pytest.raises(ValueError, match="already stochastic"):
        _check_reformulable(m, 5, 12)


def test_guard_rejects_freq_without_harmonic():
    m = _harmonic_baseline(n_harmonics=2)   # only f=1,2 (+ alter at Nyquist f=6)
    with pytest.raises(ValueError, match="no cos/sin"):
        _check_reformulable(m, 3, 12)


def test_guard_passes_valid_baseline():
    m = _harmonic_baseline()
    _check_reformulable(m, 5, 12)   # interior f=5: cos/sin present, deterministic
    _check_reformulable(m, 6, 12)   # Nyquist: alter present
