"""Rescaling architecture invariant (docs/RESCALING_ARCHITECTURE.md).

The single-source-of-truth `refactor` must make the in-memory model self-consistent:
`build → fit → forecast` (in memory) must equal
`build → fit → write .pre → load → forecast` (round-trip). This fails when the ×100
rescale is decoupled from `model.refactor` (the mu0 seed in a different scale than the
model), and holds once `_make_model` sets `refactor`, `_mu_seed` derives from it, `fit()`
syncs the estimate into the attributes, and `_write_inp` writes `model.refactor`.
"""
import os
import tempfile
import numpy as np
import fue
from art.pipeline import _make_model, _write_inp


def _ea_series():
    """A euro-area-HICP-like monthly log-level: seasonal + AR + small drift."""
    rng = np.random.default_rng(4)
    n = 240
    t = np.arange(n)
    seas = 0.3 * np.cos(2 * np.pi * t / 12) + 0.2 * np.sin(2 * np.pi * 2 * t / 12)
    a = rng.normal(0.0, 0.02, n)
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.3 * e[i - 1] + a[i]
    w = 0.0018 + 0.01 * seas + e            # ∇log space, small positive drift
    return np.exp(np.cumsum(w) + 4.6)


def test_make_model_sets_refactor_consistently():
    ts = fue.TimeSeries(data=_ea_series().tolist(), freq=12, start=[2002, 1], name="EA")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=5, estimate_mu=True)
    # the in-memory model declares the rescale it was seeded in
    assert m.refactor == 100.0
    # the mu seed lives in that same (×100) space
    assert abs(m.mu0) > 0.01          # ×100 of a ~0.0018 drift, not the raw ~0.0018


def test_in_memory_forecast_equals_pre_round_trip():
    ts = fue.TimeSeries(data=_ea_series().tolist(), freq=12, start=[2002, 1], name="EA")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=5, estimate_mu=True)
    m.fit()

    # after fit the attributes ARE the fit (P4), in the model's scale
    assert abs(m.mu0) > 0.01          # ×100 fitted drift, not a stale raw seed

    fc_mem = np.asarray(m.forecast_fuf(6).level[:6], float)

    tmp = tempfile.mktemp(suffix=".inp")
    try:
        _write_inp(ts, m, tmp)
        loaded = fue.inp.load(tmp)
        m2 = loaded[1] if isinstance(loaded, tuple) else loaded
        fc_rt = np.asarray(m2.forecast_fuf(6).level[:6], float)
    finally:
        os.unlink(tmp)

    # the invariant: same level forecast (within .6f .pre precision)
    assert np.allclose(fc_mem, fc_rt, atol=0.05), \
        f"in-memory != round-trip: {fc_mem} vs {fc_rt}"
