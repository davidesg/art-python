"""Monte Carlo null distribution of the DCD/MEG boundary likelihood-ratio test.

Companion simulation for the paper *SF_MEG* (~/Dropbox/SF_MEG/Borrador).

Context
-------
ART (Box-Jenkins-Treadway) decides, frequency by frequency, whether seasonality
is deterministic or stochastic (the Treadway MEG procedure).  The decision rests
on the DCD statistic (Davis-Chen-Dunsmuir / Davis-Dunsmuir) for the
non-invertibility of a fixed-frequency moving-average witness factor.  For the
seasonal frequencies f = 1..5 the witness is the SECOND-order factor

        1 - 2 cos(w_f) r B + r^2 B^2 ,     w_f = 2 pi f / 12,

with a single free parameter r (modulus of the roots); for the Nyquist (f=6) and
the regular trend (f=0) it is the FIRST-order (1 +/- r B).  The null H0 puts the
parameter on the unit circle (r = 1, non-invertible = deterministic seasonality),
so the boundary LR is non-standard: an atom at 0 (the pile-up effect) plus a
continuous tail.  We tabulate this distribution by simulation, per frequency and n.

        LR_f = 2 [ l(r_hat) - l(r = 1) ] = (-2 l(r=1)) - min_r (-2 l(r))

The thesis (Cuadro 2.4.5) used, for f = 1..5, critical values from *linear
interpolation* between the regular MA(1) and the lag-4 seasonal MA(1)_4 of Davis
et al. -- bundling all frequencies of a lag, which is NOT a single-frequency
factor.  This module derives the correct per-frequency distribution.

Estimator: exact Gaussian ML, NOT fue
-------------------------------------
The likelihood is computed directly from the banded (pentadiagonal) covariance
matrix of the factor via a banded Cholesky -- exact, O(n), and fast.  We do NOT
use fue here: fue's exact-ML is biased for SECOND-order MA factors near the
non-invertibility boundary (it inflates the boundary likelihood, giving pile-up
~0.82 vs the correct 0.60 at f=3, n=120).  fue's regular MA(1) is fine (f=0
validates), but the seasonal 2nd-order factors -- exactly the MEG regime -- are
not.  This bias also affects ART's production MEG/DCD_f (see IPC_DE false
positives).  Cross-checks: the banded engine reproduces (i) Davis-Dunsmuir's
regular MA(1) boundary law (f=0: pile-up 0.6575, crit 1.00/1.94/4.41) and
(ii) the even/odd MA(1) decomposition of f=3 == Davis seasonal lag-2
(pile-up 0.616, both computed with the validated MA(1) innovations likelihood).
"""
from __future__ import annotations

import argparse

import numpy as np
from scipy.linalg import cholesky_banded, cho_solve_banded
from scipy.optimize import minimize_scalar

S = 12  # monthly


# ---------------------------------------------------------------------------
# Exact Gaussian -2logL (sigma^2 concentrated) for X_t = Z_t + c1 Z_{t-1} + c2 Z_{t-2}
# ---------------------------------------------------------------------------

def neg2ll(x: np.ndarray, c1: float, c2: float) -> float:
    n = x.size
    g0 = 1.0 + c1 * c1 + c2 * c2
    g1 = c1 + c1 * c2
    g2 = c2
    ab = np.zeros((3, n))            # upper banded form (u = 2)
    ab[0, 2:] = g2
    ab[1, 1:] = g1
    ab[2, :] = g0
    try:
        cb = cholesky_banded(ab, lower=False)
    except np.linalg.LinAlgError:
        return np.inf
    logdet = 2.0 * np.log(cb[-1, :]).sum()
    quad = float(x @ cho_solve_banded((cb, False), x))
    return logdet + n * np.log(quad / n)


def _coefs(f: int, r: float) -> tuple[float, float]:
    """(c1, c2) of the witness factor at modulus r for frequency f."""
    if 1 <= f <= 5:                       # 1 - 2cos(w) r B + r^2 B^2
        return -2.0 * np.cos(2 * np.pi * f / S) * r, r * r
    if f == 6:                            # Nyquist (1 + r B)
        return r, 0.0
    if f == 0:                            # regular trend (1 - r B)
        return -r, 0.0
    raise ValueError(f"frequency f={f} out of range 0..6")


def lr_one(f: int, x: np.ndarray) -> tuple[float, bool]:
    """Boundary profile LR for one realisation; returns (LR, is_atom)."""
    obj = lambda r: neg2ll(x, *_coefs(f, r))
    l_const = obj(1.0)
    res = minimize_scalar(obj, bounds=(0.02, 0.999990), method="bounded",
                          options={"xatol": 1e-6})
    return max(0.0, l_const - res.fun), bool(res.fun >= l_const - 1e-7)


# ---------------------------------------------------------------------------
# Data generation under H0 (non-invertible boundary, r = 1)
# ---------------------------------------------------------------------------

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


def simulate_lr(f: int, n: int, reps: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for i in range(reps):
        out[i], _ = lr_one(f, simulate_boundary(f, n, rng))
    return out


_LEVELS = (0.90, 0.95, 0.99)
FREQ_LABEL = {
    0: "f0  0     (1-B)  trend",
    1: "f1  pi/6  (1-V3B+B2)",
    2: "f2  pi/3  (1- B +B2)",
    3: "f3  pi/2  (1    +B2)",
    4: "f4  2pi/3 (1+ B +B2)",
    5: "f5  5pi/6 (1+V3B+B2)",
    6: "f6  pi    (1+B) Nyq",
}


def report(lr: np.ndarray, f: int, n: int) -> None:
    q = np.quantile(lr, _LEVELS)
    atom = float((lr < 1e-6).mean())
    print(f"{FREQ_LABEL.get(f, str(f)):22s} n={n:<4} reps={lr.size:<6} "
          f"pile-up={atom:.3f}  10/5/1% = {q[0]:.3f} {q[1]:.3f} {q[2]:.3f}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--freqs", type=str, default="0,1,2,3,4,5,6")
    p.add_argument("--n", type=int, default=120)
    p.add_argument("--reps", type=int, default=20000)
    p.add_argument("--seed", type=int, default=20260629)
    p.add_argument("--out", type=str, default="")
    args = p.parse_args()
    print(f"DCD/MEG boundary LR -- exact banded ML (not fue) -- n={args.n}, reps={args.reps}")
    print(f"   anchors: f0->Davis MA(1) 0.6575|1.00/1.94/4.41 ; f3->Davis s=2 0.616|1.23/2.11/4.42")
    print("-" * 78)
    saved = {}
    for f in (int(s) for s in args.freqs.split(",")):
        lr = simulate_lr(f, args.n, args.reps, seed=args.seed + f)
        report(lr, f, args.n)
        saved[f"lr_f{f}"] = lr
    if args.out:
        np.savez(args.out, n=args.n, reps=args.reps, **saved)
        print(f"saved -> {args.out}", flush=True)
