"""
Regression test for BUG-0001 — mean collapse under ×100 rescaling + μ=0 seed.

A high-level untransformed series fit with AR(p)+mean used to come back with
μ ≈ 0 and a spurious near-unit AR root that absorbed the level, because the
`.inp` was written with a ×100 rescaling factor while μ was seeded at 0 (far from
the rescaled level).  The fix seeds μ at ``refactor · mean(transformed,
differenced series)`` in `_make_model` / `_build_arma_on_model`.

See bugs/BUG-0001-mu-collapse-rescale.md.
"""

import os
import tempfile

import numpy as np
import pytest

import fue
from art.pipeline import (_make_model, _write_inp, _load_fitted,
                          _mu_seed, _RESCALE_FACTOR)


def _high_mean_series(mean=126.0, phi=0.4, n=240, sd=15.0, seed=0):
    """A stationary AR(1) around a high, non-zero level (like the Geneva
    precipitation-days series that triggered the bug)."""
    rng = np.random.default_rng(seed)
    a = rng.normal(0, sd, n)
    y = np.empty(n)
    y[0] = mean
    for t in range(1, n):
        y[t] = mean + phi * (y[t - 1] - mean) + a[t]
    return fue.TimeSeries(np.abs(y), freq=1, start=(1, 1768), name="HM")


def _fit_or_skip(ts, **kw):
    m = _make_model(ts, **kw)
    tmp = tempfile.mktemp(suffix=".inp")
    _write_inp(ts, m, tmp)
    try:
        _, mf = _load_fitted(tmp)
    except Exception as exc:                     # engine unavailable / non-conv
        pytest.skip(f"fit unavailable: {exc}")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return mf


def test_mu_seed_is_rescaled_transformed_mean():
    ts = _high_mean_series(mean=126.0)
    data = np.asarray(ts.data, float)
    # λ=1, d=0 → level mean × refactor (the scale fue estimates μ in)
    assert _mu_seed(ts, 1.0, 0, 0, True) == pytest.approx(
        _RESCALE_FACTOR * data.mean(), rel=1e-9)
    # λ=0 (log), d=0 → log-mean × refactor
    assert _mu_seed(ts, 0.0, 0, 0, True) == pytest.approx(
        _RESCALE_FACTOR * np.log(data).mean(), rel=1e-9)
    # not estimated → 0; d≥1 → ~0 drift
    assert _mu_seed(ts, 1.0, 0, 0, False) == 0.0
    assert abs(_mu_seed(ts, 1.0, 1, 0, True)) < _RESCALE_FACTOR * 5.0


def test_mean_does_not_collapse_untransformed():
    # AR(2)+mean on an untransformed high-level series: μ must land near the
    # sample mean (not ≈0) and the AR must NOT grow a near-unit root (Σφ ≈ 1).
    ts = _high_mean_series(mean=126.0)
    mf = _fit_or_skip(ts, lam=1.0, d=0, D=0, p=2, q=0,
                      n_harmonics=0, estimate_mu=True)
    data = np.asarray(ts.data, float)
    mu_orig = mf._result.params[-1] / _RESCALE_FACTOR
    assert mu_orig == pytest.approx(data.mean(), rel=0.05)   # near mean, not ~0
    phi = mf.ar[0]
    assert abs(sum(phi)) < 0.9      # no spurious near-unit AR root
