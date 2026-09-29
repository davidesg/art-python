"""BUG-0194: the identification can propose an AR of high order.

Three limits kept it out: p_max = 3; the cut on "three quiet lags in a row",
which swallowed the s/2 submultiple; and the representative template
0.5/(i+1), NOT STATIONARY for p >= 4 (it sums to 1.225 at p = 6), so the
candidate vanished in silence. Decided: p_max = max(3, s/2), q <= 2, Q <= 1; the
regular search stays at 3 and an AR of order s/2 enters only on an ISOLATED
PACF bar at s/2 (lags 4..s/2-1 inside the band); for a complete AR of order
>= 4 the Yule-Walker template of the empirical ACF.
"""
import os
import shutil

import numpy as np
import pytest

pytest.importorskip("fue")
import fue  # noqa: E402
import art  # noqa: E402
import art.model_detection as md  # noqa: E402
from art.describe import _resid_start  # noqa: E402
from art.mcp_server import _load_ts_model  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0194_0195")


def test_hicp_es_m01_residuals_get_an_ar6(tmp_path):
    """PACF +0.18 at 1 and +0.23 at 6 (band 0.13): the AR(6) is on the list."""
    shutil.copy(os.path.join(F, "HICP_ES_m01.pre"), tmp_path)
    ts, m = _load_ts_model(str(tmp_path / "HICP_ES_m01.pre"))
    m.fit()
    r = fue.TimeSeries(m.residuals.data, freq=ts.freq, start=_resid_start(m), name="R")
    specs = art.suggest_orders(r, d=0, D=0, lam=1.0, top_n=5)
    assert (6, 0, 0, 0) in [(s.p, s.q, s.P, s.Q) for s in specs]


def test_the_half_season_lag_is_looked_at():
    """Bars only at 1 and s/2 = 6: the effective AR order reaches 6."""
    n, L = 200, 39
    pacf = np.zeros(L); acf = np.zeros(L)
    pacf[0], pacf[5] = 0.30, 0.30
    eff = md._effective_orders(acf, pacf, 12, n, 6, 2, 1, 1)
    assert eff[0] == 6


def test_a_block_of_significant_lags_is_persistence_not_a_high_ar():
    """PACF significant at 1, 2, 3, 5 and 6 (Chile's ∇ln CPI, an I(2) series):
    the s/2 bar is not isolated, so the AR search stays at 3."""
    n, L = 191, 39
    pacf = np.zeros(L); acf = np.zeros(L)
    pacf[:6] = [0.62, 0.22, 0.18, -0.04, 0.18, 0.20]
    assert md._effective_orders(acf, pacf, 12, n, 6, 2, 1, 1)[0] == 3


def test_high_order_templates_exist_and_are_stationary():
    assert md._theoretical_acf_pacf(6, 0, 0, 0, 12, 39)[0] is not None   # scaled fallback
    acf = 0.5 ** np.arange(1, 40)
    a, _ = md._theoretical_acf_pacf(6, 0, 0, 0, 12, 39, acf_emp=acf)
    assert a is not None and np.all(np.isfinite(a))


def test_default_orders():
    import inspect
    sig = inspect.signature(md.suggest_orders)
    assert sig.parameters["p_max"].default is None
    assert sig.parameters["q_max"].default == 2 and sig.parameters["Q_max"].default == 1


def test_every_seasonal_submultiple_from_4_is_looked_at():
    """Hybrid seasonality can show at any badly represented frequency: an
    isolated PACF bar at 4 (f = 3 in monthly data) opens AR(4) as well."""
    n, L = 200, 39
    pacf = np.zeros(L); acf = np.zeros(L)
    pacf[0], pacf[3] = 0.30, 0.30
    assert md._effective_orders(acf, pacf, 12, n, 6, 2, 1, 1)[0] == 4
    pacf = np.zeros(L); pacf[0], pacf[1] = 0.3, 0.3                 # quarterly: s/2 = 2 < 4
    assert md._effective_orders(acf, pacf, 4, n, 3, 2, 1, 1)[0] == 2
