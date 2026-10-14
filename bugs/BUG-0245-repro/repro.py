"""BUG-0245: confirm_and_estimate with base_pre_path silently ignores
n_harmonics/seasonal.  GDPDEC (Ecuador's GDP deflator): m02 = step×2 in
2008Q4; chaining p=2 with seasonal=True, n_harmonics=2 must add the
deterministic harmonics (quarterly: cos 1, sin 1, alter) and reach the
hand-built specification (GDPDEC_armonicos_a_mano.pre, ℓ = −140.69).
Before the fix both calls (with and without harmonics) wrote the same file.

    PYTHONPATH=src python3 bugs/BUG-0245-repro/repro.py   # exits 1 while open
"""
import os, sys, tempfile, warnings
os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.simplefilter("ignore")
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
HERE = os.path.dirname(os.path.abspath(__file__))
base = os.path.join(HERE, "GDPDEC_m02_s0804x2.pre")
kw = dict(base_pre_path=base, lam=0, d=1, D=0, p=2, q=0, estimate_mu=True)
with tempfile.TemporaryDirectory() as tmp:
    h, n = os.path.join(tmp, "h.inp"), os.path.join(tmp, "n.inp")
    fn(M.confirm_and_estimate)(base, h, seasonal=True, n_harmonics=2, **kw)
    fn(M.confirm_and_estimate)(base, n, **kw)
    iguales = open(h).read() == open(n).read()
    _, mh = M._load_fitted(h)
tipos = sorted(f"{i.type} {int(i.harmonic)}" if i.type in ("cos", "sin")
               else i.type for i in mh.interventions)
ll = float(mh.loglik)
print("with harmonics == without:", iguales)
print("deterministics:", tipos, f"· ℓ = {ll:.2f} (by hand: −140.69)")
ok = (not iguales and tipos == ["alter", "cos 1", "sin 1", "step"]
      and abs(ll - (-140.69)) < 0.01)
sys.exit(0 if ok else 1)
