"""BUG-0198: the identifier finds an AR(2) with complex roots.

The port had replaced the C's coefficient search by one representative
template per order; the AR(2)'s, 1 − 0.5B − 0.25B², has real roots and cannot
oscillate, so an AR(2) with complex roots — a cycle, what the school looks for
in monthly CPI — ranked behind the AR(1) (1 simulated series in 12). Now the
templates are searched as in ART_18 (Yule-Walker for a pure AR, the grid and
the fitted coefficients otherwise), the C's crude stationarity guard is
replaced by a contraction that keeps the cycle's period, and the ranking is
the pattern's, parsimony (fewer parameters, pure before mixed) and then the
AICc settling only what the pattern leaves tied (option B).
"""
import os

import numpy as np
import pytest

pytest.importorskip("fue")
import fue  # noqa: E402
import art  # noqa: E402
from art._acf_teorica import _poly, psi_weights  # noqa: E402
from art.mcp_server import _load_ts_model  # noqa: E402
from art.model_detection import _contract  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0196_0197")


def _sim(phi=(), theta=(), n=200, seed=0, freq=12):
    rng = np.random.default_rng(seed)
    p, q = len(phi), len(theta)
    e = rng.standard_normal(n + 300) * 0.01
    w = np.zeros(n + 300)
    for t in range(max(p, q), n + 300):
        w[t] = (e[t] + sum(phi[i] * w[t - 1 - i] for i in range(p))
                - sum(theta[j] * e[t - 1 - j] for j in range(q)))
    z = np.log(100.0) + np.cumsum(w[300:])
    return fue.TimeSeries(list(np.exp(z)), freq=freq, start=(2000, 1), name="SIM")


def _first(ts, **kw):
    s = art.suggest_orders(ts, top_n=5, **kw)[0]
    return (s.p, s.q, s.P, s.Q)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_a_monthly_ar2_with_complex_roots_comes_first(seed):
    """φ = (1.0, −0.5): inverse roots of modulus 0.71, a period of 8 months."""
    ts = _sim((1.0, -0.5), seed=seed)
    assert _first(ts, d=1, D=0, lam=0.0, n_harmonics=0) == (2, 0, 0, 0)


@pytest.mark.parametrize("seed", [0, 1])
def test_an_annual_ar2_with_complex_roots_comes_first(seed):
    ts = _sim((1.0, -0.6), n=80, seed=seed, freq=1)
    assert _first(ts, d=1, D=0, lam=0.0) == (2, 0, 0, 0)


@pytest.mark.parametrize("seed", [0, 1])
def test_the_controls_hold(seed):
    """An AR(1), an MA(1) and a negative MA(1) are still read as such."""
    kw = dict(d=1, D=0, lam=0.0, n_harmonics=0)
    assert _first(_sim((0.6,), seed=seed), **kw) == (1, 0, 0, 0)
    assert _first(_sim((), (0.6,), seed=seed), **kw) == (0, 1, 0, 0)
    assert _first(_sim((), (-0.5,), seed=seed), **kw) == (0, 1, 0, 0)


def test_the_muskrat_gets_its_ar2():
    """∇ln muskrat (Jenkins and Alavi): PACF at 2, the ACF waving."""
    ts, _ = _load_ts_model(os.path.join(F, "MUSKRAT.inp"))
    assert _first(ts, d=1, D=0, lam=0.0) == (2, 0, 0, 0)


def test_the_aicc_is_information_on_every_candidate():
    specs = art.suggest_orders(_sim((1.0, -0.5)), d=1, D=0, lam=0.0,
                               n_harmonics=0, top_n=5)
    assert all(s.aicc is not None for s in specs)
    assert abs(sum(s.weight or 0 for s in specs) - 1.0) < 0.2   # the listed share


def test_the_contraction_keeps_the_period():
    """The C rescaled Σ|φ| >= 0.99 to 0.95 — flattening a stationary AR(2)
    with complex roots. `_contract` leaves a stationary one alone and, when
    it must pull the roots in, keeps their angle: the period."""
    phi = np.array([1.0, -0.5])
    assert np.allclose(_contract(phi), phi)
    bad = np.array([1.6, -1.1])                   # inverse roots of modulus 1.05
    got = _contract(bad)
    ang = lambda c: np.angle(np.roots(np.r_[1.0, -c]))   # noqa: E731
    assert np.max(np.abs(np.roots(np.r_[1.0, -got]))) < 1.0
    assert np.allclose(np.sort(ang(bad)), np.sort(ang(got)))


def test_psi_weights_are_the_cs_recursion():
    """lfilter runs the C's recursion: identical to the loop it replaced."""
    ar, ma = _poly([0.5, -0.3], [0.4], 12), _poly([0.3, 0.2], [0.6], 12)
    psi = psi_weights(ar, ma, 300)
    ref = np.zeros(301)
    for j in range(301):
        v = ma[j] if j < len(ma) else 0.0
        for k in range(1, min(j, len(ar) - 1) + 1):
            v -= ar[k] * ref[j - k]
        ref[j] = v
    assert np.allclose(psi, ref, atol=1e-14)
