#!/usr/bin/env python3
"""BUG-0257: art writes refactor=100 whatever lambda and the size of the series,
and never checks that what the optimiser receives is in the band it works in.

fue estimates on refactor * BoxCox_lambda(y). With logs, x100 always lands in
the band (the suite's corpus: 0.29 to 39). Outside logs the size goes as
100 * cv * level**lambda:

- lambda = 1 and a series about 10 000: a spread of ~12 000;
- lambda = -1 and a series about 10 000: ~1e-4. sima's VARMA never leaves its
  start and reports LR = 0 (sima BUG-0011); mtram's transfer is marginal
  (transfer.py, next to this file, needs drtran).

Two synthetic series (an AR(1) of 1 % in logs), each estimated by art's
confirm_and_estimate with lambda fixed (the analyst's lambda; art's own
policy only proposes 0 or 1). For each, the spread of the series fue
optimises, sd(refactor * BoxCox(y)), must fall in [0.1, 1000] -- the band
measured on fue, drtran and drvarma (study of 2026-11-15) -- or art must say
it cannot put it there. Exits 1 while art's factor leaves it outside in
silence; 0 when it does not.
"""
import os
import sys
import tempfile

import numpy as np

import fue
from fue.forecast import _boxcox
import art.mcp_server as A


def serie(nivel, n=160, seed=3):
    rng = np.random.default_rng(seed)
    e = np.zeros(n)
    for t in range(1, n):
        e[t] = 0.6 * e[t - 1] + rng.normal(0, 0.01)
    return nivel * np.exp(e)


def main():
    abierto = False
    with tempfile.TemporaryDirectory() as d:
        for nombre, nivel, lam in (("NIVELES", 1e4, 1.0), ("RECIPROCA", 1e4, -1.0)):
            inp = os.path.join(d, f"{nombre}.inp")
            A.create_inp(list(map(float, serie(nivel))), inp, name=nombre, freq=12)
            A.confirm_and_estimate(inp, os.path.join(d, f"{nombre}_m.inp"), lam=lam,
                                   d=0, D=0, p=1, q=0, n_harmonics=0,
                                   seasonal=False, estimate_mu=True)
            ts, m = fue.load(os.path.join(d, f"{nombre}_m.inp"))
            w = np.array([_boxcox(float(v), m.boxlam, m.refactor) for v in ts.data])
            sd = float(w.std())
            ok = 0.1 <= sd <= 1000.0
            abierto |= not ok
            print(f"{nombre}: level ~{nivel:g}, lambda={m.boxlam:g}, refactor={m.refactor:g}"
                  f" -> sd of the series fue optimises = {sd:.3g}"
                  f"  {'ok' if ok else 'OUT of [0.1, 1000]'}")
    return 1 if abierto else 0


if __name__ == "__main__":
    sys.exit(main())
