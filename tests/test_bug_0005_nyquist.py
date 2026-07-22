"""BUG-0005 — the Nyquist `alter` is part of the deterministic seasonal package
and must appear IFF seasonality is specified.

The bug (and the test gap that let it through twice): a non-seasonal ARIMA and a
semi-annual (freq=2) SEASONAL model both have n_harmonics(pairs)=0, yet the first
must get NO seasonal terms and the second must get the alter (its only seasonal
harmonic). Gating the alter on n_harmonics conflated them. `_make_model` now gates
the whole seasonal package on the explicit `seasonal` flag.
"""
import numpy as np
import fue
from art.pipeline import _make_model


def _build(freq, n_harmonics, seasonal=None):
    rng = np.random.default_rng(3)
    y = (np.cumsum(rng.normal(0.0, 0.1, 160)) + 100.0).tolist()
    ts = fue.TimeSeries(data=y, freq=freq, start=[2000, 1], name="T")
    return _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0,
                       n_harmonics=n_harmonics, seasonal=seasonal)


def _seasonal(m):
    return [i for i in m.interventions if i.type in ("cos", "sin", "alter")]


def _alters(m):
    return [i for i in m.interventions if i.type == "alter"]


def test_nonseasonal_monthly_has_no_seasonal_terms():
    """freq=12, n_harmonics=0 (non-seasonal): NO seasonal deterministics, no alter.
    This is the exact BUG-0005 regression (WTI crude got a spurious alter)."""
    m = _build(freq=12, n_harmonics=0)          # seasonal=None -> derives False
    assert _seasonal(m) == []
    assert _alters(m) == []


def test_seasonal_false_forces_no_seasonal_terms():
    """seasonal=False drops the package even if n_harmonics>0."""
    m = _build(freq=12, n_harmonics=5, seasonal=False)
    assert _seasonal(m) == []


def test_seasonal_monthly_has_five_pairs_plus_alter():
    """freq=12 seasonal: 5 cos/sin pairs + 1 Nyquist alter = 11 seasonal terms."""
    m = _build(freq=12, n_harmonics=5)          # seasonal=None -> derives True
    assert len(_seasonal(m)) == 11
    assert len(_alters(m)) == 1


def test_semiannual_seasonal_is_alter_only():
    """freq=2 seasonal (seasonal=True): the ONLY seasonal term is the Nyquist alter,
    even though n_harmonics (pairs) = 0. This is the case the n_harmonics gate broke."""
    m = _build(freq=2, n_harmonics=0, seasonal=True)
    assert len(_alters(m)) == 1
    assert len(_seasonal(m)) == 1               # just the alter, no cos/sin pairs


def test_quarterly_seasonal_has_one_pair_plus_alter():
    """freq=4 seasonal: 1 cos/sin pair (f=1) + 1 alter (f=2 Nyquist) = 3 terms."""
    m = _build(freq=4, n_harmonics=1)
    assert len(_seasonal(m)) == 3
    assert len(_alters(m)) == 1
