"""BUG-0021 — `formal_tests` reventaba con un AR(2) de raíces complejas.

El bloque «RV — frecuencia de AR(2)» de `describe.py` leía `r.freq_hat`; el
dataclass `RVResult` declara el campo como `freq_estimated`. `freq_hat` era el
nombre de la variable LOCAL en la rutina que lo construye, y se filtró a la
plantilla. La excepción sube desde `describe_formal_tests`, así que se perdía el
informe entero — Shin-Fuller y el DCD incluidos, ya calculados.

Sólo se activa con AR(2) **y** raíces complejas (φ₁² + 4φ₂ < 0): en cualquier
otro caso `rv_res` sale vacío, el bucle no itera y el atributo no se toca. De ahí
que la batería no lo cogiera.
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.describe import describe_formal_tests
from art.formal_tests import RVResult


def test_rvresult_expone_freq_estimated_y_no_freq_hat():
    """El contrato de nombres que se rompió, fijado por los dos lados."""
    campos = set(RVResult.__dataclass_fields__)
    assert "freq_estimated" in campos
    assert "freq_hat" not in campos


@pytest.fixture(scope="module")
def modelo_ar2_complejo():
    rng = np.random.default_rng(7)
    n = 120
    y = np.zeros(n)
    for t in range(2, n):
        y[t] = 1.55 * y[t - 1] - 0.68 * y[t - 2] + rng.normal(0, 1.0)
    y = y + 100.0

    d = tempfile.mkdtemp(prefix="bug0021-")
    inp = os.path.join(d, "SYN.inp")
    A.create_inp(list(map(float, y)), inp, name="SYN", freq=4,
                 start_year=1990, start_period=1)
    out = os.path.join(d, "SYN_ar2.inp")
    A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=0, D=0,
                           p=2, q=0, n_harmonics=0, seasonal=False,
                           estimate_mu=True)
    ts, m = _load_ts_model(out.replace(".inp", ".pre"))
    m.fit()
    return m


def test_ar2_es_de_raices_complejas(modelo_ar2_complejo):
    """Sin raíces complejas el RV no actúa y el test no probaría nada."""
    phi1, phi2 = modelo_ar2_complejo.ar[0]
    assert phi1 ** 2 + 4 * phi2 < 0


def test_formal_tests_no_revienta_y_emite_el_bloque_rv(modelo_ar2_complejo):
    r = describe_formal_tests(modelo_ar2_complejo, run_meg=False)   # no debe lanzar
    assert "RV — frecuencia de AR(2)" in r.summary
    assert "f̂=" in r.summary
    # y el informe que se perdía con la excepción sigue entero
    assert "Shin-Fuller" in r.summary
