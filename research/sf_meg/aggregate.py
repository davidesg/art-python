"""Aggregate per-frequency LR Monte Carlo draws into a seasonal critical-value table.

Reads out/lr_f{f}_n{n}.npz produced by dcd_mc.py and prints, for each seasonal
frequency, the simulated 10/5/1% critical values and the pile-up probability,
side by side with the thesis interpolation (1.07/2.02/4.52) and the regular MA(1)
anchor (1.00/1.94/4.41).
"""
from __future__ import annotations

import glob
import os

import numpy as np

LEVELS = (0.90, 0.95, 0.99)
HERE = os.path.dirname(os.path.abspath(__file__))

FREQ_LABEL = {
    1: "f1  pi/6   (1-V3 B+B2)",
    2: "f2  pi/3   (1- B +B2)",
    3: "f3  pi/2   (1    +B2)",
    4: "f4  2pi/3  (1+ B +B2)",
    5: "f5  5pi/6  (1+V3 B+B2)",
    6: "f6  pi  Nyq (1+ B)    ",
}


def main() -> None:
    files = sorted(glob.glob(os.path.join(HERE, "out", "lr_f*_n*.npz")))
    if not files:
        print("no npz files yet in out/")
        return
    print(f"{'frequency':24s} {'n':>4} {'reps':>6} {'pile-up':>8} "
          f"{'10%':>7} {'5%':>7} {'1%':>7}")
    print("-" * 72)
    rows = {}
    for fp in files:
        d = np.load(fp)
        lr = d["lr"]
        f = int(d["f"])
        n = int(d["n"])
        q = np.quantile(lr, LEVELS)
        atom = float((lr < 1e-4).mean())
        rows[f] = (n, lr.size, atom, q)
    for f in sorted(rows):
        n, reps, atom, q = rows[f]
        print(f"{FREQ_LABEL.get(f, str(f)):24s} {n:>4} {reps:>6} {atom:>8.3f} "
              f"{q[0]:>7.3f} {q[1]:>7.3f} {q[2]:>7.3f}")
    print("-" * 72)
    print(f"{'thesis interp MA_f':24s} {'':>4} {'':>6} {'':>8} "
          f"{1.07:>7.2f} {2.02:>7.2f} {4.52:>7.2f}")
    print(f"{'Davis MA(1) anchor':24s} {'':>4} {'':>6} {0.6575:>8.4f} "
          f"{1.00:>7.2f} {1.94:>7.2f} {4.41:>7.2f}")


if __name__ == "__main__":
    main()
