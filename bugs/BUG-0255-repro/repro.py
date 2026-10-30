"""BUG-0255: tests/test_pipeline_regression.py::
test_el_meg_encuentra_la_estacionalidad_que_hay_y_no_otra[determinista] pins,
on BOTH sides, the MEG's false positives on the deterministic series: [1, 6].
The f = 1 one is on a knife edge. Its MA_f coefficient converges to
-0.99999994, and a relative perturbation of the series of 1e-12 -- below what
a different libm already does -- makes f = 1 deterministic. So the pinned
figure is not a property of the MEG but of the last bits of one platform: on
Alpine (musl, fue's C) and on Arch (Python 3.14, fue's pure engine) the test
says [6] (clean-install test of atsw 2.1.0, 2026-10-30), and reads as a
regression or an improvement when it is neither.

The repro runs the test's own fit and MEG on the deterministic case, as is and
with the series multiplied by 1 + 1e-12 cos(t). Expected: the same verdict.

    python3 bugs/BUG-0255-repro/repro.py   # exits 1 while open
"""
import os
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")
os.environ.setdefault("MPLBACKEND", "Agg")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", ".."))
import fue                                                         # noqa: E402
from art.formal_tests import meg                                   # noqa: E402
from tests.test_pipeline_regression import _serie, caso_determinista  # noqa: E402


def declared(eps):
    c = caso_determinista()
    y = np.asarray(c["y"], float) * (1 + eps * np.cos(np.arange(len(c["y"]))))
    c = dict(c, y=y)
    iv = []
    for f in range(1, c["freq"] // 2):
        iv.append(fue.Intervention("cos", harmonic=float(f), omega=[0.1]))
        iv.append(fue.Intervention("sin", harmonic=float(f), omega=[0.1]))
    iv.append(fue.Intervention("alter", omega=[0.1]))
    m = fue.Model(_serie(c), d=0, interventions=iv, ar=[[0.3]], ar_free=[[True]],
                  mu=float(np.mean(y)), estimate_mu=True)
    m.fit()
    return sorted({r.freq for r in meg(m) if getattr(r, "stochastic", False)})


a, b = declared(0.0), declared(1e-12)
print("declared stochastic, the series as is:      ", a)
print("declared stochastic, perturbed by 1e-12:    ", b)
sys.exit(1 if a != b else 0)
