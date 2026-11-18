"""BUG-0060 — un error típico inválido no puede imprimirse como uno válido.

BUG-0027 ya detectaba la covarianza-semilla y lo avisaba DEBAJO del bloque.
Dentro del cerco la cifra salía con el mismo formato que una legítima, y de ahí
se calcula un t. Sobre ITCER_m00mu: t=−4.64 impreso, −2.43 el honesto.
"""
import math
import os
import warnings

import numpy as np
import pytest

import fue
from art.describe import model_equation
from art.diagnosis import bfgs_seed_var

from datos_replica import REPLICA, REPLICA_DS


R = REPLICA


def _cargar(rel):
    p = R + rel
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    return _load_fitted(p)


def _n_semilla(m):
    s = math.sqrt(bfgs_seed_var(m._result))
    return sum(1 for se in m.std_errors if abs(abs(float(se)) - s) <= 1e-4 * s)


@pytest.mark.parametrize("rel", ["run3/ITCER/ITCER_m00mu.pre",
                                 "run3/PGAS/PGAS_m03.pre",
                                 "guiado/RATIO/RATIO_m31.pre"])
def test_se_marcan_exactamente_los_que_son_semilla(rel):
    ts, m = _cargar(rel)
    eq = model_equation(ts, m)
    assert eq.count("(✗") == _n_semilla(m)


def test_la_degeneracion_parcial_no_marca_los_validos():
    """niter=1: dos de tres. El AR(1) sí estimó su varianza y no debe marcarse."""
    ts, m = _cargar("run3/PGAS/PGAS_m03.pre")
    if _n_semilla(m) != 2:
        # Ya no es un testigo: con fue >= 0.1.17 los errores típicos son del
        # hessiano por diferencias y no hay semilla. La lógica la guarda
        # test_sintetico_degeneracion_parcial.
        pytest.skip("el testigo de la réplica ya no tiene errores típicos en la "
                    "semilla: no mide nada (la guarda el caso sintético)")
    eq = model_equation(ts, m)
    assert eq.count("(✗") == 2
    assert "(0.0786)" in eq, "el error típico válido debe salir SIN marcar"


def test_la_leyenda_acompaña_al_marcador():
    ts, m = _cargar("run3/ITCER/ITCER_m00mu.pre")
    if not _n_semilla(m):
        pytest.skip("el testigo de la réplica ya no tiene errores típicos en la "
                    "semilla: no mide nada (lo guarda el caso sintético)")
    eq = model_equation(ts, m)
    assert "NO VÁLIDO" in eq
    assert "semilla del BFGS" in eq
    assert "No calcules t con él" in eq


def test_se_publica_el_error_tipico_honesto_de_mu():
    """Sin ARMA libre, μ es la media muestral y su SE exacto es σ̂ₐ/√n."""
    ts, m = _cargar("run3/ITCER/ITCER_m00mu.pre")
    if not _n_semilla(m):
        pytest.skip("el testigo de la réplica ya no tiene errores típicos en la "
                    "semilla: no mide nada (lo guarda el caso sintético)")
    r = m._result
    n = len(np.asarray(r.residuals, dtype=float))
    se_ok = math.sqrt(r.sigma2) / math.sqrt(n)
    eq = model_equation(ts, m)
    assert f"{se_ok:.4f}" in eq
    assert "el error típico correcto es" in eq
    # y el t que se publica es el honesto, no el de la semilla
    mu = float(m.params[0])
    assert f"{mu/se_ok:+.2f}" in eq


def test_con_ARMA_libre_no_se_inventa_un_SE_de_mu():
    """σ̂ₐ/√n sólo vale sin ARMA; con ARMA no se publica nada."""
    ts, m = _cargar("guiado/ITCER/ITCER_m20.pre")
    if _n_semilla(m) == 0:
        pytest.skip("este modelo no tiene errores típicos semilla")
    eq = model_equation(ts, m)
    assert "el error típico correcto es" not in eq


