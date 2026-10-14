"""BUG-0237 (sólo el texto): cuando la Q cierra la puerta de formal_tests, se
cita la Q que DECIDE —retardo 3f+3, g.l. descontando el ARMA— y no el p mínimo
de los cuatro retardos. MA(1) 0,5 con d = 1 de la batería (BUG-0237-repro):
el p mínimo es 0,0077 (otro retardo) y la Q(39) con 38 g.l. da 0,0163."""
import re
import warnings

import numpy as np
import pytest
from scipy.signal import lfilter

fue = pytest.importorskip("fue")
from art.describe import describe_formal_tests
from art.pipeline import _make_model


def test_la_puerta_cita_la_q_del_retardo_que_decide():
    warnings.filterwarnings("ignore")
    rng = np.random.default_rng(2026)
    # la misma secuencia que el repro: las 7 estructuras de d = 0 y las 5 de
    # d = 1 que van antes del MA(1)
    for _ in range(12):
        rng.normal(size=500)
    a = rng.normal(size=500)
    x = np.cumsum(lfilter([1, -0.5], [1], a)[300:])
    x = x - x.min() + 100.0
    ts = fue.TimeSeries([float(v) for v in x], freq=12, start=(2000, 1), name="S")
    m = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=1, n_harmonics=0, estimate_mu=False)
    m.fit()
    t = describe_formal_tests(m, run_meg=False).summary
    linea = next(l for l in t.splitlines() if "La diagnosis falla en" in l)
    assert "p mínimo" not in linea
    assert re.search(r"ruido blanco \(Q\): Q\(39\) con 38 g\.l\., p = 0\.0163", linea)
