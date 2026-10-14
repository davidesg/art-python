"""BUG-0244: confirm_and_estimate with base_pre_path does not accept `p` as a
list of factors (TypeError in _arma_starts).  IPC_US m06 (AR(2) + two
interventions): chaining p=[1, 2] should estimate AR(1)·AR(2) keeping both
interventions.

    PYTHONPATH=src python3 bugs/BUG-0244-repro/repro.py   # exits 1 while open
"""
import os, sys, tempfile
os.environ.setdefault("ART_NO_VIEWER", "1")
from art import mcp_server as M
fn = lambda t: getattr(t, "fn", t)
txt = lambda o: "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                          for c in (o if isinstance(o, list) else [o]))
HERE = os.path.dirname(os.path.abspath(__file__))
with tempfile.TemporaryDirectory() as tmp:
    out = txt(fn(M.confirm_and_estimate)(
        os.path.join(HERE, "IPC_US_m06.inp"), os.path.join(tmp, "x.inp"),
        base_pre_path=os.path.join(HERE, "IPC_US_m06.pre"),
        p=[1, 2], q=0, estimate_mu=True))
    if "TypeError" in out or not os.path.exists(os.path.join(tmp, "x.pre")):
        print("p=[1, 2] with base_pre_path fails:",
              next((l for l in out.splitlines() if "Error" in l), out[:300]))
        sys.exit(1)
    _, m = M._load_ts_model(os.path.join(tmp, "x.pre"))
ords = [len(f) for f in m.ar]
tipos = sorted(i.type for i in m.interventions)
print("AR factors:", ords, "· interventions:", tipos)
sys.exit(0 if ords == [1, 2] and tipos == ["impulse", "step"] else 1)
