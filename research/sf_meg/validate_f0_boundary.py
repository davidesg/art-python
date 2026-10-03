"""Validation for art BUG-0011, item 2: the boundary likelihood ℓ(θ=1) of the
over-differencing DCD at f=0.

art's `dcd_overdiff_regular` imposes ∇^{d+1}, fits a regular MA(1) witness and
computes LR = 2[ℓ(θ̂) − ℓ(θ=1)] with fue. The paper's appendix says fue's profile
jumps exactly at the non-invertible boundary. Before replacing ℓ(θ=1) by anything,
three questions, measured on series where the exact banded engine applies (an MA
witness plus deterministic regressors, no AR):

  1. How far is fue's LR from the exact one, on the same data?
  2. Is the exact ℓ(θ=1) on ∇²y the RESTRICTED (REML) likelihood of ∇y with an
     unknown constant (Harvey's result)? If so, −2ℓ_exact(θ=1) − (−2ℓ_REML) is a
     constant that does not depend on the data: its spread across replications
     must be ~0.
  3. Under H0 (d=1 true), what is the real size of the test at the bare 5% crit
     (1.94) and at the one measured for the candidate's design (2.15), with fue's
     ℓ(θ=1) and with the exact one?

Usage:  python validate_f0_boundary.py --reps 200 --n 216
"""
from __future__ import annotations

import argparse
import warnings

import numpy as np
from scipy.optimize import minimize_scalar

import deterministic_effect as D

S = 12


def harmonics(n: int) -> np.ndarray:
    """The 11 seasonal regressors at the level: 5 cos/sin pairs and the Nyquist."""
    t = np.arange(1, n + 1)
    cols = []
    for g in range(1, 6):
        w = 2 * np.pi * g / S
        cols += [np.cos(w * t), np.sin(w * t)]
    cols.append((-1.0) ** t)
    return np.column_stack(cols)


def simulate_h0(n, rng, mu=0.3, amp=1.0):
    """d=1 true: y = cumsum(mu + a) + a deterministic seasonal of amplitude amp."""
    H = harmonics(n)
    beta = rng.normal(0, amp, H.shape[1])
    return np.cumsum(mu + rng.standard_normal(n)) + H @ beta


def exact_lr(y):
    """Exact banded LR on ∇²y with the regressors ∇²H; also −2ℓ at θ=1."""
    H = harmonics(len(y))
    x2 = np.diff(y, 2)
    Z2 = np.diff(H, 2, axis=0)
    obj = lambda r: D.neg2ll_reg(x2, -r, 0.0, Z2)
    at1 = obj(1.0)
    res = minimize_scalar(obj, bounds=(0.02, 0.99999), method="bounded",
                          options={"xatol": 1e-7})
    return max(0.0, at1 - res.fun), at1, 1 - (res.x if res.fun < at1 else 1.0)


def reml_neg2ll(y):
    """−2ℓ REML (σ² concentrated) of ∇y = c + ∇H·β + e, e white noise."""
    H = harmonics(len(y))
    x1 = np.diff(y)
    X = np.column_stack([np.ones(len(x1)), np.diff(H, axis=0)])
    m, k = X.shape
    beta, *_ = np.linalg.lstsq(X, x1, rcond=None)
    rss = float(((x1 - X @ beta) ** 2).sum())
    _, logdet = np.linalg.slogdet(X.T @ X)
    return (m - k) * np.log(rss / (m - k)) + logdet


def fue_lr(y):
    """What art computes: fue, candidate d=2 with the harmonics, MA witness."""
    import fue
    n = len(y)
    ts = fue.TimeSeries(data=y.tolist(), freq=S, start=[2000, 1], name="SIM")

    def itvs():
        out = []
        for g in range(1, 6):
            out.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True],
                                        harmonic=float(g)))
            out.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True],
                                        harmonic=float(g)))
        out.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))
        return out

    def fit(ma, free):
        m = fue.Model(ts, d=2, D=0, boxlam=1.0, refactor=1.0, ma=[[ma]],
                      ma_free=[[free]], ar=[], ar_free=[], ar_s=[], ma_s=[],
                      interventions=itvs(), ifadf=[0] * 7, mu=0.0,
                      estimate_mu=False)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m.fit()
        return float(m._result.loglik)

    lf, lc = fit(0.85, True), fit(1.0, False)
    return 2.0 * (lf - lc)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reps", type=int, default=200)
    p.add_argument("--n", type=int, default=216)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()
    rng = np.random.default_rng(a.seed)
    lr_ex, lr_fue, gap, dist = [], [], [], []
    for _ in range(a.reps):
        y = simulate_h0(a.n, rng)
        lx, at1, d1 = exact_lr(y)
        lr_ex.append(lx)
        lr_fue.append(fue_lr(y))
        gap.append(at1 - reml_neg2ll(y))
        dist.append(d1)
    lr_ex, lr_fue, gap = map(np.asarray, (lr_ex, lr_fue, gap))
    print(f"H0 (d=1 true), n={a.n}, reps={a.reps}, 11 harmonics, no AR")
    print(f"1. LR fue − LR exact: mean {np.mean(lr_fue - lr_ex):+.3f}, "
          f"median {np.median(lr_fue - lr_ex):+.3f}, "
          f"max |diff| {np.max(np.abs(lr_fue - lr_ex)):.3f}")
    holds = gap.std() < 1e-6
    print(f"2. −2ℓ_exact(θ=1) − (−2ℓ_REML): mean {gap.mean():+.4f}, "
          f"sd {gap.std():.2e}  → the REML identity "
          + ("HOLDS (constant across replications)" if holds else
             "does NOT hold as written (it varies with the data)"))
    print("3. size (rejection rate under H0):")
    for c in (1.94, 2.15):
        print(f"   crit {c:.2f}: fue {np.mean(lr_fue > c):.3f}   "
              f"exact {np.mean(lr_ex > c):.3f}   (nominal 0.05)")
    print(f"   pile-up (LR≈0): fue {np.mean(lr_fue < 1e-6):.3f}   "
          f"exact {np.mean(lr_ex < 1e-6):.3f}")


if __name__ == "__main__":
    main()
