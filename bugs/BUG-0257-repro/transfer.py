#!/usr/bin/env python3
"""BUG-0257, what it costs downstream (needs drtran): mtram's transfer estimate
with lambda = -1 on series about 10 000, with art's refactor = 100 and with a
factor that puts the transformed series' spread near 1.

Two synthetic series, Y_t = 0.5 Y_{t-1} + 0.4 X_{t-1} + a_t in logs (1 % and
0.5 %), each fitted by fue as an AR(1) with mu and written as a .pre; then
load_pre, a link X -> Y with b = 1, and estimate. Prints the status and the
gain. Not part of the exit code: repro.py is.
"""
import os
import sys
import tempfile
import warnings

import numpy as np

import fue
from fue.forecast import _boxcox
import drtran.mcp_server as M

warnings.filterwarnings("ignore")


def pares(nivel, n=160, seed=11):
    rng = np.random.default_rng(seed)
    e, x = np.zeros(n), np.zeros(n)
    for t in range(1, n):
        x[t] = 0.6 * x[t - 1] + rng.normal(0, 0.01)
    for t in range(1, n):
        e[t] = 0.5 * e[t - 1] + 0.4 * x[t - 1] + rng.normal(0, 0.005)
    return nivel * np.exp(e), nivel * np.exp(x)


def corre(ref, lam=-1.0, nivel=1e4):
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for nm, s in zip(("Y", "X"), pares(nivel)):
            ts = fue.TimeSeries(list(map(float, s)), freq=12, start=(2000, 1), name=nm)
            w = np.array([_boxcox(float(v), lam, ref) for v in s])
            m = fue.Model(ts, d=0, D=0, boxlam=lam, ar=[[0.1]], ar_free=[[True]],
                          mu=float(w.mean()), estimate_mu=True, refactor=ref)
            m.fit()
            p = os.path.join(d, f"{nm}.pre")
            m.write_pre(p)
            paths.append(p)
        name = f"r{ref:g}"
        M.load_pre(name, ", ".join(paths))
        M.set_network(name, '[{"out":0,"inp":1,"b":1,"r":0,"s":0}]')
        out = M.estimate(name)
    for l in out.splitlines():
        if "status" in l or "GANANCIA" in l or "GAIN" in l:
            print(f"  refactor={ref:<9g}{l.strip()}")


if __name__ == "__main__":
    corre(100.0)
    corre(1e6)
    sys.exit(0)
