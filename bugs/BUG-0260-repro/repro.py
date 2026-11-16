#!/usr/bin/env python3
"""BUG-0260: compare_versions suppresses the comparison between two models of
the same series that differ only in lambda or in the rescaling factor.

Neither changes the dependent variable, only its units: with the same operator
and sample, the log-likelihood in the units of y, l + n ln(factor) +
(lambda - 1) sum ln y (fue.scale.loglik_y), compares them. compare_versions
printed "— no comp." and, between factors, told the analyst to re-estimate
"the same model badly labelled" -- since 0.2.5 a factor other than 100 can be
the right one (BUG-0257).

A quarterly random walk about 100: (1) the same model, d = 1, with factor 100
and 1; (2) the series in logs and in levels. Exits 1 while either comparison
is suppressed, or the first gives a Delta loglik away from 0.
"""
import os
import re
import sys
import tempfile
import warnings

import numpy as np

os.environ.setdefault("ART_NO_VIEWER", "1")
warnings.filterwarnings("ignore")

import fue
from art import mcp_server as srv
from art.pipeline import _write_inp


def _txt(items):
    return "\n".join(getattr(i, "text", "") for i in items)


def main():
    rng = np.random.default_rng(3)
    y = np.exp(np.cumsum(0.02 * rng.standard_normal(80)) + np.log(100.0))
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")
    fn = getattr(srv.compare_versions, "fn", srv.compare_versions)
    ok = True
    with tempfile.TemporaryDirectory() as d:
        paths = {}
        for tag, lam, rf in (("l100", 0.0, 100.0), ("l1", 0.0, 1.0), ("n100", 1.0, 100.0)):
            m = fue.Model(ts, boxlam=lam, d=1, mu=0.0, estimate_mu=False, refactor=rf)
            m.fit()
            p = os.path.join(d, tag + ".inp")
            _write_inp(ts, m, p, refactor=rf)
            paths[tag] = p
        t1 = _txt(fn(paths["l100"], paths["l1"], 0.0, 0.0))
        t2 = _txt(fn(paths["l100"], paths["n100"], 0.0, 1.0))
    m1 = re.search(r"\| loglik\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|", t1)
    m2 = re.search(r"\| loglik\s*\|[^|]*\|[^|]*\|\s*([^|]+?)\s*\|", t2)
    d1 = m1.group(1) if m1 else "?"
    d2 = m2.group(1) if m2 else "?"
    print(f"factor 100 vs 1, same model: Δ loglik = {d1}")
    print(f"logs vs levels:              Δ loglik = {d2}")
    if "no comp" in d1 or "no comp" in d2:
        ok = False
    else:
        try:
            ok = abs(float(d1)) < 1e-2
        except ValueError:
            ok = False
    print("FIXED" if ok else "OPEN: the comparison is suppressed (or is not invariant)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
