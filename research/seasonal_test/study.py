"""BUG-0206 — size and power of six tests of deterministic seasonality.

Monthly (s=12) series whose regular differences w follow one of the dynamics
below; under H0 there is no seasonal pattern, under H1 a deterministic one
(in the level, so w carries its difference) of amplitude a x sd(w). Every
candidate of `candidates.py` sees the same series.

  size:  every dynamic (and a stochastic seasonal AR, H0 for a DETERMINISTIC
         test), n in {120, 216, 400}.
  power: every dynamic, n in {120, 216, 400}, a in {0.1, 0.2, 0.3, 0.4}, the
         pattern concentrated in the annual cycle or spread over all the
         harmonics. Common random numbers: the same innovations for every a.

Results in results/*.npz; `report.py` turns them into tables.

    python study.py --reps 2000 --reps-power 500 --reps-lr 400 --reps-lr-power 200
"""
from __future__ import annotations

import argparse
import hashlib
import math
import os
import time
from multiprocessing import Pool

import numpy as np
from scipy.signal import lfilter

import candidates as C

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "results")

# w_t = sum phi_i w_{t-i} + e_t - sum theta_j e_{t-j}   (Box-Jenkins signs)
DYN = {
    "wn":            ([], []),
    "ar1+0.6":       ([0.6], []),
    "ar1-0.6":       ([-0.6], []),
    "ar1+0.9":       ([0.9], []),
    "ar2_real":      ([0.5, 0.3], []),
    # complex roots r=0.8: the spectral peak AT a seasonal frequency (period
    # 6, harmonic 2) and BETWEEN them (period 9)
    "ar2_cplx_seas": ([2 * 0.8 * math.cos(math.pi / 3), -0.64], []),
    "ar2_cplx_off":  ([2 * 0.8 * math.cos(2 * math.pi / 9), -0.64], []),
    "ar3_a":         ([0.4, 0.2, 0.2], []),
    "ar3_b":         ([0.5, -0.3, 0.3], []),
    "ma1+0.5":       ([], [0.5]),
    "ma1-0.5":       ([], [-0.5]),
    "ma1+0.9":       ([], [0.9]),
    "arma11_a":      ([0.7], [0.4]),
    "arma11_b":      ([-0.5], [0.3]),
    "arma21_a":      ([2 * 0.8 * math.cos(math.pi / 3), -0.64], [0.3]),
    "arma21_b":      ([0.5, 0.2], [-0.4]),
}
SEASONAL_AR = {"sar1+0.5": 0.5}          # w_t = 0.5 w_{t-12} + e_t (H0 only)
NS = (120, 216, 400)
AMPS = (0.1, 0.2, 0.3, 0.4)
SHAPES = ("annual", "spread")
BURN = 300


def _check_stationary():
    for k, (ar, ma) in DYN.items():
        if ar:
            r = np.roots(np.r_[1.0, -np.asarray(ar)][::-1])
            assert np.all(np.abs(r) > 1.0), (k, np.abs(r))
        if ma:
            r = np.roots(np.r_[1.0, -np.asarray(ma)][::-1])
            assert np.all(np.abs(r) > 1.0), (k, np.abs(r))


def _sd_arma(ar, ma, m=5000):
    """Theoretical sd of the ARMA with unit innovations (psi weights)."""
    imp = np.zeros(m)
    imp[0] = 1.0
    psi = lfilter(np.r_[1.0, -np.asarray(ma)], np.r_[1.0, -np.asarray(ar)], imp)
    return float(np.sqrt(np.sum(psi ** 2)))


def _pattern(n, shape):
    """The level pattern P_t (periodic, s=12) and its difference, the latter
    scaled to unit sd. Phases fixed, so every replication sees the same
    pattern."""
    t = np.arange(n + 1)
    if shape == "annual":
        P = np.cos(2 * np.pi * t / 12 + 0.7)
    else:
        rng = np.random.default_rng(20261004)
        ph = rng.uniform(0, 2 * np.pi, 6)
        P = sum(np.cos(2 * np.pi * k * t / 12 + ph[k - 1]) for k in range(1, 7))
    dP = np.diff(P)
    return dP / dP.std()


