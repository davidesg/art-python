"""ADF and KPSS without statsmodels: the two unit-root tests art uses to
choose d, written from the literature.

They reproduce what art called before, statsmodels 0.14's
`adfuller(x, autolag="AIC")` (constant, no trend) and
`kpss(x, regression="c", nlags="auto")`, number for number: the verdicts on
d are p < 0.05, so the port has to land on the same side of that line. The
tests pin the agreement against statsmodels, which stays a TEST dependency
only.

Why not the C's: ART's `unit_root_tests.c` takes the ADF p-value from a
Student t (the Dickey-Fuller law is not a t) and uses fixed critical values;
its KPSS "5 %" value switches between the 10 %, 5 % and 1 % columns by n.

References
----------
Dickey, D.A. and Fuller, W.A. (1979). JASA 74, 427-431.
MacKinnon, J.G. (1994). "Approximate asymptotic distribution functions for
    unit-root and cointegration tests." JBES 12, 167-176.  (p-values)
MacKinnon, J.G. (2010). "Critical values for cointegration tests." Queen's
    University WP 1227.  (critical values)
Schwert, G.W. (1989). JBES 7, 147-159.  (the ADF maximum lag)
Kwiatkowski, D., Phillips, P.C.B., Schmidt, P. and Shin, Y. (1992). J.
    Econometrics 54, 159-178.  (KPSS; Table 1, critical values)
Hobijn, B., Franses, P.H. and Ooms, M. (1998). Econometric Institute Report
    9802/A.  (the KPSS automatic bandwidth)
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

# --------------------------------------------------------------------------- #
#  MacKinnon (1994) response surface, one series (N = 1), with constant ("c") #
# --------------------------------------------------------------------------- #
# Below TAU_STAR the small-p polynomial, above it the large-p one; outside
# [TAU_MIN, TAU_MAX] the p-value is 0 or 1. Coefficients in increasing power,
# already scaled as MacKinnon tabulates them (1, 1, 1e-2 and 1, 1e-1, 1e-1,
# 1e-2).
_TAU_STAR = -1.61
_TAU_MIN = -18.83
_TAU_MAX = 2.74
_SMALLP = (2.1659, 1.4412, 3.8269e-2)
_LARGEP = (1.7339, 9.3202e-1, -1.2745e-1, -1.0368e-2)

# MacKinnon (2010), N = 1, constant: 1 %, 5 %, 10 %; c(T) = b0 + b1/T + b2/T² + b3/T³
_CRIT_2010 = ((-3.43035, -6.5393, -16.786, -79.433),
              (-2.86154, -2.8903, -4.234, -40.040),
              (-2.56677, -1.5384, -2.809, 0.0))

# KPSS (1992), Table 1, level stationarity: 10 %, 5 %, 2.5 %, 1 %
_KPSS_CRIT = (0.347, 0.463, 0.574, 0.739)
_KPSS_P = (0.10, 0.05, 0.025, 0.01)


def _polyval_inc(coef, x):
    return sum(c * x ** k for k, c in enumerate(coef))


def mackinnon_p(tau: float) -> float:
    """Asymptotic p-value of the ADF t-statistic (constant, N = 1)."""
    if tau > _TAU_MAX:
        return 1.0
    if tau < _TAU_MIN:
        return 0.0
    coef = _SMALLP if tau <= _TAU_STAR else _LARGEP
    return float(norm.cdf(_polyval_inc(coef, tau)))


def mackinnon_crit(nobs: float = math.inf) -> dict:
    """Finite-sample critical values of the ADF test (constant, N = 1)."""
    out = {}
    for lbl, b in zip(("1%", "5%", "10%"), _CRIT_2010):
        if math.isinf(nobs):
            out[lbl] = b[0]
        else:
            out[lbl] = b[0] + b[1] / nobs + b[2] / nobs ** 2 + b[3] / nobs ** 3
    return out


def _ols(y, X):
    """OLS: coefficients, their t-ratios and the Gaussian AIC (as statsmodels)."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n, k = X.shape
    ssr = float(e @ e)
    s2 = ssr / (n - k)
    se = np.sqrt(s2 * np.diag(np.linalg.pinv(X.T @ X)))
    llf = -0.5 * n * (math.log(2 * math.pi) + math.log(ssr / n) + 1.0)
    return beta, beta / se, -2.0 * llf + 2.0 * k


