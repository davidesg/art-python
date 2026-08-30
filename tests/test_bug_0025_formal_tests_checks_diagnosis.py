"""BUG-0025 — `formal_tests` firmaba "el modelo es adecuado" sin mirar la diagnosis.

Los contrastes formales son la ÚLTIMA etapa: sus nulas se derivan bajo residuos
que son ruido blanco. La capa guiada de ART ya lo decía tres veces («el MEG
evalúa AL FINAL», «B) Contrastes formales SI LOS RESIDUOS ESTÁN LIMPIOS»), pero
era prosa — el motor no la comprobaba, así que la condición no cerraba nada.

Mismo principio que BUG-0010: si algo queda sin contrastar —allí una frecuencia,
aquí la adecuación entera— el informe no puede terminar en "el modelo es
adecuado".
"""
import os
import tempfile

import numpy as np
import pytest

from art import mcp_server as A
from art.pipeline import _load_ts_model
from art.diagnosis import diagnose
from art.describe import describe_formal_tests

ADECUADO = "El modelo es adecuado"
AVISO    = "todavía NO es adecuado"


def _ajusta(a, tag):
    """Paseo aleatorio con las innovaciones dadas, ajustado con ARIMA(0,1,0)."""
    y = 100.0 + np.cumsum(a)
    d = tempfile.mkdtemp(prefix=f"bug0025-{tag}-")
    inp = os.path.join(d, "S.inp")
    A.create_inp(list(map(float, y)), inp, name="S", freq=4,
                 start_year=1990, start_period=1)
    out = os.path.join(d, "S_m00.inp")
    A.confirm_and_estimate(inp_path=inp, output_path=out, lam=1.0, d=1, D=0,
                           p=0, q=0, n_harmonics=0, seasonal=False,
                           estimate_mu=False)
    ts, m = _load_ts_model(out.replace(".inp", ".pre"))
    m.fit()
    return m


@pytest.fixture(scope="module")
def modelo_inadecuado():
    """Un anómalo enorme sin tratar: la Q y la normalidad se hunden."""
    rng = np.random.default_rng(12)
    a = rng.normal(0, 1.0, 120)
    a[60] = 9.0
    return _ajusta(a, "malo")


@pytest.fixture(scope="module")
def modelo_limpio():
    """Semilla 7: JB p=0.963, Q mín p=0.486, sin residuos extremos."""
    rng = np.random.default_rng(7)
    return _ajusta(rng.normal(0, 1.0, 120), "bueno")


def test_el_caso_sigue_siendo_el_que_muerde(modelo_inadecuado):
    dg = diagnose(modelo_inadecuado)
    assert dg.jb_pvalue <= 0.05
    assert dg.extreme                      # hay residuos extremos sin tratar


def test_no_firma_que_el_modelo_es_adecuado(modelo_inadecuado):
    r = describe_formal_tests(modelo_inadecuado, run_meg=True)
    assert ADECUADO not in r.recommendation
    assert "aún no es adecuado" in r.recommendation


def test_el_aviso_va_arriba_del_informe(modelo_inadecuado):
    r = describe_formal_tests(modelo_inadecuado, run_meg=True)
    assert AVISO in r.summary
    # antes de cualquier estadístico: lo que está en cuestión es si se pueden leer
    assert r.summary.index(AVISO) < r.summary.index("**DCD")


def test_data_expone_el_estado_de_la_diagnosis(modelo_inadecuado):
    r = describe_formal_tests(modelo_inadecuado, run_meg=True)
    assert r.data["diagnosis_ok"] is False
    assert r.data["diagnosis_failures"]


def test_un_modelo_limpio_conserva_el_cierre(modelo_limpio):
    """El control: donde la diagnosis pasa, nada cambia respecto de antes."""
    dg = diagnose(modelo_limpio)
    assert dg.jb_pvalue > 0.05
    assert not dg.extreme
    assert min(dg.q_pvalues) > 0.05
    r = describe_formal_tests(modelo_limpio, run_meg=True)
    assert r.data["diagnosis_ok"] is True
    assert AVISO not in r.summary
    assert ADECUADO in r.recommendation
