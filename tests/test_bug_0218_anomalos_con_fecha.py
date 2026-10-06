"""BUG-0218 — los anómalos de la diagnosis iban sin fecha y con otra z.

«obs 149 (z=+3,56)»: el índice es sobre los residuos —cambia con d— y la z
dividía por la desviación típica muestral, mientras el `.out` usa la
poblacional (3,57). Ahora va la fecha, el índice del `.out` y su misma z.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.diagnosis import diagnose
from art.pipeline import _RESCALE_FACTOR, _write_inp, mirar


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


@pytest.fixture(scope="module")
def serie(tmp_path_factory):
    """Paseo con deriva y un pulso grande en 03/2025 (obs 183 de la serie)."""
    d = tmp_path_factory.mktemp("b218")
    rng = np.random.default_rng(218)
    n = 188                                   # 2010:01 … 2025:08, como Retiro
    z = np.cumsum(0.004 + 0.01 * rng.standard_normal(n))
    z[182] += 0.08
    ts = fue.TimeSeries(np.exp(7 + z).tolist(), freq=12, start=(2010, 1), name="R")
    f = str(d / "R.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    return d, f


def _estima(d, f, dd, nombre):
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(fn(f, str(d / f"{nombre}.inp"), lam=0, d=dd, D=0, p=0, q=1,
                  n_harmonics=0, seasonal=False, estimate_mu=(dd == 1),
                  domain="price_index", modo="autonomo"))
    return t, str(d / f"{nombre}.out"), str(d / f"{nombre}.pre")


def test_la_misma_fecha_con_d1_y_con_d2(serie):
    d, f = serie
    t1, _, _ = _estima(d, f, 1, "m1")
    t2, _, _ = _estima(d, f, 2, "m2")
    l1 = re.search(r"Residuos extremos[^\n]*", t1).group(0)
    l2 = re.search(r"Residuos extremos[^\n]*", t2).group(0)
    assert "03/2025 (obs 182," in l1, l1
    assert "03/2025 (obs 181," in l2, l2


def test_la_z_es_la_del_out(serie):
    d, f = serie
    _, out, pre = _estima(d, f, 1, "m1z")
    tabla = {int(o): float(z) for o, z in re.findall(
        r"\|\s+(\d+)\s+\d+/\s*\d{4}\s+(-?\d+\.\d+)\s+\|", open(out).read())}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dg = diagnose(mirar(pre)[1])
    assert dg.extreme
    for o, z in dg.extreme:
        assert o in tabla and f"{z:.2f}" == f"{tabla[o]:.2f}", (o, z, tabla.get(o))
        assert dg.extreme_dates[o]
