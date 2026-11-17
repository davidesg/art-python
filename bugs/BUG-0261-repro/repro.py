#!/usr/bin/env python3
"""BUG-0261: on macOS, estimating the same model from its .pre does not give
the standard errors it gives from its .inp (or not by the finite-difference
Hessian).

tests/test_fue_bug_0015_metodo_de_las_se.py::test_estimar_acepta_el_pre_y_las_se_coinciden
fails on macOS (arm64 and Intel) and nowhere else, in the atsw 2.1.1 and
2.1.3 preflights with the suites (art-python runs 43094293797 and
44154374179). It is BUG-0090's model -- a random walk about 100 with a step at
80, d = 1, AR(1), refactor 100 -- estimated from the .inp and from its .pre:
the test asks that both have their s.e. from the finite-difference Hessian,
that the second knows it comes from a .pre, that the s.e. agree to rtol 1e-3,
and that no warning is raised. The CI log does not say which fails.

Runs the four checks separately and says which fail. Exits 1 if any fails
here; 0 if all hold on macOS (fixed); 2 if all hold on another platform (it
does not reproduce here: run it on a Mac).
"""
import os
import platform
import sys
import tempfile
import warnings

import numpy as np

os.environ.setdefault("ART_NO_VIEWER", "1")
import fue                                              # noqa: E402
from art import diagnosis as D                          # noqa: E402
from art import pipeline as P                           # noqa: E402


def main():
    d = tempfile.mkdtemp(prefix="bug261-")
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.standard_normal(150) * 0.4) + 100.0
    y[80:] += 4.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="R15")
    itv = fue.Intervention("step", at=80, omega=[0.0, 0.0], omega_free=[True, True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0, estimate_mu=False,
                  interventions=[itv], refactor=P._RESCALE_FACTOR)
    f_inp = os.path.join(d, "R15.inp")
    P._write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m_inp = P.estimar(f_inp)
        f_pre = os.path.join(d, "R15.pre")
        m_inp.write_pre(f_pre)
        _, m_pre = P.estimar(f_pre)
    a, b = m_inp._result, m_pre._result
    print("se_method .inp:", getattr(a, "se_method", None), "| .pre:", getattr(b, "se_method", None))
    print("s.e. .inp:", np.round(a.std_errors, 6))
    print("s.e. .pre:", np.round(b.std_errors, 6))
    checks = {
        "s.e. from the finite-difference Hessian, both": D.se_del_hessiano(a) and D.se_del_hessiano(b),
        "the second knows it comes from a .pre": bool(P.viene_de_pre(m_pre)),
        "s.e. agree to rtol 1e-3": bool(np.allclose(b.std_errors, a.std_errors, rtol=1e-3, atol=0)),
        "no warning on the .pre's s.e.": P.aviso_se_no_fiable(m_pre) == "",
    }
    for k, v in checks.items():
        print(f"  [{'ok' if v else 'FAILS'}] {k}")
    mac = platform.system() == "Darwin"
    if not all(checks.values()):
        print("OPEN")
        return 1
    if mac:
        print("FIXED on macOS")
        return 0
    print(f"all hold on {platform.system()} {platform.machine()}: the defect shows on macOS "
          "only -- run this there")
    return 2


if __name__ == "__main__":
    sys.exit(main())
