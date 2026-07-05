"""Convergence of the seasonal DCD/MEG critical values in the sample size n.

Reads out/table_n{n}.npz (produced by dcd_mc.py) and prints, per frequency, the
pile-up and 10/5/1% critical values across the available n, so the approach to the
asymptotic (Davis) values is visible.  Also prints the mean over the complex
frequencies f1..f5 (which share a common law) and the thesis interpolation.
"""
from __future__ import annotations

import glob
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
LEVELS = (0.90, 0.95, 0.99)
LAB = {0: "f0 (1-B)", 1: "f1", 2: "f2", 3: "f3 (1+B2)", 4: "f4", 5: "f5",
       6: "f6 Nyq"}


def _crit(lr):
    return float((lr < 1e-6).mean()), np.quantile(lr, LEVELS)


def main():
    tables = {}
    for fp in glob.glob(os.path.join(HERE, "out", "table_n*.npz")):
        n = int(re.search(r"table_n(\d+)", fp).group(1))
        tables[n] = np.load(fp)
    if not tables:
        print("no table_n*.npz files yet")
        return
    ns = sorted(tables)
    print(f"DCD/MEG seasonal critical values vs n   (n in {ns})")
    print(f"{'freq':10s} {'n':>5} {'pileup':>7} {'10%':>7} {'5%':>7} {'1%':>7}")
    print("-" * 50)
    complex_pool = {n: [] for n in ns}
    for f in range(7):
        for n in ns:
            key = f"lr_f{f}"
            if key not in tables[n]:
                continue
            atom, q = _crit(tables[n][key])
            print(f"{LAB[f]:10s} {n:>5} {atom:>7.3f} {q[0]:>7.3f} {q[1]:>7.3f} {q[2]:>7.3f}")
            if 1 <= f <= 5:
                complex_pool[n].append(tables[n][key])
        print()
    print("=" * 50)
    print("POOLED complex frequencies f1..f5:")
    print(f"{'':10s} {'n':>5} {'pileup':>7} {'10%':>7} {'5%':>7} {'1%':>7}")
    for n in ns:
        if complex_pool[n]:
            lr = np.concatenate(complex_pool[n])
            atom, q = _crit(lr)
            print(f"{'pooled':10s} {n:>5} {atom:>7.3f} {q[0]:>7.3f} {q[1]:>7.3f} {q[2]:>7.3f}")
    print("-" * 50)
    print(f"{'Davis MA(1)':10s} {'inf':>5} {0.6575:>7.4f} {1.00:>7.2f} {1.94:>7.2f} {4.41:>7.2f}")
    print(f"{'thesis itp':10s} {'?':>5} {'':>7} {1.07:>7.2f} {2.02:>7.2f} {4.52:>7.2f}")


if __name__ == "__main__":
    main()
