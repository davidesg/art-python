"""BUG-0235 — con d=2, formal_tests contrastaba d=3.

`dcd_overdiff_regular` hacía `mc.d = d + 1` sin tope: sobre un IMA(2,1)
construía ∇³ y publicaba «d confirmado ✓» como confirmatorio del orden de
integración; y Shin-Fuller, con un AR casi en 1, proponía d+1 = 3. Con la regla
de un paso d no sube de 2. La duda de un modelo en d=2 es la de abajo, y su par
cruza dos modelos: el DCD de subdiferenciación del modelo en d=2 y el
Shin-Fuller del modelo en d=1 (`modelo_d_menos_1`).
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from scipy.signal import lfilter

import art.describe as describe
from art.describe import describe_formal_tests
from art.formal_tests import DCDResult, ShinFullerResult, dcd_overdiff_regular
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


def _ajusta(tmp, nombre, y, d, **kw):
    ts = fue.TimeSeries([float(v) for v in y], freq=12, start=(2000, 1),
                        name=nombre)
    f = str(tmp / f"{nombre}.inp")
    kw.setdefault("ar", [[0.0]])
    kw.setdefault("ar_free", [[False]])
    _write_inp(ts, fue.Model(ts, d=d, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, **kw), f)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return estimar(f)[1]


@pytest.fixture(scope="module")
def modelos(tmp_path_factory):
    """La misma serie I(2): un IMA(2,1) y un AR(1) en d=1."""
    tmp = tmp_path_factory.mktemp("d2")
    g = np.random.default_rng(235)
    x = lfilter([1, -0.8], [1], g.standard_normal(260))[60:]
    y = 1000 + np.cumsum(np.cumsum(x))
    m2 = _ajusta(tmp, "IMA", y, 2, ma=[[0.5]], ma_free=[[True]])
    m1 = _ajusta(tmp, "AR1", y, 1, ar=[[0.5]], ar_free=[[True]])
    return m2, m1


def test_desde_d2_no_se_construye_nabla3(modelos):
    m2, _ = modelos
    assert dcd_overdiff_regular(m2) is None


def test_el_informe_no_confirma_d_sobre_nabla3(modelos):
    m2, _ = modelos
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = describe_formal_tests(m2, run_meg=False).summary
    assert "Candidato: ∇^3" not in s
    assert "d confirmado ✓" not in s
    assert "no se contrasta desde d=2" in s


def _sf(stationary, n=200):
    return ShinFullerResult(
        phi_null=1 - 4 / n, phi_free=[0.5 if stationary else 0.97],
        loglik_free=0.0, loglik_constrained=-5.0 if stationary else 0.0,
        phi_1u=5.0 if stationary else 0.3, crit_10pct=1.07, crit_5pct=1.76,
        crit_1pct=3.43, df=1, pvalue=0.5, n=n, s=12,
        phi_dominant=0.5 if stationary else 0.97)


def test_shin_fuller_en_d2_no_propone_d3(modelos, monkeypatch):
    m2, _ = modelos
    monkeypatch.setattr(describe, "shin_fuller", lambda _m: _sf(False))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(m2, run_meg=False)
    assert "considerar d+1" not in d.summary
    assert "Considera aumentar d en 1" not in d.recommendation
    assert "no se sube" in d.summary


def test_el_par_cruzado_de_la_frontera_1_2(modelos, monkeypatch):
    """Villaverde: SF en d=1 rechaza (d=1 basta) y el DCD de subdiferenciación
    en d=2 también (θ̂ = 0,906, LR = 23,9): los dos rechazan, θ̂ en la banda →
    ambiguo."""
    m2, m1 = modelos
    ud = DCDResult(factor_index=0, freq=None, coef_free=0.906, coef_null=1.0,
                   loglik_free=0.0, loglik_constrained=-11.95, lr=23.9, n=200)
    monkeypatch.setattr(describe, "shin_fuller", lambda _m: _sf(True))
    monkeypatch.setattr(describe, "dcd_underdiff_regular", lambda _m: ud)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(m2, run_meg=False, modelo_d_menos_1=m1)
    assert "Par de la frontera 1/2" in d.summary
    assert "AMBIGUO" in d.summary
    assert d.data["par_d_menos_1"] == "ambiguo"
    assert "El modelo es adecuado" not in d.recommendation


def test_el_par_cruzado_coincide_en_d(modelos, monkeypatch):
    m2, m1 = modelos
    ud = DCDResult(factor_index=0, freq=None, coef_free=0.5, coef_null=1.0,
                   loglik_free=0.0, loglik_constrained=-20.0, lr=40.0, n=200)
    monkeypatch.setattr(describe, "shin_fuller",
                        lambda m: _sf(False) if int(m.d) == 1 else _sf(True))
    monkeypatch.setattr(describe, "dcd_underdiff_regular", lambda _m: ud)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(m2, run_meg=False, modelo_d_menos_1=m1)
    assert d.data["par_d_menos_1"] == "d"
    assert "Coinciden en d=2" in d.summary


def test_el_resumen_de_shin_fuller_en_d2_no_propone_d3():
    # el resumen del resultado, no sólo el texto de describe
    base = dict(phi_null=0.98, phi_free=[0.999], loglik_free=0.0,
                loglik_constrained=0.0, phi_1u=0.0, crit_10pct=1.0,
                crit_5pct=1.5, crit_1pct=2.5, df=1, pvalue=1.0, n=200, s=12,
                phi_dominant=0.999)
    assert "considerar d+1" in ShinFullerResult(**base, d=1).summary()
    r2 = ShinFullerResult(**base, d=2).summary()
    assert "considerar d+1" not in r2 and "no se propone d+1" in r2
