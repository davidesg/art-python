"""
BUG-0006 reproduction — the default seasonal-AR seed (positive) sends the US-CPI
AR(2)x(2,0,0)_12 model to a SPURIOUS optimum under fue>=0.1.7: mu collapses to an
absurd value, the seasonal AR flips sign, sigma_a jumps, AIC is ~100 worse -- yet the
fit reports converged=True / ifault=0 with no diagnostic. Passing the identified
(negative) seasonal-AR seed reaches the correct optimum (paper Table 2).

Run from this folder:  python repro.py
Needs: fue (>=0.1.7 to see the bug; fue 0.1.3 converges correctly with either seed)
       and art (for art.pipeline._make_model).

The US CPI series (monthly, 2002:01-2026:05, n=293) is embedded in US_CPI.pre; we
load it from there so the repro is self-contained.
"""
import numpy as np
import fue
from art.pipeline import _make_model

ld = fue.load("US_CPI.pre")
ts = ld[0] if isinstance(ld, tuple) else ld.series          # US CPI series
SPEC = dict(lam=0.0, d=1, D=0, p=2, q=0, n_harmonics=5, P=2, Q=0, estimate_mu=True)


def report(tag, m):
    r = m._result
    p = np.asarray(r.params, float)
    phi, mu = p[-5:-1], p[-1]
    sigma_a = 100.0 * np.sqrt(r.sigma2)                     # residual scale, log*100 units
    print(f"{tag:16s} | Phi seed {str(m_seed):>16s} -> "
          f"phi_hat={np.round(phi,3).tolist()}  mu_hat={mu:+.4f}  "
          f"sigma_a={sigma_a:.4f}  AIC={r.aic:.1f}  "
          f"converged={r.converged} ifault={r.ifault}")


# (1) default seed -> spurious optimum
m1 = _make_model(ts, **SPEC)
m_seed = m1.ar_s                                             # what _make_model chose (positive)
m1.fit()
report("default seed", m1)

# (2) identified seed (negative Phi) -> correct optimum, paper Table 2
m2 = _make_model(ts, **SPEC)
m2.ar = [[0.60, -0.17]]
m2.ar_s = [[-0.11, -0.09]]
m_seed = m2.ar_s
m2.fit()
report("identified seed", m2)

print("\nExpected under fue>=0.1.7:")
print("  default seed  -> mu_hat ~ -0.14, sigma_a ~ 0.305, AIC ~ -2511  (SPURIOUS, but converged=True)")
print("  identified    -> mu_hat ~  0.00, sigma_a ~ 0.261, AIC ~ -2613  (paper Table 2 US row)")
print("  => a ~100-AIC / -0.04-sigma gap between two 'converged' fits of the same spec = the bug.")
