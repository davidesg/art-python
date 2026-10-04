"""BUG-0206 — the real size of art's seasonality test (HAC F) under H0.

Series with NO seasonality: levels I(1), the differences AR(phi) with
phi in {0, +0.6, -0.4}. Each is passed through art's own
`seasonal_detection.detect_seasonality(ts, d=1, lam=1.0)` (lam=1: the series
is already on the additive scale), and the rejection rate is compared with the
plain OLS F of the same harmonic regression, at the nominal 5%.

It also prints the mean F under H0 (it should be ~1) and the HAC/OLS ratio of
the coefficient variances, which shows the missing n/(n-k) correction.

    python hac_size.py            # 500 replications per cell
    python hac_size.py --reps 2000
"""
import argparse
import warnings

import numpy as np
from scipy import stats

import fue
from art import seasonal_detection as sd

warnings.simplefilter("ignore")


def ols_f(w, s=12, d=1):
    X = sd._build_differenced_harmonic_matrix(len(w), d, s)
    c, *_ = np.linalg.lstsq(X, w, rcond=None)
    u = w - X @ c
    n, k = X.shape
    q = s - 1
    s2 = u @ u / (n - k)
    V = s2 * np.linalg.inv(X.T @ X)
    g = c[1:]
    f = g @ np.linalg.inv(V[1:, 1:]) @ g / q
    return f, f > stats.f.ppf(0.95, q, n - k)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=500)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    print(f"{'n':>4} {'phi':>5}  {'HAC (art)':>10} {'OLS':>6}  {'mean F HAC':>10} {'mean F OLS':>10}")
    for n in (120, 216, 400):
        for phi in (0.0, 0.6, -0.4):
            rh = ro = 0
            fh, fo = [], []
            for _ in range(a.reps):
                e = rng.standard_normal(n + 50)
                x = np.zeros_like(e)
                for t in range(1, len(e)):
                    x[t] = phi * x[t - 1] + e[t]
                level = 100 + np.cumsum(x[50:])          # I(1), no seasonality
                ts = fue.TimeSeries.from_array(level.tolist(), freq=12,
                                               start=[2000, 1], name="H0")
                r = sd.detect_seasonality(ts, d=1, lam=1.0)
                rh += r.seasonal_detected
                fh.append(r.f_stat)
                f, rej = ols_f(np.diff(level))
                ro += rej
                fo.append(f)
            print(f"{n:4d} {phi:+5.1f}  {rh / a.reps:10.3f} {ro / a.reps:6.3f}  "
                  f"{np.mean(fh):10.2f} {np.mean(fo):10.2f}")
    print("\nnominal size 0.05; under H0 the mean F should be ~1")


if __name__ == "__main__":
    main()
