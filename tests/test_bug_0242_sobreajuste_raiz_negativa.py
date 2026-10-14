"""BUG-0242 — el Shin-Fuller por sobreajuste se callaba con una raíz real negativa.

IPC_US m06: AR(2) de raíces complejas y dos intervenciones. El sobreajuste
AR(3) se factoriza en AR(1)·AR(2) con φ̂ = −0,206; `shin_fuller` lanza la
excepción de BUG-0215 («raíz negativa»), `_try` la volvía `None`, y el
informe decía «el lado AR no existe en esta corrida». Sí existe: la raíz
recuperada está lejos de +1, así que el lado AR no apoya d+1.
"""
import os
import warnings

import pytest

pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import describe_formal_tests
from art.formal_tests import shin_fuller_sobreajuste

PRE = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0242-repro",
                   "IPC_US_m06.pre")


@pytest.fixture(scope="module")
def m06():
    from art.mcp_server import _load_fitted
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _load_fitted(PRE)[1]


def test_devuelve_la_raiz_negativa_en_vez_de_lanzar(m06):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = shin_fuller_sobreajuste(m06)
    assert r.sin_raiz_positiva and r.sf is None
    assert r.phi_real == pytest.approx(-0.206, abs=0.01)
    assert r.convergido


def test_el_informe_lo_presenta_y_el_cierre_lo_lee(m06):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(m06, run_meg=False)
    s, rec = d.summary, d.recommendation
    assert "no existe en esta corrida" not in s
    assert "raíz real sale NEGATIVA" in s
    assert "el lado AR no apoya d+1" in s
    # el DCD de sobrediferenciación pide d+1 y el lado AR no: el par discrepa
    assert "NO lo apoya" in rec
