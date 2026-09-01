"""BUG-0024 — la banda de cuasi-cancelación se afirma por DISTANCIA, no por discrepancia.

El bloque del par en f=0 ponía `quasi_cancellation = True` sólo porque los dos
contrastes discreparan, sin mirar nunca a qué distancia de la frontera θ=+1 está
el testigo — y el rótulo que emite nombra una banda concreta (r≈0.90–0.95, o sea
distancia ≤ 0.10).

Es la misma especie que BUG-0022 un escalón más abajo: allí se borraba el SIGNO
del testigo, aquí se ignoraba su MAGNITUD.
"""
import io
import os
import tempfile
import warnings

import numpy as np
import pytest

import fue
from art.describe import BANDA_CUASI_CANCELACION, describe_formal_tests
from art.formal_tests import dcd_overdiff_regular, shin_fuller

PL = """************************************************
* FUE
************************************************
** Frequency of time series: either 1(A), 4(Q) or 12(M):
 4
** Number of observations and starting date of time series:
 {n}  1 2000 S
** Number of deterministic variables (including seasonal components):
0
** Number and orders of regular AR operators:
1 1
**
0.300000  1
** Number and orders of annual AR operators:
0
** Number and orders of regular MA operators:
0
** Number and orders of anual MA operators:
0
** Number and frequencies of regular AR(2) operators with fixed frequency:
0
** Number and frequencies of regular MA(2) operators with fixed frequency:
0
** Mean parameter (mu):
0.000000 0
** Box-Cox lambda, regular differences and complete annual differences:
 1.00  0  0
** Individual factors of the annual difference (starting at freq 0.0):
0 0 0
** ACF/PACF bands (0 Automatic) and reescaling factor:
 0 1.00
** Time series (stochastic and non-standard deterministic variables):
{datos}
"""


def _ajusta(y, tmp):
    f = os.path.join(tmp, f"b{np.random.randint(1_000_000)}.inp")
    io.open(f, "w", encoding="utf-8").write(
        PL.format(n=len(y), datos="\n".join(f"{v:.8f}" for v in y)))
    ts, m = fue.load(f)
    m.fit()
    return m


def _discrepa(m):
    sf = shin_fuller(m)
    od = dcd_overdiff_regular(m)
    return sf.stationary != (not (od.lr >= od._crit["5%"])), od.coef_free


def _busca(dentro_de_la_banda, semilla, integrado):
    """Un modelo que DISCREPA con el testigo dentro o fuera de la banda."""
    warnings.simplefilter("ignore")
    tmp = tempfile.mkdtemp()
    rng = np.random.default_rng(semilla)
    for _ in range(20):
        a = rng.standard_normal(220)
        if integrado:
            y = np.cumsum(a)[100:]
        else:
            w = np.zeros(220)
            for t in range(1, 220):
                w[t] = 0.5 * w[t - 1] + a[t]
            y = w[100:]
        y = y - y.mean()
        try:
            m = _ajusta(y, tmp)
            disc, th = _discrepa(m)
        except Exception:
            continue
        if not disc:
            continue
        dist = 1.0 - th
        if (dist <= BANDA_CUASI_CANCELACION) == dentro_de_la_banda and dist > 1e-9:
            return m, dist
    return None, None


def test_el_umbral_es_el_del_paper():
    """r≈0.90–0.95 en `tab:compare` ⇒ distancia 0.05–0.10 a la frontera."""
    assert BANDA_CUASI_CANCELACION == pytest.approx(0.10)


def test_dentro_de_la_banda_si_se_afirma():
    m, dist = _busca(dentro_de_la_banda=True, semilla=99, integrado=True)
    if m is None:
        pytest.skip("no se encontró un caso dentro de la banda")
    r = describe_formal_tests(m, run_meg=False)
    assert r.data["f0_pair"]["quasi_cancellation"] is True
    txt = r.summary.replace("**", "")
    assert "banda de cuasi-cancelación" in txt
    assert "equivalentes en previsión" in txt


def test_fuera_de_la_banda_NO_se_afirma():
    """θ̂ lejos de +1: discrepan, pero no es la banda que el rótulo nombra."""
    m, dist = _busca(dentro_de_la_banda=False, semilla=99, integrado=False)
    if m is None:
        pytest.skip("no se encontró un caso fuera de la banda")
    assert dist > BANDA_CUASI_CANCELACION
    r = describe_formal_tests(m, run_meg=False)
    assert r.data["f0_pair"]["quasi_cancellation"] is False
    txt = r.summary.replace("**", "")
    assert "NO es la banda de cuasi-cancelación" in txt
    # y no puede colarse la conclusión que la banda autorizaba
    assert "equivalentes en previsión" not in txt


def test_fuera_de_la_banda_dice_que_hacer():
    """Negar la banda sin decir qué hacer dejaría al analista peor que antes."""
    m, _ = _busca(dentro_de_la_banda=False, semilla=99, integrado=False)
    if m is None:
        pytest.skip("no se encontró un caso fuera de la banda")
    txt = describe_formal_tests(m, run_meg=False).summary
    assert "estima el candidato rival" in txt
    assert "inadecuado" in txt          # la primera causa a descartar
