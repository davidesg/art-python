"""BUG-0206 — the candidate tests of deterministic seasonality.

All work on w, the regular differences of the (log) series, with art's design:
an intercept plus the s-1 differenced harmonics
(`seasonal_detection._build_differenced_harmonic_matrix`). Each returns
(statistic, p-value); the test rejects at 5% when p < 0.05.

  hac_art   art's test as it is: Newey-West (Bartlett, 1-3 lags by n), HC0
            meat, Wald/q against F(q, n-k).
  hac_hc1   the same with the small-sample factor n/(n-k) (HC1).
  ewc       equal-weighted cosine HAC with fixed-b F critical values
            (Lazarus, Lewis, Stock and Watson 2018): W/q * (K-q+1)/K ~
            F(q, K-q+1). K = max(ceil(0.4 n^(2/3)), q+4): their rule, raised
            so that K > q with q = 11.
  fgls      prewhitening / feasible GLS: an AR(p) on the OLS residuals (p by
            AIC, at most 6), w and X filtered with it, OLS F on the filtered
            regression (Cochrane-Orcutt, two steps).
  ols       the plain OLS F (drvarma's, the C's).
  lr        the LR of the harmonics inside the ARMA model, exact Gaussian
            likelihood (statsmodels ARIMA), with the TRUE orders: an oracle,
            the best a model-based test can do; chi2(q).
"""
from __future__ import annotations

import math
import warnings

import numpy as np
from scipy import stats

from art.seasonal_detection import _build_differenced_harmonic_matrix

S = 12
Q = S - 1


def design(n, s=S, d=1):
    return _build_differenced_harmonic_matrix(n, d, s)


def _ols(w, X):
    XtX_inv = np.linalg.inv(X.T @ X)
    c = XtX_inv @ (X.T @ w)
    return c, w - X @ c, XtX_inv


def _wald(g, V):
    try:
        return float(g @ np.linalg.solve(V, g))
    except np.linalg.LinAlgError:
        return 0.0


def _nw_meat(X, u, L):
    xu = X * u[:, None]
    S_ = xu.T @ xu
    for lag in range(1, L + 1):
        wgt = 1.0 - lag / (L + 1.0)
        cr = xu[lag:].T @ xu[:-lag]
        S_ += wgt * (cr + cr.T)
    return S_


def _art_lags(n):
    return 1 if n <= 100 else (2 if n <= 200 else 3)


def hac_art(w, X):
    n, k = X.shape
    c, u, Xi = _ols(w, X)
    V = Xi @ _nw_meat(X, u, _art_lags(n)) @ Xi
    f = _wald(c[1:], V[1:, 1:]) / Q
    return f, float(stats.f.sf(f, Q, max(n - k, 1)))


def hac_hc1(w, X):
    n, k = X.shape
    c, u, Xi = _ols(w, X)
    V = Xi @ _nw_meat(X, u, _art_lags(n)) @ Xi * n / (n - k)
    f = _wald(c[1:], V[1:, 1:]) / Q
    return f, float(stats.f.sf(f, Q, max(n - k, 1)))


def ewc_K(n):
    return max(math.ceil(0.4 * n ** (2.0 / 3.0)), Q + 4)


def ewc(w, X):
    n, k = X.shape
    c, u, Xi = _ols(w, X)
    K = ewc_K(n)
    t = np.arange(1, n + 1) - 0.5
    xu = X * u[:, None]
    Om = np.zeros((k, k))
    for j in range(1, K + 1):
        lam = math.sqrt(2.0 / n) * (np.cos(math.pi * j * t / n) @ xu)
        Om += np.outer(lam, lam)
    Om /= K
    V = Xi @ (n * Om) @ Xi
    W = _wald(c[1:], V[1:, 1:])
    f = W / Q * (K - Q + 1) / K
    return f, float(stats.f.sf(f, Q, K - Q + 1))


def _ar_fit(u, p):
    """OLS AR(p) on u (no constant: OLS residuals have mean 0)."""
    if p == 0:
        return np.zeros(0), float(u @ u / len(u))
    Y = u[p:]
    Z = np.column_stack([u[p - i - 1:len(u) - i - 1] for i in range(p)])
    a, *_ = np.linalg.lstsq(Z, Y, rcond=None)
    r = Y - Z @ a
    return a, float(r @ r / len(r))


def fgls(w, X, pmax=6):
    n, k = X.shape
    c, u, _ = _ols(w, X)
    best = None
    for p in range(pmax + 1):
        a, s2 = _ar_fit(u[pmax - p:], p) if p else _ar_fit(u[pmax:], 0)
        aic = (n - pmax) * math.log(s2) + 2 * p
        if best is None or aic < best[0]:
            best = (aic, p, a)
    _, p, a = best

    def filt(z):
        out = z[p:].copy()
        for i in range(p):
            out -= a[i] * z[p - i - 1:len(z) - i - 1]
        return out
    wf = filt(w)
    Xf = np.column_stack([filt(X[:, j]) for j in range(k)])
    m = len(wf)
    cf, uf, Xi = _ols(wf, Xf)
    df2 = max(m - k - p, 1)
    s2 = float(uf @ uf) / df2
    f = _wald(cf[1:], s2 * Xi[1:, 1:]) / Q
    return f, float(stats.f.sf(f, Q, df2))


def ols(w, X):
    n, k = X.shape
    c, u, Xi = _ols(w, X)
    s2 = float(u @ u) / (n - k)
    f = _wald(c[1:], s2 * Xi[1:, 1:]) / Q
    return f, float(stats.f.sf(f, Q, n - k))


def lr(w, X, order):
    """LR of the harmonics in ARIMA(p,0,q) with constant, true orders."""
    from statsmodels.tsa.arima.model import ARIMA
    p, q = order
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        l1 = ARIMA(w, exog=X[:, 1:], order=(p, 0, q), trend="c").fit().llf
        l0 = ARIMA(w, order=(p, 0, q), trend="c").fit().llf
    stat = max(0.0, 2.0 * (l1 - l0))
    return stat, float(stats.chi2.sf(stat, Q))


CHEAP = {"hac_art": hac_art, "hac_hc1": hac_hc1, "ewc": ewc,
         "fgls": fgls, "ols": ols}


def lr_fue(w, order, s=S):
    """The same LR with fue (art's engine, C): the series is cumsum(w), d=1,
    the s-1 harmonics as fue's cos/sin/alter terms, the TRUE ARMA orders, a
    mean. That is art's own model; much faster than statsmodels."""
    import fue
    p, q = order
    y = np.concatenate([[0.0], np.cumsum(w)]) + 1000.0
    ts = fue.TimeSeries(data=y.tolist(), freq=s, start=[2000, 1], name="SIM")

    def itvs():
        out = []
        for g in range(1, s // 2):
            out.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                                        harmonic=float(g)))
            out.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                                        harmonic=float(g)))
        out.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))
        return out

    def fit(with_h):
        m = fue.Model(ts, d=1, D=0, boxlam=1.0, refactor=1.0,
                      ar=[[0.1] * p] if p else [], ar_free=[[True] * p] if p else [],
                      ma=[[0.1] * q] if q else [], ma_free=[[True] * q] if q else [],
                      ar_s=[], ma_s=[],
                      interventions=itvs() if with_h else [],
                      ifadf=[0] * 7, mu=float(np.mean(w)), estimate_mu=True)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit()
        return float(m._result.loglik)

    stat = max(0.0, 2.0 * (fit(True) - fit(False)))
    return stat, float(stats.chi2.sf(stat, Q))
