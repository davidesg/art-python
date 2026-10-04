"""BUG-0206 — which F tests seasonality where (research/seasonal_test).

Identification keeps the HAC F (more power; a false positive is pruned later
in the model). The residual diagnosis uses the OLS F: there H0 is white noise,
where the HAC F gave 18% false alarms at n=216."""
import warnings

import numpy as np
import pytest
from scipy import stats

import fue
from art import diagnosis
from art import seasonal_detection as sd


def _ts(x):
    return fue.TimeSeries.from_array(list(map(float, x)), freq=12,
                                     start=[2000, 1], name="x")


def test_the_default_is_still_hac():
    rng = np.random.default_rng(0)
    ts = _ts(100 + np.cumsum(rng.standard_normal(217)))
    a = sd.detect_seasonality(ts, d=1, lam=1.0)
    b = sd.detect_seasonality(ts, d=1, lam=1.0, test="hac")
    assert a.f_stat == b.f_stat and "HAC F" in a.message


def test_ols_is_the_plain_f():
    rng = np.random.default_rng(1)
    e = rng.standard_normal(216)
    r = sd.detect_seasonality(_ts(e), d=0, lam=1.0, test="ols")
    X = sd._build_differenced_harmonic_matrix(216, 0, 12)
    c, *_ = np.linalg.lstsq(X, e, rcond=None)
    u = e - X @ c
    V = (u @ u / (216 - 12)) * np.linalg.inv(X.T @ X)
    f = c[1:] @ np.linalg.solve(V[1:, 1:], c[1:]) / 11
    assert r.f_stat == pytest.approx(f, rel=1e-10)
    assert r.p_value == pytest.approx(stats.f.sf(f, 11, 204), rel=1e-8)
    assert "OLS F" in r.message


def test_an_unknown_test_is_refused():
    with pytest.raises(ValueError):
        sd.detect_seasonality(_ts(np.arange(1, 100.0)), d=1, test="bartlett")


def test_white_residuals_rarely_look_seasonal():
    """The residual check's false-alarm rate on white noise is near 5% with
    the OLS F (it was 18% with the HAC F at n=216)."""
    rng = np.random.default_rng(2)
    R = 300
    hits = sum(sd.detect_seasonality(_ts(rng.standard_normal(216)), d=0,
                                     lam=1.0, test="ols").seasonal_detected
               for _ in range(R))
    assert hits / R < 0.09


def test_diagnose_asks_for_the_ols_f(monkeypatch):
    seen = {}
    real = diagnosis.detect_seasonality

    def spy(*a, **k):
        seen.update(k)
        return real(*a, **k)
    monkeypatch.setattr(diagnosis, "detect_seasonality", spy)
    rng = np.random.default_rng(3)
    y = 100 + np.cumsum(0.2 + rng.standard_normal(216))
    m = fue.Model(_ts(y), d=1, D=0, boxlam=1.0, refactor=1.0,
                  ar=[], ar_free=[], ma=[], ma_free=[], ar_s=[], ma_s=[],
                  interventions=[], ifadf=[0] * 7, mu=0.2, estimate_mu=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit()
        diagnosis.diagnose(m)
    assert seen.get("test") == "ols" and seen.get("d") == 0
