"""BUG-0249 — la llamada 1 de guided_intervention, sobre un modelo que ya
tiene el orden que el anómalo pudo fabricar.

Calibraba sólo los RESIDUOS del modelo. Con el AR(1) dentro, el orden ya se
comió la señal: r(1) +0.009 → −0.110, «no cambia la identificación». Sobre la
misma serie sin el AR, r(1) +0.221 → +0.071 al omitir los anómalos, y el par
12/1973–01/1974 hace un tercio. Ahora se calibran las dos y se dice.

Minneapolis (flour_prices.csv, ejemplo lutkepohl_poskitt de sima), ln, d = 1.
"""
import os
import warnings

import pytest

from art import mcp_server as M

CSV = os.path.join(os.path.dirname(__file__), os.pardir,
                   "bugs", "BUG-0249-repro", "flour_prices.csv")
SPEC = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)


def _fn(t):
    return getattr(t, "fn", t)


def _txt(o):
    return "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                     for c in (o if isinstance(o, list) else [o]))


@pytest.fixture(scope="module")
def minneapolis(tmp_path_factory):
    warnings.simplefilter("ignore")
    tmp = str(tmp_path_factory.mktemp("bug0249"))
    inp = os.path.join(tmp, "Minneapolis.inp")
    _fn(M.load_data)(CSV, inp, column="Minneapolis")
    _fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"), p=1, q=0, **SPEC)
    _fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m03.inp"), p=0, q=0, **SPEC)
    gi = _fn(M.guided_intervention)
    return dict(
        ar=_txt(gi(os.path.join(tmp, "m02.pre"), threshold=2.4)),
        wn=_txt(gi(os.path.join(tmp, "m03.pre"), threshold=2.4)),
        ar2=_txt(gi(os.path.join(tmp, "m02.pre"), threshold=2.4, date="12/1973")))


def test_sobre_el_ar1_dice_que_ya_lo_tiene(minneapolis):
    assert "Este modelo ya tiene AR(1)" in minneapolis["ar"]


def test_calibra_la_serie_sin_el_ar(minneapolis):
    txt = minneapolis["ar"]
    assert "| AR | PACF(1) | +0.221 | +0.071 |" in txt


def test_nombra_el_par_que_lo_hace(minneapolis):
    txt = minneapolis["ar"]
    assert "puede estar fabricado" in txt
    assert "12/1973–01/1974" in txt


def test_la_parada_no_cubre_el_orden(minneapolis):
    assert "Salvo el orden del modelo" in minneapolis["ar"]


def test_sin_arma_no_hay_seccion(minneapolis):
    assert "Este modelo ya tiene" not in minneapolis["wn"]


def test_la_llamada_2_explica_el_factor_de_la_leyenda(minneapolis):
    txt = minneapolis["ar2"]
    assert "«hypothesis ×" in txt
    assert "mínimos cuadrados" in txt


def test_ordenes_arma_no_cuenta_el_relleno():
    class _Relleno:
        ar, ar_free = [[0.0]], [[False]]
        ma = ar_s = ma_s = None
        ma_free = ar_s_free = ma_s_free = None

    class _ARMA11:
        ar, ar_free = [[0.3]], [[True]]
        ma, ma_free = [[0.2]], [[True]]
        ar_s = ma_s = ar_s_free = ma_s_free = None

    assert M._ordenes_arma(_Relleno()) == {}
    assert M._ordenes_arma(_ARMA11()) == {"AR": 1, "MA": 1}
    assert M._texto_ordenes_arma({"AR": 1, "MA": 1}) == "AR(1) y MA(1)"
