"""BUG-0262: guided_identification has no `modo`: in the autonomous lane its
figures travel as images, in every one of its calls.

The tools that estimate and intervene take modo="autonomo" and then save
their figures next to the model instead of returning them (BUG-0208). The
tool of the first nodes (lambda, d, seasonality, orders) does not: it has no
`modo`, and every call returns its figures as ImageContent, which the client
resends on every later turn.

WTI.inp: the WTI oil price, monthly, 1990-2007 (FRED), data only.

    python3 bugs/BUG-0262-repro/repro.py   # exits 1 while open
"""
import inspect
import os
import shutil
import sys
import tempfile

os.environ.setdefault("ART_NO_VIEWER", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "src"))
import art.mcp_server as m          # noqa: E402
from mcp.types import ImageContent  # noqa: E402

params = inspect.signature(m.guided_identification).parameters
print("guided_identification takes modo:", "modo" in params)
if "modo" not in params:
    print("OPEN: no modo, so the autonomous lane cannot ask for its figures to stay")
    sys.exit(1)
with tempfile.TemporaryDirectory() as t:
    os.environ["ART_FIG_DIR"] = t
    inp = shutil.copy(os.path.join(HERE, "WTI.inp"), os.path.join(t, "WTI.inp"))
    res = m.guided_identification(inp, domain="multiplicative",
                                  expectativas="I(1) in logs, short memory",
                                  modo="autonomo")
    imgs = [c for c in res if isinstance(c, ImageContent)]
    saved = [f for f in os.listdir(t) if f.startswith("WTI__") and f.endswith(".png")]
    print(f"images returned in autonomous: {len(imgs)}; saved next to the model: {len(saved)}")
    if imgs or not saved:
        print("OPEN: the figures still travel, or were not saved next to the model")
        sys.exit(1)
    res = m.guided_identification(inp, domain="multiplicative",
                                  expectativas="I(1) in logs, short memory")
    if not [c for c in res if isinstance(c, ImageContent)]:
        print("the guided lane lost its figures")
        sys.exit(2)
print("closed: in autonomous the figures stay next to the model; guided still shows them")
sys.exit(0)
