"""BUG-0249: guided_intervention (call 1) calibrates on the residuals of the
model it is given.  If that model already has the order an outlier pair may
have made, the order has absorbed it and the calibration cannot see it.
Minneapolis (flour_prices.csv, the lutkepohl_poskitt example of sima), ln, d=1.

    python3 bugs/BUG-0249-repro/repro.py      # exits 1 while the bug is open
"""
import os, re, sys, tempfile
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
spec = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)

def r1(report):
    m = re.search(r"^\| 1 \| ([+-][0-9.]+) \| ([+-][0-9.]+) \|", report, re.M)
    return float(m.group(1)), float(m.group(2))

with tempfile.TemporaryDirectory() as tmp:
    inp = os.path.join(tmp, "Minneapolis.inp")
    fn(M.load_data)(os.path.join(HERE, "flour_prices.csv"), inp, column="Minneapolis")
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"), p=1, q=0, **spec)  # AR(1)
    fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m03.inp"), p=0, q=0, **spec)  # (0,1,0)
    on_ar = txt(fn(M.guided_intervention)(os.path.join(tmp, "m02.pre"), threshold=2.4))
    on_wn = txt(fn(M.guided_intervention)(os.path.join(tmp, "m03.pre"), threshold=2.4))
print("calibrated on the AR(1) residuals: r(1) obs %+.3f, without outliers %+.3f" % r1(on_ar))
print("calibrated on the (0,1,0) = the identification series: r(1) obs %+.3f, without %+.3f" % r1(on_wn))
warned = re.search(r"ya (tiene|lleva) (un )?AR", on_ar) is not None
print("the call on the AR(1) warns that its own order cannot be judged:", warned)
sys.exit(0 if warned else 1)
