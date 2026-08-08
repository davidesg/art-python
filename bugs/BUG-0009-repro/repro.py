"""BUG-0009 — `dcd_overdiff_regular` overwrites the Nyquist witness and reports a
spurious `d+1`.

Both witnesses are regular MA(1) polynomials `(1 − θB)`, so in `fue` they live in the
same slot, `model.ma`. But they measure OPPOSITE roots:

    regular difference   d = (1 − B)   root at B = +1   witness θ → +1   (freq 0)
    Nyquist difference   ifadf[6] = (1 + B)   root at B = −1   witness θ → −1  (f = s/2)

`dcd_overdiff_regular` builds its over-differenced candidate with

    mc.ma = [[float(witness_init)]]        # "replace any existing regular MA"

which DELETES the Nyquist witness whenever f = s/2 has been reformulated — while
`mc.ifadf[6] = 1` survives untouched. The candidate is then left with an uncancelled
(1 + B) seasonal unit root, which the f=0 witness has to absorb: θ̂ is dragged away
from +1 and the test reports "genuine extra unit root → consider d+1" on a model whose
d is correct. Note that f = 6 is not governed by `d` at all — its integration order is
`ifadf[6]` — so the regular over-differencing test should never have touched it.

Run:  python repro.py
"""
import copy
import os

import fue

from art.formal_tests import dcd_overdiff_regular, _extract_ma_param

HERE = os.path.dirname(os.path.abspath(__file__))
CRIT = 1.94                      # DCD 5% critical value, s=1 law

# NL_CPI, CBS national CPI, 2002-01..2019-12 (n=216), lam=0, d=1, D=0.
# The three models differ ONLY in which frequencies were reformulated to stochastic.
MODELS = [
    ("D    baseline, nothing reformulated", "NL_CPI_Dsar.pre"),
    ("S23  f=2,3 reformulated  (no Nyquist)", "NL_CPI_S23.pre"),
    ("S236 f=2,3,6 reformulated (WITH Nyquist)", "NL_CPI_S236.pre"),
]


def _overdiff(model, keep_existing_ma):
    """`dcd_overdiff_regular`'s candidate, with the regular-MA slot either
    commandeered (current behaviour) or preserved (proposed fix)."""
    mc = copy.deepcopy(model)
    mc._result = None
    mc.d = int(mc.d) + 1
    mc.mu0 = 0.0
    mc.estimate_mu = False
    prev = [list(op) for op in mc.ma] if keep_existing_ma else []
    mc.ma = prev + [[0.85]]
    mc.ma_free = [[True] * len(op) for op in prev] + [[True]]
    mc.fit()
    return _extract_ma_param(mc, len(prev)), mc.ma      # the f=0 witness is LAST


print("=" * 78)
print("PART 1 — the symptom: the verdict flips when, and only when, f=6 is reformulated")
print("=" * 78)
for label, fname in MODELS:
    ts, m = fue.inp.load(os.path.join(HERE, fname))
    m.fit()
    r = dcd_overdiff_regular(m)
    verdict = "consider d+1  <-- WRONG" if r.lr >= CRIT else "d confirmed"
    print(f"{label:42}")
    print(f"    model.ma = {str(m.ma):34}  ifadf[6] = {m.ifadf[6]}")
    print(f"    theta = {r.coef_free:+.4f}   LR = {r.lr:7.3f}   ->  {verdict}\n")

print("=" * 78)
print("PART 2 — the mechanism: preserving the Nyquist witness restores theta = +1")
print("=" * 78)
ts, m = fue.inp.load(os.path.join(HERE, "NL_CPI_S236.pre"))
m.fit()
th_now, ma_now = _overdiff(m, keep_existing_ma=False)
th_fix, ma_fix = _overdiff(m, keep_existing_ma=True)
print(f"  current  mc.ma = [[0.85]]        -> candidate ma = "
      f"{[[round(c, 4) for c in o] for o in ma_now]}   theta_f0 = {th_now:+.4f}")
print(f"  proposed keep + append           -> candidate ma = "
      f"{[[round(c, 4) for c in o] for o in ma_fix]}   theta_f0 = {th_fix:+.4f}")
print("\n  Expected: current +0.7295 (spurious d+1); proposed +1.0000 (d confirmed),")
print("  matching D and S23 exactly.")