def test_un_modelo_sin_semilla_no_recibe_marcas():
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(11)
    a = rng.standard_normal(200)
    w = np.zeros(200)
    for t in range(1, 200):
        w[t] = 0.6 * w[t - 1] + a[t]
    ts = fue.TimeSeries((100 + np.cumsum(w) / 20).tolist(), freq=4,
                        start=(2000, 1), name="SIN")
    from art.pipeline import ModelSpec, build_and_fit
    import tempfile
    spec = ModelSpec(lam=1.0, d=1, D=0, p=1, q=0, P=0, Q=0, n_harmonics=0)
    fr = build_and_fit(ts, spec, tempfile.mktemp(suffix=".inp"), 3.5)
    if _n_semilla(fr.model):
        pytest.skip("la estimación dejó varianzas en la semilla")
    assert "(✗" not in model_equation(ts, fr.model)
    assert "NO VÁLIDO" not in model_equation(ts, fr.model)



# ── los mismos casos, construidos: no dependen de la réplica ───────────────
#
# Con fue >= 0.1.17 los errores típicos salen del hessiano por diferencias, que
# no tiene semilla; la marca sigue haciendo falta cuando fue cae al BFGS
# (se_method "bfgs (...)"). Aquí se pone un ajuste en ese estado: método BFGS y
# las varianzas elegidas exactamente en la semilla 2/n.

def _con_semilla(m, en_semilla):
    r = m._result
    n = len(np.asarray(r.residuals, dtype=float))
    cov = np.array(r.cov_matrix, dtype=float, copy=True)
    for i in en_semilla:
        cov[i, :] = 0.0
        cov[:, i] = 0.0
        cov[i, i] = 2.0 / n
    r.cov_matrix = cov
    r.std_errors = np.sqrt(np.diag(cov))
    r.se_method = "bfgs (fdhess: no salió)"
    return m


def _ajusta(con_ar, seed=3):
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(seed)
    y = 100.0 + np.cumsum(rng.standard_normal(120) + 0.3)
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")
    kw = dict(ar=[[0.0]], ar_free=[[True]]) if con_ar else {}
    m = fue.Model(ts, boxlam=1.0, d=1, mu=0.0, estimate_mu=True, **kw)
    m.fit()
    return ts, m


def test_sintetico_degeneracion_parcial():
    """Uno de dos en la semilla: se marca ése y sólo ése."""
    ts, m = _ajusta(con_ar=True)
    _con_semilla(m, [1])
    assert _n_semilla(m) == 1
    eq = model_equation(ts, m)
    assert eq.count("(✗") == 1
    valido = float(m.std_errors[0])
    assert f"({valido:.4f})" in eq, "el error típico válido debe salir SIN marcar"


def test_sintetico_la_leyenda_acompaña_al_marcador():
    ts, m = _ajusta(con_ar=True)
    _con_semilla(m, [0, 1])
    eq = model_equation(ts, m)
    assert eq.count("(✗") == 2
    assert "NO VÁLIDO" in eq and "semilla del BFGS" in eq and "No calcules t con él" in eq


def test_sintetico_el_error_tipico_honesto_de_mu():
    """Sin ARMA, μ es la media muestral y su SE exacto es σ̂ₐ/√n; se publica, y
    el t que se imprime es el honesto, no el de la semilla."""
    ts, m = _ajusta(con_ar=False)
    _con_semilla(m, [0])
    r = m._result
    n = len(np.asarray(r.residuals, dtype=float))
    se_ok = math.sqrt(r.sigma2) / math.sqrt(n)
    eq = model_equation(ts, m)
    assert f"{se_ok:.4f}" in eq and "el error típico correcto es" in eq
    assert f"{float(m.params[0]) / se_ok:+.2f}" in eq


def test_sintetico_con_ARMA_no_se_inventa_un_SE_de_mu():
    ts, m = _ajusta(con_ar=True)
    _con_semilla(m, [0, 1])
    assert "el error típico correcto es" not in model_equation(ts, m)


def test_sintetico_con_fdhess_no_hay_marcas():
    ts, m = _ajusta(con_ar=True)
    assert m._result.se_method == "fdhess"
    assert "(✗" not in model_equation(ts, m)
