#!/usr/bin/env python3
"""BUG-0258: with lambda = 1 the equation prints mu and the harmonics' omegas on
fue's x100 scale, next to a sigma_a already back in the series' units.

BUG-0033 divided sigma_a by refactor and BUG-0253 the interventions' omegas;
mu, the cos/sin/alter coefficients and the diagnosis's "residual mean" were left
on the scale fue estimates in (refactor * y).

Synthetic monthly series about 100 in levels: an AR(1) of sd 1, plus a cosine of
amplitude 2 at the annual frequency. art estimates it with lambda = 1, mu and
one harmonic pair, and prints the equation. Exits 1 while mu reads ~10 000 (or
the cosine's coefficient ~200) next to sigma_a ~1; 0 when all are in the units
of the series.
"""
import os
import re
import sys
import tempfile

import numpy as np

import art.mcp_server as A


def serie(n=160, seed=7):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.6 * e[t - 1] + rng.normal(0, 1.0)
    t = np.arange(1, n + 1)
    return 100.0 + e + 2.0 * np.cos(2 * np.pi * t / 12)


def main():
    y = serie()
    with tempfile.TemporaryDirectory() as d:
        inp = os.path.join(d, "NIVELES.inp")
        A.create_inp(list(map(float, y)), inp, name="NIVELES", freq=12)
        r = A.confirm_and_estimate(inp, os.path.join(d, "NIVELES_m.inp"), lam=1.0,
                                   d=0, D=0, p=1, q=0, n_harmonics=1,
                                   seasonal=True, estimate_mu=True)
    txt = "\n".join(str(getattr(c, "text", c)) for c in r)
    mu = float(re.search(r"Nₜ [−+] ([0-9.]+)\)", txt).group(1))
    sigma = float(re.search(r"σ̂ₐ = ([0-9.]+)", txt).group(1))
    cos = re.search(r"([−+]?\s*[0-9.]+)\s*cos\(", txt)
    cos = abs(float(cos.group(1).replace("−", "-").replace(" ", ""))) if cos else float("nan")
    print(f"series mean {y.mean():.2f}, innovation sd 1, cosine amplitude 2")
    print(f"equation:   mu = {mu:g}   cos coefficient = {cos:g}   sigma_a = {sigma:g}")
    abierto = mu > 10 * y.mean() or cos > 20
    print("mu / the harmonic are on the x100 scale" if abierto else "all in the series' units")
    return 1 if abierto else 0


if __name__ == "__main__":
    sys.exit(main())
