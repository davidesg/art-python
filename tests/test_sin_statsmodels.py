"""art without statsmodels (2026-09-28): the theoretical ACF is ART's C
simulator (`_acf_teorica`), and ADF/KPSS are written from the literature
(`_raiz_unitaria`). statsmodels is a TEST dependency only: here it is the
yardstick the ports must reproduce, number for number, because the choice of
d is p < 0.05 and must not move.
"""
import os
import subprocess
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

from art._acf_teorica import acf_pacf
from art._raiz_unitaria import adf, kpss, mackinnon_crit

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0192", "")


def _series():
    rng = np.random.default_rng(3)
    for i in range(120):
        n = int(rng.integers(20, 400))
        e = rng.standard_normal(n)
        kind = i % 4
        if kind == 0:
            yield np.cumsum(e)
        elif kind == 1:
            yield e
        elif kind == 2:
            yield np.convolve(e, [1, .6])[:n]
        else:
            yield np.cumsum(np.cumsum(e))
    for f, c in [("airline_serie_G.csv", "pasajeros"), ("IPC_ES_2002_2019.csv", "value")]:
        y = np.log(pd.read_csv(F + f)[c].values)
        yield from (y, np.diff(y), np.diff(np.diff(y)), y[12:] - y[:-12])


def test_adf_is_statsmodels_adfuller():
    st = pytest.importorskip("statsmodels.tsa.stattools")
    for x in _series():
        a, b = st.adfuller(x, autolag="AIC"), adf(x)
        assert b[0] == pytest.approx(a[0], abs=1e-8)
        assert b[1] == pytest.approx(a[1], abs=1e-10)
        assert b[2] == a[2] and b[3] == a[3]                    # lag and nobs
        for k in ("1%", "5%", "10%"):
            assert b[4][k] == pytest.approx(a[4][k], abs=1e-12)


def test_kpss_is_statsmodels_kpss():
    st = pytest.importorskip("statsmodels.tsa.stattools")
    for x in _series():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            a = st.kpss(x, regression="c", nlags="auto")
        b = kpss(x)
        assert b[0] == pytest.approx(a[0], abs=1e-12)
        assert b[1] == pytest.approx(a[1], abs=1e-12)
        assert b[2] == a[2]


def test_mackinnon_asymptotic_critical_values():
    c = mackinnon_crit()
    assert (c["1%"], c["5%"], c["10%"]) == (-3.43035, -2.86154, -2.56677)


def _bj(phi, theta, Phi, Theta, s):
    def poly(reg, seas):
        a = np.r_[1.0, -np.asarray(reg, float)]
        b = np.zeros(len(seas) * s + 1); b[0] = 1.0
        for i, v in enumerate(seas):
            b[(i + 1) * s] = -v
        return np.convolve(a, b)
    return poly(phi, Phi), poly(theta, Theta)


@pytest.mark.parametrize("p,q,P,Q", [(0, 1, 0, 1), (1, 0, 0, 0), (1, 1, 0, 1), (2, 1, 1, 0),
                                     (0, 3, 0, 1), (3, 0, 1, 1), (0, 0, 1, 0), (1, 2, 1, 1)])
def test_theoretical_acf_is_armaprocess_in_bj_convention(p, q, P, Q):
    ap = pytest.importorskip("statsmodels.tsa.arima_process")
    phi = [.5 / (i + 1) for i in range(p)]
    theta = [.3 / (i + 1) for i in range(q)]
    Phi = [.4 / (i + 1) for i in range(P)]
    Theta = [min(.3 + .1 * i, .8) for i in range(Q)]
    a, pc = acf_pacf(phi, theta, Phi, Theta, 12, 39)
    ar, ma = _bj(phi, theta, Phi, Theta, 12)
    pr = ap.ArmaProcess(ar=ar, ma=ma)
    np.testing.assert_allclose(a, pr.acf(40)[1:40], atol=1e-12)
    np.testing.assert_allclose(pc, pr.pacf(40)[1:40], atol=1e-12)


def test_the_c_convention_ma1_bar_is_negative():
    a, _ = acf_pacf(theta=[0.3], lags=2)
    assert a[0] == pytest.approx(-0.3 / 1.09)


def test_not_stationary_or_not_invertible_is_refused():
    assert acf_pacf(phi=[1.0], lags=5) == (None, None)
    assert acf_pacf(theta=[1.2], lags=5) == (None, None)


def test_art_does_not_import_statsmodels():
    code = ("import sys, art, art.model_detection, art.identification, art.describe, "
            "art.mcp_server; print('statsmodels' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.stdout.strip().splitlines()[-1] == "False", out.stderr[-2000:]
