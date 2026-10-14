"""BUG-0250: confirm_and_estimate with base_pre_path and p=0, q=0 keeps the
base's AR instead of removing it.  Minneapolis (flour_prices.csv, the
lutkepohl_poskitt example of sima): m04 = AR(1) + two steps from 12/1973;
chaining p=0, q=0 from m04.pre should give the (0,1,0) with the steps.

    python3 bugs/BUG-0250-repro/repro.py      # exits 1 while the bug is open
"""
import os, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
spec = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)
with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "Minneapolis.inp")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Minneapolis")
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"), p=1, q=0, **spec)
    fn(M.guided_intervention)(os.path.join(tmp, "m02.pre"), date="12/1973", form="step",
                              n_omega=2, output_path=os.path.join(tmp, "m04.inp"))
    out = txt(fn(M.confirm_and_estimate)(os.path.join(tmp, "m04.inp"), os.path.join(tmp, "m05.inp"),
                                         base_pre_path=os.path.join(tmp, "m04.pre"),
                                         p=0, q=0, estimate_mu=False))
eq = [l for l in out.splitlines() if "∇Nₜ" in l]
print("m05 (asked p=0, q=0):", eq[0].strip() if eq else "?")
kept = any("B)" in l and "(1 −" in l for l in eq)
print("the AR(1) of the base is still there:", kept)
sys.exit(1 if kept else 0)
