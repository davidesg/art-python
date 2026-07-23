"""BUG-0007 (ART side) — a fuf model rebuilt with fue.Model(...) must carry
`refactor`.

`update_and_forecast` (and the intervention-append path) rebuild the model from
its fields after appending observations. fuf models carry `refactor = 100` (ART's
×100 conditioning) and store `mu0` in that rescaled space. Rebuilding at the fue
default `refactor = 1.0` reads the drift 100× off, so the forecast LEVEL runs away.
Only models WITH a mean are affected (with mu0 = 0 there is no drift to mis-scale).
"""
import numpy as np
import fue
from art.pipeline import _make_model


def _fitted_model_with_mean(freq=12, n=240, seed=7):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    w = 0.002 + 0.01 * np.cos(2 * np.pi * t / freq) + rng.normal(0.0, 0.004, n)
    y = np.exp(np.cumsum(w) + 4.6)                      # positive level, small +drift
    ts = fue.TimeSeries.from_array(y.tolist(), freq=freq, start=(2002, 1), name="X")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0,
                    n_harmonics=2, P=0, Q=0, estimate_mu=True)
    m.fit()
    return ts, m


def _rebuild(ts, m, carry_refactor):
    """Rebuild exactly as mcp_server.update_and_forecast does."""
    kw = dict(
        ar=m.ar, ar_free=m.ar_free, ma=m.ma, ma_free=m.ma_free,
        ar_s=m.ar_s, ar_s_free=m.ar_s_free, ma_s=m.ma_s, ma_s_free=m.ma_s_free,
        ar_f=m.ar_f, ma_f=m.ma_f, d=m.d, D=m.D, ifadf=m.ifadf,
        interventions=m.interventions, mu=m.mu0, estimate_mu=m.estimate_mu,
        boxlam=m.boxlam,
    )
    if carry_refactor:
        kw["refactor"] = m.refactor
    return fue.Model(ts, **kw)


def test_model_carries_mean_in_rescaled_space():
    _, m = _fitted_model_with_mean()
    assert m.refactor == 100.0
    assert abs(m.mu0) > 0.01          # ×100 of a ~0.002 drift, not the raw ~0.002


def test_rebuild_with_refactor_does_not_explode():
    ts, m = _fitted_model_with_mean()
    last = float(ts.data[-1])
    fc = np.asarray(_rebuild(ts, m, carry_refactor=True).forecast_fuf(horizon=24).level, float)
    # sane: the level stays in the neighbourhood of the last observation
    assert np.all(fc < 1.5 * last) and np.all(fc > 0.5 * last), fc


def test_dropping_refactor_runs_the_level_away():
    # control — this is the bug the fix guards against: without refactor the
    # mis-scaled drift blows the level up relative to carrying it.
    ts, m = _fitted_model_with_mean()
    fc_ok  = np.asarray(_rebuild(ts, m, carry_refactor=True).forecast_fuf(horizon=24).level, float)
    fc_bad = np.asarray(_rebuild(ts, m, carry_refactor=False).forecast_fuf(horizon=24).level, float)
    assert fc_bad[-1] > 2.0 * fc_ok[-1], (fc_ok[-1], fc_bad[-1])
