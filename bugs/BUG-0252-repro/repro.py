"""BUG-0252: confirm_and_estimate with base_pre_path drops ar_f_freqs in silence.
Minneapolis (flour_prices.csv, the lutkepohl_poskitt example of sima): from the
AR(1) m02.pre, chaining with ar_f_freqs=[2] (a fixed-frequency AR(2) at the
semiannual frequency 2π·2/12) should add that factor; it gives m02 again.

    python3 bugs/BUG-0252-repro/repro.py      # exits 1 while the bug is open
"""
import os, sys, tempfile
import fue
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
HERE = os.path.dirname(os.path.abspath(__file__))
spec = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)
with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "Minneapolis.inp")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Minneapolis")
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"), p=1, q=0, **spec)
    fresh = os.path.join(tmp, "fresh.inp")
    fn(M.confirm_and_estimate)(inp, fresh, p=1, q=0, ar_f_freqs=[2], **spec)
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m03.inp"),
                               base_pre_path=os.path.join(tmp, "m02.pre"),
                               p=1, q=0, ar_f_freqs=[2], estimate_mu=False)
    n_fresh = len(fue.load(os.path.join(tmp, "fresh.pre"))[1].ar_f)
    n_chain = len(fue.load(os.path.join(tmp, "m03.pre"))[1].ar_f)
print("fixed-frequency AR factors, fresh with ar_f_freqs=[2]:", n_fresh)
print("fixed-frequency AR factors, chained with ar_f_freqs=[2]:", n_chain)
sys.exit(1 if n_chain != n_fresh else 0)
