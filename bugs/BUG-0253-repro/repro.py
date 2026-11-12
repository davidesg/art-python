"""BUG-0253: with λ=1 the ω of an intervention are shown in fue's ×100 scale,
next to a σ̂ₐ already converted back to the series' units (BUG-0033 fixed σ̂ₐ
only). Effective Fed Funds rate, 1985-1995, as 100·log(1+y/100) (FRED
FEDFUNDS; Martín Manjón and Treadway 1997): in ∇ the jump of 12/1986 is
+0.8171, and the step ×2 there estimates ω₀ = 0.8171 in the series' units.
The equation prints ω₀ = 81.710 beside σ̂ₐ = 0.21966.

    python3 bugs/BUG-0253-repro/repro.py      # exits 1 while the bug is open
"""
import os, re, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
HERE = os.path.dirname(os.path.abspath(__file__))
spec = dict(lam=1.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)


def text(out):
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "") or ""
                     for x in (out if isinstance(out, (list, tuple)) else [out]))


with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "R0.inp")
    fn(M.load_data)(os.path.join(HERE, "fedfunds_1985_1995.csv"), inp, column="R0")
    base = os.path.join(tmp, "m00.inp")
    fn(M.confirm_and_estimate)(inp, base, p=0, q=0, **spec)
    out = text(fn(M.guided_intervention)(base, date="12/1986", form="step", n_omega=2,
                                         output_path=os.path.join(tmp, "m01.inp")))
eq = re.search(r"\+ \(\s*([0-9.]+)\s+−\s*([0-9.]+)·B\) ξ", out)
sig = re.search(r"σ̂ₐ = ([0-9.]+)", out)
w0, s = float(eq.group(1)), float(sig.group(1))
print(f"equation: ω₀ = {w0}   σ̂ₐ = {s}   (the ∇ jump at 12/1986 is 0.8171)")
# Same units as σ̂ₐ and the series: ω₀ ≈ 0.817. In fue's ×100 scale: 81.71.
sys.exit(1 if w0 > 10 * 0.8171 else 0)
