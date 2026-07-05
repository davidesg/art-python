"""Effect of deterministic components (mean + harmonics) on the seasonal DCD/MEG
boundary LR null distribution.

Extends the exact banded-ML engine of dcd_mc.py with a regression (GLS) component,
so the witness LR is computed in the realistic MEG model that carries a mean and
the deterministic harmonics at the OTHER frequencies (the harmonics at the tested
frequency f are annihilated by the ifadf unit root and are dropped).

Monthly deterministic seasonality has s-1 = 11 parameters (5 complex pairs cos/sin
+ 1 Nyquist term); the mean is separate.  Testing a complex frequency f annihilates
its 2 harmonics, leaving 9 seasonal + mean = 10 regressors.

Validated against fue (additive-at-level decomposition): at f=0 with the full
regressor set, this engine and fue agree to 3 decimals (pile-up 0.927 vs 0.928).
The deterministic effect is RESONANCE-dependent: at f=0 the mean is resonant with
the zero-frequency unit root and the critical values collapse (Chen-Davis); at a
seasonal frequency the surviving regressors are non-resonant and the effect is
modest (critical values rise ~30%).  Because the MEG annihilates the resonant
harmonics (those at f), it avoids the catastrophic resonant pile-up by design.

Estimator note: uses the exact banded Cholesky likelihood, NOT fue.  fue's
likelihood has an erratic jump at the exact non-invertibility boundary (coef=-1)
that inflates the pile-up (see dcd_mc.py and the project notes).
"""
from __future__ import annotations

import argparse

import numpy as np
from scipy.linalg import cholesky_banded, cho_solve_banded
from scipy.optimize import minimize_scalar

S = 12


def neg2ll_reg(x: np.ndarray, c1: float, c2: float, Z: np.ndarray | None) -> float:
    """Exact -2logL (beta, sigma2 concentrated) for x = Z beta + (1+c1 B+c2 B^2) errors."""
    n = x.size
    g0 = 1.0 + c1 * c1 + c2 * c2
    g1 = c1 + c1 * c2
    g2 = c2
    ab = np.zeros((3, n))
    ab[0, 2:] = g2
    ab[1, 1:] = g1
    ab[2, :] = g0
    try:
        cb = cholesky_banded(ab, lower=False)
    except np.linalg.LinAlgError:
        return np.inf
    logdet = 2.0 * np.log(cb[-1, :]).sum()
    Gx = cho_solve_banded((cb, False), x)
    if Z is None or Z.shape[1] == 0:
        quad = float(x @ Gx)
    else:
        GZ = cho_solve_banded((cb, False), Z)
        A = Z.T @ GZ
        b = Z.T @ Gx
        beta = np.linalg.solve(A, b)
        quad = float(x @ Gx - b @ beta)
    return logdet + n * np.log(quad / n)


def _coefs(f: int, r: float) -> tuple[float, float]:
    if 1 <= f <= 5:
        return -2.0 * np.cos(2 * np.pi * f / S) * r, r * r
    if f == 6:
        return r, 0.0
    if f == 0:
        return -r, 0.0
    raise ValueError(f)


def design(f: int, n: int, kind: str) -> np.ndarray | None:
    """Regression design at the level.  kind: none | mean | full (mean+other harmonics)."""
    if kind == "none":
        return None
    t = np.arange(1, n + 1)
    cols = [np.ones(n)]                       # mean / constant
    if kind == "mean":
        return np.column_stack(cols)
    for g in range(1, 6):                     # complex harmonics at other frequencies
        if g == f:
            continue
        wg = 2 * np.pi * g / S
        cols += [np.cos(wg * t), np.sin(wg * t)]
    if f != 6:                                # Nyquist term (annihilated when testing Nyquist)
        cols.append((-1.0) ** t)
    return np.column_stack(cols)


def simulate_boundary(f: int, n: int, rng: np.random.Generator) -> np.ndarray:
    if 1 <= f <= 5:
        w = 2 * np.pi * f / S
        a = rng.standard_normal(n + 2)
        return a[2:] - 2 * np.cos(w) * a[1:-1] + a[:-2]
    if f == 6:
        a = rng.standard_normal(n + 1)
        return a[1:] + a[:-1]
    if f == 0:
        a = rng.standard_normal(n + 1)
        return a[1:] - a[:-1]
    raise ValueError(f)


def lr_one(f: int, x: np.ndarray, Z: np.ndarray | None) -> float:
    obj = lambda r: neg2ll_reg(x, *_coefs(f, r), Z)
    l_const = obj(1.0)
    res = minimize_scalar(obj, bounds=(0.02, 0.99999), method="bounded",
                          options={"xatol": 1e-6})
    return max(0.0, l_const - res.fun)


def simulate(f: int, kind: str, n: int, reps: int, seed: int) -> np.ndarray:
    Z = design(f, n, kind)
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for i in range(reps):
        out[i] = lr_one(f, simulate_boundary(f, n, rng), Z)
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--f", type=int, default=3)
    p.add_argument("--n", type=int, default=120)
    p.add_argument("--reps", type=int, default=10000)
    p.add_argument("--seed", type=int, default=100)
    args = p.parse_args()
    print(f"deterministic-components effect -- f={args.f}, n={args.n}, reps={args.reps}")
    for kind in ("none", "mean", "full"):
        lr = simulate(args.f, kind, args.n, args.reps, args.seed)
        q = np.quantile(lr, (0.90, 0.95, 0.99))
        k = 0 if design(args.f, args.n, kind) is None else design(args.f, args.n, kind).shape[1]
        print(f"  {kind:5s} (k={k:2d}): pile-up={float((lr<1e-6).mean()):.3f}  "
              f"10/5/1% = {q[0]:.3f} {q[1]:.3f} {q[2]:.3f}", flush=True)
