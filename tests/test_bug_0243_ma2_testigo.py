"""BUG-0243 — con un MA(2), el DCD de subdiferenciación añadía un MA(1) aparte.

El testigo se buscaba entre los factores MA de longitud 1: un MA(2) escrito
como un solo factor no contaba, y se AÑADÍA un MA(1) libre al lado (Moncloa,
ARIMA(1,2,2): θ̂ = −0,12, LR = 50,6, sin significado). La pregunta es si el MA
tiene una raíz en +1: el testigo es la raíz real del MA(2) más cercana a +1, y
el restringido es (1 − B)·MA(1). Y el DCD de sobrediferenciación ya no tira el
MA(2): lo conserva junto al testigo.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from scipy.signal import lfilter

from art.formal_tests import dcd_overdiff_regular, dcd_underdiff_regular
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

PRE = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0243-repro",
                   "Moncloa_m03.pre")


def _raices_theta(fac):
    z = np.roots([-c for c in reversed(fac)] + [1.0])
    return [1.0 / r.real for r in z if abs(r.imag) < 1e-8]


@pytest.fixture(scope="module")
def moncloa():
    from art.mcp_server import _load_fitted
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _load_fitted(PRE)[1]


def test_el_testigo_es_la_raiz_del_ma2(moncloa):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = dcd_underdiff_regular(moncloa)
    esperado = max(_raices_theta(list(moncloa.ma[0])))
    assert r.coef_free == pytest.approx(esperado, abs=1e-6)
    assert r.coef_free > 0.8                     # no el −0,12 del MA(1) añadido
    assert "MA(2)" in r.testigo
    assert r.loglik_free == pytest.approx(float(moncloa._result.loglik))
    assert r.calculable and r.lr >= r._crit["5%"]


def _ajusta(tmp, nombre, y, d, **kw):
    ts = fue.TimeSeries([float(v) for v in y], freq=12, start=(2000, 1),
                        name=nombre)
    f = str(tmp / f"{nombre}.inp")
    _write_inp(ts, fue.Model(ts, d=d, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[False]], **kw), f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return estimar(f)[1]


@pytest.fixture(scope="module")
def ma2_complejo(tmp_path_factory):
    g = np.random.default_rng(243)
    y = 100 + np.cumsum(lfilter([1, -0.5, 0.6], [1], g.standard_normal(500))[300:])
    return _ajusta(tmp_path_factory.mktemp("ma2"), "MA2C", y, 1,
                   ma=[[0.4, -0.5]], ma_free=[[True, True]])


def test_ma2_de_raices_complejas_lo_dice(ma2_complejo):
    assert not _raices_theta(list(ma2_complejo.ma[0])), "precondición: complejas"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = dcd_underdiff_regular(ma2_complejo)
    assert r.raices_complejas
    assert r.calculable


def test_la_sobrediferenciacion_conserva_el_ma2(ma2_complejo):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = dcd_overdiff_regular(ma2_complejo)
    # el testigo va DESPUÉS del MA(2) conservado, no en su lugar
    assert r.factor_index == 1
    assert r.calculable
