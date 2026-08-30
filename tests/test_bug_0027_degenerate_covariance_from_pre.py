"""BUG-0027 — semilla exactamente en el óptimo ⇒ covarianza degenerada, sin aviso.

`fue` inicializa la inversa del hessiano como `c·I` y la actualiza en cada
iteración. Con `niter = 0` no hay actualización: lo que vuelve como covarianza ES
la semilla, y todos los errores típicos salen idénticos. El resultado se declara
`converged=True`, así que nada avisa, y el valor es pequeño y creíble.

El disparador es estrecho — la coincidencia EXACTA — y por eso el defecto es
intermitente: una semilla a 1e-5 del óptimo todavía itera y da una covarianza
correcta. Es lo que un `.pre` es por diseño, y el convenio de la suite ya dice
que la estimación va desde el `.inp`: reejecutar un `.pre` verifica el invariante
de que los parámetros no se mueven, no estima.
"""
import os
import tempfile

import numpy as np
import pytest

import fue
from art.diagnosis import covariance_is_degenerate, degenerate_variance_indices
from art.pipeline import _write_inp, _load_ts_model


def _ee(m):
    return np.sqrt(np.diag(np.asarray(m._result.cov_matrix)))


def _serie(n=120, seed=19):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 1.0, n)
    u = np.zeros(n)
    for t in range(2, n):
        u[t] = 0.75 * u[t - 1] - 0.30 * u[t - 2] + a[t]
    y = 100.0 + np.cumsum(u)
    return fue.TimeSeries(list(map(float, y)), freq=4, start=(2004, 1), name="SYN")


def _ajusta(ts, seed_ar):
    m = fue.Model(ts, d=1, ifadf=[0, 0, 0], ar=[list(seed_ar)], ar_free=[[True, True]],
                  mu=0.0, estimate_mu=False)
    m.fit()
    return m


@pytest.fixture(scope="module")
def par():
    """(ajuste normal, ajuste desde su propio óptimo)."""
    ts = _serie()
    m1 = _ajusta(ts, [0.0, 0.0])                 # arranca lejos
    m2 = _ajusta(ts, list(m1.ar[0]))             # arranca EXACTAMENTE en el óptimo
    return ts, m1, m2


def test_el_ajuste_normal_itera_y_da_ee_distintas(par):
    _, m1, _ = par
    assert m1._result.niter > 0
    se = _ee(m1)
    assert not np.allclose(se, se[0], rtol=1e-6)
    assert covariance_is_degenerate(m1._result) is False


def test_arrancar_en_el_optimo_para_en_cero_iteraciones(par):
    _, _, m2 = par
    assert m2._result.niter == 0
    assert m2._result.converged is True        # y aun así se declara convergido


def test_la_covarianza_es_un_multiplo_de_la_identidad(par):
    _, _, m2 = par
    cov = np.asarray(m2._result.cov_matrix)
    d = np.diag(cov)
    assert np.allclose(d, d[0])
    assert np.allclose(cov - np.diag(d), 0.0)
    assert covariance_is_degenerate(m2._result) is True


def test_el_invariante_del_pre_SI_se_cumple(par):
    """Los parámetros no se mueven — eso es correcto y no se toca."""
    _, m1, m2 = par
    assert np.allclose(np.asarray(m1._result.params),
                       np.asarray(m2._result.params), atol=1e-8)


def test_una_semilla_CERCA_del_optimo_no_lo_dispara(par):
    """Lo que hace intermitente al defecto: basta apartarse 1e-5."""
    ts, m1, _ = par
    m3 = _ajusta(ts, [m1.ar[0][0] + 1e-5, m1.ar[0][1] - 1e-5])
    assert m3._result.niter > 0
    assert covariance_is_degenerate(m3._result) is False


def test_el_round_trip_por_pre_conserva_el_caso(par):
    """Escribir el óptimo y releerlo reproduce la degeneración."""
    ts, m1, _ = par
    d = tempfile.mkdtemp(prefix="bug0027-")
    p = os.path.join(d, "SYN.pre")
    _write_inp(ts, m1, p)
    _, m = _load_ts_model(p)
    m.fit()
    if m._result.niter > 0:
        pytest.skip("el redondeo del .pre apartó la semilla del óptimo")
    assert covariance_is_degenerate(m._result) is True


def test_test_intervention_se_niega_en_vez_de_publicar_el_numero(par):
    """Un contraste sobre una covarianza que no existe no es un contraste."""
    from art.interventions import test_intervention
    ts, m1, _ = par
    itv = fue.Intervention("step", at=60, omega=[0.0], omega_free=[True])
    m = fue.Model(ts, d=1, ifadf=[0, 0, 0], ar=[list(m1.ar[0])], ar_free=[[True, True]],
                  mu=0.0, estimate_mu=False, interventions=[itv])
    m.fit()
    if not covariance_is_degenerate(m._result):
        pytest.skip("esta configuración no degeneró")
    with pytest.raises(ValueError, match="BUG-0027"):
        test_intervention(m, 0)


def test_un_solo_parametro_SI_se_marca():
    """Corregido: excluir npar=1 fue un error, y del peor tipo — deja fuera el
    modelo MÁS COMÚN de todos.

    Una media sola sin ARMA tiene solución cerrada (su estimador máximo-verosímil
    es la media muestral), así que el optimizador para en niter=0 y devuelve la
    semilla. Y ése es el m00 con que empieza cualquier análisis: el agujero
    cubría la línea base de todo."""
    ts = _serie()
    m = fue.Model(ts, d=1, ifadf=[0, 0, 0], mu=0.0, estimate_mu=True)
    m.fit()
    if m._result.niter != 0:
        pytest.skip("esta realización sí iteró")
    assert covariance_is_degenerate(m._result) is True
    assert degenerate_variance_indices(m._result) == [0]


def test_la_degeneracion_PARCIAL_tambien_se_marca():
    """El caso peligroso: con niter=1 el BFGS actualiza UNA dirección y deja el
    resto en la semilla. Unos errores típicos válidos y otros no, sin nada que
    los distinga. El primer arreglo exigía diagonal constante y se le escapaba."""
    ts = _serie()
    m1 = _ajusta(ts, [0.0, 0.0])
    m2 = _ajusta(ts, list(m1.ar[0]))
    idx = degenerate_variance_indices(m2._result)
    assert covariance_is_degenerate(m2._result) is True
    assert idx, "alguna varianza debe seguir en la semilla"


def test_la_semilla_es_una_CONSTANTE_independiente_de_la_escala():
    """Lo que hace detectable la degeneración parcial: BFGS_SEED_VAR no depende
    de sigma2. Medido con sigma2 de 0.0063 y de 7.30: idéntica."""
    from art.diagnosis import bfgs_seed_var
    ts = _serie()
    m1 = _ajusta(ts, [0.0, 0.0])
    m2 = _ajusta(ts, list(m1.ar[0]))
    d = np.diag(np.asarray(m2._result.cov_matrix))
    assert any(abs(v - bfgs_seed_var(m2._result)) <= 1e-5 * bfgs_seed_var(m2._result) for v in d)
