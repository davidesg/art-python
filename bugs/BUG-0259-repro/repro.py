#!/usr/bin/env python3
"""BUG-0259: art seeds mu with sign(y)|y|**lambda, and fue transforms with
(y**lambda - 1)/lambda: for lambda not 0 or 1 the seed is in another space and
fue falls into BUG-0001's degenerate optimum.

`pipeline._mu_seed` exists so that mu does not start far from the data
(BUG-0001: an AR root at 1 absorbs the level). It transforms with
sign(y)|y|**lambda; fue (`fue.forecast._boxcox`, the C's transform) with
(y**lambda - 1)/lambda. With lambda = -1 and a series about 100 the seed is
~1 and the series fue fits sits at ~99.

A synthetic AR(1) of 1 % in logs, about 100; art's confirm_and_estimate with
lambda = -1, d = 0, AR(1) and mu. The same model seeded at the mean of what fue
fits is the reference. Exits 1 while art's fit is the degenerate one (phi at 1,
log-likelihood well below the reference); 0 when both agree.
"""
import os
import sys
import tempfile
import warnings

import numpy as np

import fue
from fue.forecast import _boxcox
import art.mcp_server as A
from art.pipeline import _mu_seed

warnings.filterwarnings("ignore")


def serie(n=160, seed=3):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.6 * e[t - 1] + rng.normal(0, 0.01)
    return 100.0 * np.exp(e)


def main():
    lam = -1.0
    y = serie()
    ts = fue.TimeSeries(list(map(float, y)), freq=12, start=(2000, 1), name="Y")
    w = np.array([_boxcox(float(v), lam, 100.0) for v in y])
    print(f"lambda={lam:g}: art's mu seed = {_mu_seed(ts, lam, 0, 0, True):.5g}; "
          f"mean of the series fue fits = {w.mean():.5g}")
    with tempfile.TemporaryDirectory() as d:
        A.create_inp(list(map(float, y)), os.path.join(d, "Y.inp"), name="Y", freq=12)
        A.confirm_and_estimate(os.path.join(d, "Y.inp"), os.path.join(d, "Y_m.inp"),
                               lam=lam, d=0, D=0, p=1, q=0, n_harmonics=0,
                               seasonal=False, estimate_mu=True)
        _, m = fue.load(os.path.join(d, "Y_m.inp"))
        m.fit()
    ref = fue.Model(ts, d=0, D=0, boxlam=lam, ar=[[0.1]], ar_free=[[True]],
                    mu=float(w.mean()), estimate_mu=True, refactor=100.0)
    ref.fit()
    phi, ll = m._result.params[0], m.loglik
    phi_r, ll_r = ref._result.params[0], ref.loglik
    print(f"art:          phi = {phi:.4f}  logL = {ll:.3f}")
    print(f"well seeded:  phi = {phi_r:.4f}  logL = {ll_r:.3f}")
    abierto = ll < ll_r - 1.0
    print("art lands in the degenerate optimum" if abierto else "art reaches the optimum")
    return 1 if abierto else 0


if __name__ == "__main__":
    sys.exit(main())
