"""BUG-0224 — DCD de subdiferenciación sin potencia con AR libre.

Bajo H₀ (θ = 1) el modelo es (1 − φB)∇N = (1 − B)a ⇔ (1 − φB)N = a, y con el
AR libre el optimizador recupera la ∇ con φ → 1: el LR se hunde aunque el
testigo esté lejísimos de +1. Rc (dolarización, n = 68): sin AR, LR 157,7; con
un AR(1) no significativo, φ̂ del restringido 0,979, LR 1,57 y «testigo NO
invertible (θ→+1) → con d−1 bastaba» con θ̂ = −0,06.

El arreglo acota la raíz AR real positiva dominante del restringido en
ρₘ = 1 − 4/n (el umbral de Shin-Fuller) y el veredicto lee también θ̂.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from scipy.signal import lfilter

from art.describe import _estado_subdif, describe_formal_tests
from art.formal_tests import DCDResult, dcd_underdiff_regular
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

REPRO = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0224-repro")


def _carga(nombre):
    from art.mcp_server import _load_fitted
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _load_fitted(os.path.join(REPRO, nombre))[1]


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


def _ud(m):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return dcd_underdiff_regular(m)


def test_rc_con_ar_libre_la_diferencia_es_genuina():
    r = _ud(_carga("Rc_m01_ar1.pre"))
    assert r.calculable
    # el restringido quería reconstruir la ∇ con el AR, y se acotó
    assert r.ar_acotado
    assert r.phi_restringido >= r.rho_m
    assert r.lr >= r._crit["5%"], f"LR={r.lr:.3f}: sigue sin potencia"
    assert _estado_subdif(r) == "genuina"


def test_rc_sin_ar_no_cambia():
    r = _ud(_carga("Rc_m00.pre"))
    assert not r.ar_acotado and r.phi_restringido is None
    assert r.lr > 100


def test_rc_el_informe_no_dice_que_bastaba_d_menos_1():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = describe_formal_tests(_carga("Rc_m01_ar1.pre"), run_meg=False,
                                  subdiferenciacion=True).summary
    bloque = s.split("**DCD sub-diferenciación regular**")[1]
    assert "bastaba" not in bloque.split("\n\n")[0]
    assert "θ→+1" not in bloque.split("\n\n")[0]
    assert "Se acota en ρₘ" in bloque          # dice qué hizo el AR


def test_paseo_con_ar_libre_sigue_confirmando_d(tmp_path):
    g = np.random.default_rng(224)
    lfilter([1], [1, -0.5], g.standard_normal(500))       # mismo orden que la validación
    y = 100 + np.cumsum(lfilter([1], [1, -0.2], g.standard_normal(500))[300:])
    sin_ar = _ud(_ajusta(tmp_path, "RW0", y, 1))
    con_ar = _ud(_ajusta(tmp_path, "RW1", y, 1, ar=[[0.1]], ar_free=[[True]]))
    assert _estado_subdif(sin_ar) == "genuina"
    assert _estado_subdif(con_ar) == "genuina"


def test_estacionario_en_niveles_sigue_detectando_la_diferencia_que_sobra(tmp_path):
    g = np.random.default_rng(224)
    y = 100 + lfilter([1], [1, -0.5], g.standard_normal(500))[300:]
    r = _ud(_ajusta(tmp_path, "EST", y, 1, ar=[[0.3]], ar_free=[[True]]))
    assert not r.ar_acotado              # un AR en 0,5 no reconstruye nada
    assert _estado_subdif(r) == "cancelada"


def _r(theta, lr, **kw):
    return DCDResult(factor_index=0, freq=None, coef_free=theta, coef_null=1.0,
                     loglik_free=lr / 2, loglik_constrained=0.0, lr=lr, n=200, **kw)


def test_el_veredicto_lee_theta_y_no_solo_el_lr():
    assert _estado_subdif(_r(0.98, 0.2)) == "cancelada"
    # LR bajo con θ̂ lejos de +1: no es «θ→+1»
    assert _estado_subdif(_r(-0.06, 1.5)) == "no_concluyente"
    # LR bajo con el AR acotado: por el lado AR la ∇ hace falta
    assert _estado_subdif(_r(0.99, 0.5, ar_acotado=True, phi_restringido=0.99,
                             rho_m=0.94)) == "no_concluyente"
