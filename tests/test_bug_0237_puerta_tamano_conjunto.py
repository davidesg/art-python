"""BUG-0237 — la puerta de adecuación sin corrección por multiplicidad.

La adecuación (`DiagnosisResult.clean`, la puerta de `formal_tests`) es UNA
afirmación hecha con k contrastes —Q en 3f+3, JB, media residual y, con f > 1,
estacionalidad residual—, cada uno al 5 %: tamaño conjunto ~16 % medido, y 5 de
21 modelos VERDADEROS «todavía NO adecuados». Ahora cada criterio va al 5 %/k
(Bonferroni) y lo que rechaza al 5 % aislado se dice como salvedad.
"""
import dataclasses
import os
import warnings

import numpy as np
import pytest
from scipy.signal import lfilter

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.describe import describe_formal_tests
from art.diagnosis import ALFA_ADECUACION, alfa_por_criterio, diagnose
from art.pipeline import _make_model


def _ajusta(x, d, p, q, freq=12):
    ts = fue.TimeSeries([float(v) for v in x], freq=freq, start=(2000, 1), name="S")
    m = _make_model(ts, lam=1.0, d=d, D=0, p=p, q=q, n_harmonics=0,
                    estimate_mu=(d == 0))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m.fit()
    return m


@pytest.fixture(scope="module")
def ruido():
    rng = np.random.default_rng(237)
    return diagnose(_ajusta(rng.normal(size=200) + 100.0, d=0, p=0, q=0))


def test_el_nivel_de_cada_criterio_es_5_entre_k():
    assert alfa_por_criterio(12) == pytest.approx(0.05 / 4)
    assert alfa_por_criterio(4) == pytest.approx(0.05 / 4)
    assert alfa_por_criterio(1) == pytest.approx(0.05 / 3)


def test_diagnose_pone_el_nivel_de_la_puerta(ruido):
    assert ruido.alfa == pytest.approx(0.0125)


def test_un_p_de_003_en_la_q_es_salvedad_no_bloqueo(ruido):
    ps = list(ruido.q_pvalues)
    ps[-1] = 0.03
    g = dataclasses.replace(ruido, q_pvalues=ps, jb_pvalue=0.5, mean_t=0.0)
    assert g.white_noise
    assert any(r.startswith("Q(") for r in g.rechazos_aislados)
    # el mismo resultado con el 5 % por criterio (lo de antes) bloqueaba
    assert not dataclasses.replace(g, alfa=ALFA_ADECUACION).white_noise


def test_la_media_usa_el_cuantil_de_la_puerta(ruido):
    g = dataclasses.replace(ruido, mean_t=-2.18)
    assert g.centred and any("media" in r for r in g.rechazos_aislados)
    assert not dataclasses.replace(g, alfa=ALFA_ADECUACION).centred
    assert not dataclasses.replace(ruido, mean_t=-3.5).centred


def test_los_21_modelos_verdaderos_del_repro():
    """La batería de BUG-0236/0237 (N = 200, SEED = 2026): antes 5 de 21 con la
    puerta cerrada; con tamaño conjunto 5 % se esperan ~1."""
    N, SEED = 200, 2026
    estr = [([], []), ([0.6], []), ([0.95], []), ([0.5, 0.3], []),
            ([1.0, -0.5], []), ([], [0.5]), ([0.6], [0.3])]
    rng = np.random.default_rng(SEED)
    cerradas = 0
    for d in (0, 1, 2):
        for phi, theta in estr:
            a = rng.normal(size=N + 300)
            x = lfilter(np.r_[1, -np.array(theta, float)],
                        np.r_[1, -np.array(phi, float)], a)[300:]
            for _ in range(d):
                x = np.cumsum(x)
            x = x - x.min() + 100.0
            m = _ajusta(x, d, len(phi), len(theta))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                t = describe_formal_tests(m, run_meg=False).summary
            cerradas += "todavía NO es adecuado" in t
    assert cerradas <= 2, f"{cerradas} de 21 modelos verdaderos con la puerta cerrada"
