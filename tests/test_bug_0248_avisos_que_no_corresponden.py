"""BUG-0248 — cinco avisos que no correspondían al modelo recién estimado.

Buffalo (flour_prices.csv, ejemplo lutkepohl_poskitt de sima), ln, d = 1:
m01 = (0,1,0), m02 = (1,1,1).

1. m02, ARMA(1,1) con corr(φ̂, θ̂) = +0.988: la nota «puede ser normal en AR(2)
   con raíces complejas» salía en todo par AR–MA. Es un factor común.
2. m01, ruido blanco ELEGIDO: el escaneo latente terminaba en «procede a la
   identificación ARMA».
3. formal_tests sobre m01.pre: el aviso de SE no fiables, sin parámetros.
4. formal_tests, DCD: «Este candidato lleva el AR del modelo» sin AR (el
   relleno `[[0.0]]` fijo contaba).
5. guided_intervention sobre m01: «este modelo lleva ARMA» por el mismo relleno.
"""
import os
import warnings

import pytest

from art import mcp_server as M

CSV = os.path.join(os.path.dirname(__file__), os.pardir,
                   "bugs", "BUG-0248-repro", "flour_prices.csv")
SPEC = dict(lam=0.0, d=1, D=0, n_harmonics=0, seasonal=False, estimate_mu=False)


def _fn(t):
    return getattr(t, "fn", t)


def _txt(o):
    return "\n".join(c if isinstance(c, str) else getattr(c, "text", "")
                     for c in (o if isinstance(o, list) else [o]))


@pytest.fixture(scope="module")
def buffalo(tmp_path_factory):
    warnings.simplefilter("ignore")
    tmp = str(tmp_path_factory.mktemp("bug0248"))
    inp = os.path.join(tmp, "Buffalo.inp")
    _fn(M.load_data)(CSV, inp, column="Buffalo")
    m01 = _txt(_fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m01.inp"),
                                           p=0, q=0, **SPEC))
    m02 = _txt(_fn(M.confirm_and_estimate)(inp, os.path.join(tmp, "m02.inp"),
                                           p=1, q=1, **SPEC))
    ft = _txt(_fn(M.formal_tests)(os.path.join(tmp, "m01.pre"), run_meg=False))
    iv = _txt(_fn(M.guided_intervention)(
        os.path.join(tmp, "m01.pre"), date="12/1973", form="step", n_omega=2,
        output_path=os.path.join(tmp, "m03.inp")))
    return dict(tmp=tmp, m01=m01, m02=m02, ft=ft, iv=iv)


def test_1_arma11_no_lleva_la_nota_del_ar2(buffalo):
    assert "corr(AR(1), MA(1))" in buffalo["m02"], "precondición: el par sale"
    assert "AR(2) con raíces complejas" not in buffalo["m02"]
    assert "factor común" in buffalo["m02"]


def test_2_ruido_blanco_elegido_no_manda_a_identificar(buffalo):
    assert "Escaneo de anómalos" in buffalo["m01"], "precondición: hay escaneo"
    assert "procede a la identificación ARMA" not in buffalo["m01"]


def test_3_sin_parametros_no_hay_aviso_de_se(buffalo):
    assert "NO son fiables" not in buffalo["ft"]


def test_3_unitario_sin_parametros_libres(buffalo):
    """Un (0,1,0) estimado desde su `.pre`: cero parámetros, ningún aviso."""
    from art.pipeline import aviso_se_no_fiable, _load_fitted
    from art.diagnosis import _build_param_labels
    _, m = _load_fitted(os.path.join(buffalo["tmp"], "m01.pre"))
    assert not _build_param_labels(m)
    assert aviso_se_no_fiable(m) == ""


def test_4_dcd_sin_ar_no_dice_que_lleva_el_ar(buffalo):
    assert "sin AR regular" in buffalo["ft"], "precondición: candidato sin AR"
    assert "lleva el AR del modelo" not in buffalo["ft"]


def test_5_intervencion_sobre_ruido_blanco_no_lleva_arma(buffalo):
    assert "este modelo lleva ARMA" not in buffalo["iv"]


def test_5_lleva_arma_relleno_y_fijo():
    from art.interventions import _lleva_arma

    class _Relleno:
        ar, ar_free = [[0.0]], [[False]]
        ma = ar_s = ma_s = None

    class _Libre:
        ar, ar_free = [[0.0]], [[True]]
        ma = ar_s = ma_s = None

    class _FijoNoNulo:
        ar, ar_free = [[0.4]], [[False]]
        ma = ar_s = ma_s = None

    assert not _lleva_arma(_Relleno())
    assert _lleva_arma(_Libre())
    assert _lleva_arma(_FijoNoNulo())