def _seed(*key):
    h = hashlib.sha256(repr(key).encode()).digest()
    return int.from_bytes(h[:8], "little")


def _series(dyn, n, rng):
    e = rng.standard_normal(n + BURN)
    if dyn in SEASONAL_AR:
        a = np.zeros(13)
        a[0], a[12] = 1.0, -SEASONAL_AR[dyn]
        w = lfilter([1.0], a, e)
    else:
        ar, ma = DYN[dyn]
        w = lfilter(np.r_[1.0, -np.asarray(ma)], np.r_[1.0, -np.asarray(ar)], e)
    return w[BURN:]


def _orders(dyn):
    if dyn in SEASONAL_AR:
        return (12, 0)
    ar, ma = DYN[dyn]
    return (len(ar), len(ma))


def run_cell(args):
    """One (dyn, n) cell: H0 and every (shape, amp), the same innovations."""
    dyn, n, R, Rp, Rlr, Rlrp = args
    X = C.design(n)
    names = list(C.CHEAP) + ["lr"]
    rng = np.random.default_rng(_seed(dyn, n))
    base = [_series(dyn, n, rng) for _ in range(max(R, Rp))]
    out = {"dyn": dyn, "n": n}
    h0 = np.full((len(names), R), np.nan)
    p0 = np.full((len(names), R), np.nan)
    for r in range(R):
        w = base[r]
        for i, nm in enumerate(C.CHEAP):
            h0[i, r], p0[i, r] = C.CHEAP[nm](w, X)
        if r < Rlr and dyn not in SEASONAL_AR:
            h0[-1, r], p0[-1, r] = C.lr_fue(w, _orders(dyn))
    out["h0_stat"], out["h0_p"] = h0, p0
    if dyn in SEASONAL_AR:
        return out
    sdw = _sd_arma(*DYN[dyn])
    for shape in SHAPES:
        dP = _pattern(n, shape)
        for a in AMPS:
            st = np.full((len(names), Rp), np.nan)
            pv = np.full((len(names), Rp), np.nan)
            for r in range(Rp):
                w = base[r] + a * sdw * dP
                for i, nm in enumerate(C.CHEAP):
                    st[i, r], pv[i, r] = C.CHEAP[nm](w, X)
                if r < Rlrp:
                    st[-1, r], pv[-1, r] = C.lr_fue(w, _orders(dyn))
            out[f"h1_{shape}_{a}_stat"], out[f"h1_{shape}_{a}_p"] = st, pv
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=2000)
    ap.add_argument("--reps-power", type=int, default=500)
    ap.add_argument("--reps-lr", type=int, default=400)
    ap.add_argument("--reps-lr-power", type=int, default=200)
    ap.add_argument("--procs", type=int, default=4)
    ap.add_argument("--only", default="", help="comma-separated dynamics")
    a = ap.parse_args()
    _check_stationary()
    os.makedirs(OUT, exist_ok=True)
    dyns = list(DYN) + list(SEASONAL_AR)
    if a.only:
        dyns = [d for d in dyns if d in a.only.split(",")]
    cells = [(d, n, a.reps, a.reps_power, a.reps_lr, a.reps_lr_power)
             for d in dyns for n in NS]
    t0 = time.time()
    with Pool(a.procs) as pool:
        for k, res in enumerate(pool.imap_unordered(run_cell, cells), 1):
            np.savez_compressed(os.path.join(OUT, f"{res['dyn']}_n{res['n']}.npz"),
                                names=np.array(list(C.CHEAP) + ["lr"]),
                                **{kk: v for kk, v in res.items()
                                   if kk not in ("dyn", "n")})
            print(f"[{k}/{len(cells)}] {res['dyn']} n={res['n']}  "
                  f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
