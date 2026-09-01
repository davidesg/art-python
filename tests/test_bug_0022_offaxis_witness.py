"""BUG-0022 — un testigo de sobrediferenciación negativo se informaba como
«banda de cuasi-cancelación».

La frontera de sobrediferenciación en f=0 está en θ=+1 y sólo ahí: es el factor
(1−B). `describe.py` medía la distancia como `abs(1 - abs(θ̂))`, y ese abs()
INTERIOR refleja un testigo del eje de Nyquist (θ̂<0, raíz hacia B=−1) sobre el
eje de f=0. Un θ̂=−0.57 aparecía «a 0.43 de la frontera» cuando está a 1.57, y el
informe lo vendía como la banda r≈0.90–0.95, donde las representaciones son
equivalentes en previsión.

`dcd_overdiff_regular` ya documenta el arrastre negativo como su modo de fallo
conocido; lo que faltaba era comprobarlo.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.formal_tests import dcd_overdiff_regular, shin_fuller
from art.describe import describe_formal_tests


def _ajusta_ar2_en_niveles(y, tag):
    d = tempfile.mkdtemp(prefix=f"bug0022-{tag}-")
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=2004, start_period=1)
    out = os.path.join(d, "S_ar2.inp")
    A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=0, D=0,
                           p=2, q=0, n_harmonics=0, seasonal=False,
                           estimate_mu=True)
    ts, m = _load_ts_model(out.replace(".inp", ".pre"))
    m.fit()
    return m


@pytest.fixture(scope="module")
def modelo_testigo_negativo():
    """ARIMA(1,1,0) — I(1) por construcción — ajustado con un AR(2) en niveles.

    Reproduce la configuración medida en ln PGAS: Shin-Fuller dice estacionario
    y el testigo del DCD se va a negativo, que es la única rama que emite el
    texto de la banda. Semilla 9 fijada.
    """
    rng = np.random.default_rng(9)
    n = 84
    u = np.zeros(n)
    for t in range(1, n):
        u[t] = 0.58 * u[t - 1] + rng.normal(0, 1.0)
    return _ajusta_ar2_en_niveles(100.0 + np.cumsum(u), "neg")


def test_la_configuracion_es_la_que_dispara_el_bloque(modelo_testigo_negativo):
    """El asunto de BUG-0022 es el TESTIGO, no el veredicto del lado AR.

    La versión anterior exigía además `shin_fuller(m).stationary is True`, y ese
    «estacionario» sobre una serie I(1) por construcción era precisamente el
    veredicto equivocado que corrigió BUG-0065. Lo que este bloque prueba —un
    testigo en θ̂<0 midiendo Nyquist— no depende de él, y ligarlo a un error
    ajeno hacía que el test defendiera ese error.
    """
    m = modelo_testigo_negativo
    assert dcd_overdiff_regular(m).coef_free < 0.0    # lado MA: fuera del eje


def test_no_se_declara_cuasi_cancelacion_con_testigo_negativo(modelo_testigo_negativo):
    r = describe_formal_tests(modelo_testigo_negativo, run_meg=False)
    # la bandera, que es lo que consume quien lea `data` en vez del texto
    assert r.data["f0_pair"]["quasi_cancellation"] is False
    # y el texto: no puede AFIRMAR la banda (la menciona para negarla)
    assert "es la **banda de cuasi-cancelación**" not in r.summary
    assert "El testigo se salió del eje f=0" in r.summary


def test_la_distancia_impresa_es_la_real_y_no_la_reflejada(modelo_testigo_negativo):
    m = modelo_testigo_negativo
    th = dcd_overdiff_regular(m).coef_free
    r = describe_formal_tests(m, run_meg=False)
    assert f"{1.0 - th:.4f}" in r.summary            # distancia con signo
    reflejada = f"{abs(1.0 - abs(th)):.4f}"
    assert reflejada not in r.summary               # la fórmula vieja, fuera
    assert 1.0 - th > 1.0                           # y de verdad está lejos


def test_un_testigo_fugado_no_cierra_en_modelo_adecuado(modelo_testigo_negativo):
    r = describe_formal_tests(modelo_testigo_negativo, run_meg=False)
    assert "no detectan problemas" not in r.recommendation
    assert "fuera del eje f=0" in r.recommendation


def test_la_banda_legitima_se_sigue_informando():
    """Con θ̂>0 y discrepancia, el texto de la banda debe seguir saliendo.

    Semilla 7: θ̂=+0.778, LR=4.79 > 1.94 — el testigo está en el eje correcto y
    los dos lados discrepan, que es la banda legítima.
    """
    rng = np.random.default_rng(7)
    n = 84
    u = np.zeros(n)
    for t in range(1, n):
        u[t] = 0.58 * u[t - 1] + rng.normal(0, 1.0)
    m = _ajusta_ar2_en_niveles(100.0 + np.cumsum(u), "pos")

    od = dcd_overdiff_regular(m)
    if not (shin_fuller(m).stationary and od.coef_free > 0
            and od.lr >= od._crit['5%']):
        pytest.skip("esta realización no cae en la rama de banda legítima")

    r = describe_formal_tests(m, run_meg=False)
    assert r.data["f0_pair"]["quasi_cancellation"] is True
    assert "es la **banda de cuasi-cancelación**" in r.summary
    assert "El testigo se salió del eje f=0" not in r.summary
