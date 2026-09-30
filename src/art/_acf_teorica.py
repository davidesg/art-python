"""Theoretical ACF/PACF of a multiplicative SARMA, ported from ART's C.

`ARMA.c` (`calcular_coeficientes_psi`, `calcular_ACF_PACF_SARIMA`, identical
from ART_v1 to ART_18.1): the ψ weights of the MA(∞), truncated at M = 2000
terms; the autocovariances as Σ ψⱼ ψⱼ₊ₖ; the PACF by Durbin-Levinson.

The convention is Box-Jenkins', as in the C:

    (1 − φ₁B − …)(1 − Φ₁Bˢ − …) wₜ = (1 − θ₁B − …)(1 − Θ₁Bˢ − …) aₜ

so θ > 0 gives a NEGATIVE bar at lag 1. This module exists so that the
convention cannot drift again (BUG-0192: statsmodels' `ArmaProcess` takes the
MA polynomial as written, and the C's θ > 0 were passed to it as 1 + θB).

One difference from the C, deliberate: in its mixed branch (AR present) the
C builds the MA part as 1 − θB − ΘBˢ, without the cross term +θΘ B^{1+s} of
the multiplicative model; its pure-MA branch has it. Here the MA is always
the full product, so pure MA and pure AR models agree with the C to rounding,
and mixed ones are the multiplicative model the C's pure branch describes.
"""
from __future__ import annotations

import numpy as np

M = 2000          # truncation of the MA(∞), as the C


def _poly(reg, seas, s):
    """Coefficients of (1 − Σ rᵢBⁱ)(1 − Σ Sᵢ B^{is}), increasing powers."""
    a = np.r_[1.0, -np.asarray(reg, float)]
    b = np.zeros(len(seas) * s + 1)
    b[0] = 1.0
    for i, v in enumerate(seas):
        b[(i + 1) * s] = -float(v)
    return np.convolve(a, b)


def _outside_unit_circle(poly):
    """True if every root of the polynomial (increasing powers) lies outside."""
    c = np.trim_zeros(np.asarray(poly, float), "b")
    if len(c) <= 1:
        return True
    return bool(np.all(np.abs(np.roots(c[::-1])) > 1.0))


def psi_weights(ar_poly, ma_poly, m=M):
    """ψ₀ … ψₘ of ma(B)/ar(B): ψⱼ = maⱼ − Σₖ arₖ ψⱼ₋ₖ (ar₀ = 1).

    The C's recursion exactly, run by `scipy.signal.lfilter` (the same
    difference equation, the impulse as input): identical to 1e-17 and some
    150 times faster than the loop it replaces — which is what lets the
    identifier search the coefficients again, as the C does (BUG-0198)."""
    from scipy.signal import lfilter
    x = np.zeros(m + 1)
    x[0] = 1.0
    return lfilter(np.asarray(ma_poly, float), np.asarray(ar_poly, float), x)


def acf_pacf(phi=(), theta=(), Phi=(), Theta=(), s=1, lags=40, m=M):
    """ACF and PACF at lags 1..lags, or (None, None) if the model is not
    stationary or not invertible (as statsmodels' checks, which art used)."""
    ar = _poly(phi, Phi, s)
    ma = _poly(theta, Theta, s)
    if not (_outside_unit_circle(ar) and _outside_unit_circle(ma)):
        return None, None
    psi = psi_weights(ar, ma, m)
    gamma = np.array([psi[:m + 1 - k] @ psi[k:] for k in range(lags + 1)])
    if gamma[0] <= 1e-10:
        return np.zeros(lags), np.zeros(lags)
    rho = gamma / gamma[0]

    # Durbin-Levinson, as the C
    pacf = np.zeros(lags + 1)
    prev = np.zeros(lags + 1)
    if lags >= 1:
        pacf[1] = prev[1] = rho[1]
    for n in range(2, lags + 1):
        num = rho[n] - prev[1:n] @ rho[n - 1:0:-1]
        den = 1.0 - prev[1:n] @ rho[1:n]
        cur = np.zeros(lags + 1)
        cur[n] = 0.0 if abs(den) < 1e-10 else num / den
        cur[1:n] = prev[1:n] - cur[n] * prev[n - 1:0:-1]
        pacf[n] = cur[n]
        prev = cur
    return rho[1:], pacf[1:]
