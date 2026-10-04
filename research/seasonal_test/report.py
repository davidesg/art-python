"""BUG-0206 — tables from results/*.npz (written by study.py).

  1. SIZE: rejection rate at 5% under H0, by candidate, dynamic and n.
  2. POWER (raw): rejection rate at 5% under H1, by candidate, dynamic,
     amplitude and shape, for one n.
  3. POWER (size-adjusted): with each candidate's own 95% quantile under H0
     in that cell as critical value, so an oversized test does not look
     powerful for the wrong reason.
  4. A summary per candidate: worst and median size over the cells, and the
     mean size-adjusted and raw power.

    python report.py [--n 216] [--md out.md]
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np

import study as S

HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    data = {}
    for f in glob.glob(os.path.join(HERE, "results", "*.npz")):
        z = np.load(f)
        dyn, n = os.path.basename(f)[:-4].rsplit("_n", 1)
        data[(dyn, int(n))] = {k: z[k] for k in z.files}
    return data


def rate(p):
    p = p[~np.isnan(p)]
    return float(np.mean(p < 0.05)) if p.size else float("nan")


def adj_power(h0, h1):
    h0 = h0[~np.isnan(h0)]
    h1 = h1[~np.isnan(h1)]
    if not h0.size or not h1.size:
        return float("nan")
    return float(np.mean(h1 > np.quantile(h0, 0.95)))


def fmt(v):
    return "  —  " if v != v else f"{v:5.3f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=216)
    ap.add_argument("--md", default="")
    a = ap.parse_args()
    D = load()
    names = [str(x) for x in next(iter(D.values()))["names"]]
    dyns = [d for d in list(S.DYN) + list(S.SEASONAL_AR) if any(k[0] == d for k in D)]
    L = []
    w = max(len(d) for d in dyns) + 2

    L.append("## 1. Size: rejection rate at 5% under H0 (no deterministic seasonality)\n")
    for n in S.NS:
        L.append(f"n = {n}\n")
        L.append("| dynamic | " + " | ".join(names) + " |")
        L.append("|---|" + "---|" * len(names))
        for d in dyns:
            if (d, n) not in D:
                continue
            p = D[(d, n)]["h0_p"]
            L.append(f"| {d} | " + " | ".join(fmt(rate(p[i])) for i in range(len(names))) + " |")
        L.append("")

    for kind in ("raw", "adj"):
        title = ("Power (raw), rejection rate at 5%" if kind == "raw" else
                 "Power, size-adjusted (critical value = own 95% quantile under H0)")
        L.append(f"## {2 if kind == 'raw' else 3}. {title}, n = {a.n}\n")
        for shape in S.SHAPES:
            for amp in S.AMPS:
                L.append(f"pattern {shape}, amplitude {amp} x sd(w)\n")
                L.append("| dynamic | " + " | ".join(names) + " |")
                L.append("|---|" + "---|" * len(names))
                for d in S.DYN:
                    if (d, a.n) not in D:
                        continue
                    z = D[(d, a.n)]
                    vals = []
                    for i in range(len(names)):
                        h1p = z[f"h1_{shape}_{amp}_p"][i]
                        h1s = z[f"h1_{shape}_{amp}_stat"][i]
                        vals.append(rate(h1p) if kind == "raw"
                                    else adj_power(z["h0_stat"][i], h1s))
                    L.append(f"| {d} | " + " | ".join(fmt(v) for v in vals) + " |")
                L.append("")

    L.append("## 4. Summary per candidate (all n, the ARMA dynamics)\n")
    L.append("| candidate | worst size | median size | cells with size > 0.075 "
             "| mean raw power | mean size-adj. power |")
    L.append("|---|---|---|---|---|---|")
    for i, nm in enumerate(names):
        sz, rp, ap_ = [], [], []
        for (d, n), z in D.items():
            if d in S.SEASONAL_AR:
                continue
            sz.append(rate(z["h0_p"][i]))
            for shape in S.SHAPES:
                for amp in S.AMPS:
                    rp.append(rate(z[f"h1_{shape}_{amp}_p"][i]))
                    ap_.append(adj_power(z["h0_stat"][i], z[f"h1_{shape}_{amp}_stat"][i]))
        sz = np.array(sz)
        L.append(f"| {nm} | {np.nanmax(sz):.3f} | {np.nanmedian(sz):.3f} | "
                 f"{int(np.sum(sz > 0.075))}/{int(np.sum(~np.isnan(sz)))} | "
                 f"{np.nanmean(rp):.3f} | {np.nanmean(ap_):.3f} |")
    txt = "\n".join(L)
    print(txt)
    if a.md:
        open(a.md, "w").write(txt + "\n")


if __name__ == "__main__":
    main()