def _adf_design(x, xdiff, lags):
    """Rows t with `lags` lagged differences: [level_{t-1}, Δx_{t-1}, …, Δx_{t-lags}]."""
    nobs = len(xdiff) - lags
    cols = [x[lags:lags + nobs]]                         # level, lagged once
    for j in range(1, lags + 1):
        cols.append(xdiff[lags - j:lags - j + nobs])
    return np.column_stack(cols), xdiff[lags:]


def adf(x) -> tuple[float, float, int, int, dict]:
    """Augmented Dickey-Fuller, constant, lag by AIC.

    Returns (t-statistic, p-value, lags used, nobs, critical values), as
    statsmodels' `adfuller(x, autolag="AIC")` does (without its icbest).

    The lag search runs on a COMMON sample, the one the maximum lag leaves,
    so the AICs are comparable; the chosen lag is then refitted on its own,
    longer, sample. Maximum lag: Schwert's 12·(n/100)^¼, capped at n/2 − 2.
    """
    x = np.asarray(x, dtype=float)
    if x.max() == x.min():
        raise ValueError("Invalid input, x is constant")
    n = len(x)
    maxlag = int(math.ceil(12.0 * (n / 100.0) ** 0.25))
    maxlag = min(n // 2 - 1 - 1, maxlag)
    if maxlag < 0:
        raise ValueError("sample size is too short for the ADF regression")
    xdiff = np.diff(x)

    Xmax, ymax = _adf_design(x, xdiff, maxlag)
    ones = np.ones((len(ymax), 1))
    best = None
    for lag in range(0, maxlag + 1):
        _b, _t, aic = _ols(ymax, np.hstack([ones, Xmax[:, :lag + 1]]))
        if best is None or aic < best[0]:
            best = (aic, lag)
    usedlag = best[1]

    X, y = _adf_design(x, xdiff, usedlag)
    _b, t, _aic = _ols(y, np.hstack([X, np.ones((len(y), 1))]))
    stat = float(t[0])
    return stat, mackinnon_p(stat), usedlag, len(y), mackinnon_crit(len(y))


def _kpss_bandwidth(e, n):
    """Hobijn, Franses and Ooms (1998): the automatic Bartlett bandwidth."""
    covlags = int(n ** (2.0 / 9.0))
    s0 = float(e @ e) / n
    s1 = 0.0
    for i in range(1, covlags + 1):
        g = float(e[i:] @ e[:n - i]) / (n / 2.0)
        s0 += g
        s1 += i * g
    gamma = 1.1447 * ((s1 / s0) ** 2) ** (1.0 / 3.0)
    return int(gamma * n ** (1.0 / 3.0))


def kpss(x) -> tuple[float, float, int, dict]:
    """KPSS for level stationarity, automatic bandwidth.

    Returns (statistic, p-value, bandwidth, critical values), as statsmodels'
    `kpss(x, regression="c", nlags="auto")`. The p-value is interpolated in
    KPSS's Table 1, so it is clipped to [0.01, 0.10]: beyond the table the true
    p-value is smaller (or larger) than the one returned.
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    e = x - x.mean()
    lags = min(_kpss_bandwidth(e, n), n - 1)
    eta = float(np.sum(np.cumsum(e) ** 2)) / n ** 2
    s = float(e @ e)
    for i in range(1, lags + 1):
        s += 2.0 * float(e[i:] @ e[:n - i]) * (1.0 - i / (lags + 1.0))
    stat = eta / (s / n)
    p = float(np.interp(stat, _KPSS_CRIT, _KPSS_P))
    crit = dict(zip(("10%", "5%", "2.5%", "1%"), _KPSS_CRIT))
    return stat, p, lags, crit
