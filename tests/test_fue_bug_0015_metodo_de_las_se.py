"""fue/BUG-0015 arreglado: art mira QUÉ hessiano dio los errores típicos.

Desde fue 0.1.17 cada ajuste dice su método en `FitResult.se_method` —"fdhess",
"bfgs (fdhess: …)" o "none (…)"— y el `.out` lo escribe como
"Standard errors: <método>". Las defensas de art contra la semilla del BFGS
(BUG-0027, 0041, 0060, 0090, 0091, 0159, 0168) se aplican SÓLO cuando el método
no es "fdhess": con un fue anterior (sin `se_method`) o cuando fue cae al BFGS.
"""
import os
import types
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art import diagnosis as D  # noqa: E402
from art import pipeline as P  # noqa: E402
from art.outfile import AVISO_OUT_BFGS, aviso_out, lee_out  # noqa: E402

nuevo = pytest.mark.skipif(not D.fue_calcula_hessiano(),
                           reason="el fue instalado es anterior a 0.1.17")


def _res(metodo=None, niter=0, n=100, k=3):
    """Un resultado mínimo: covarianza EXACTAMENTE en la semilla 2/n."""
    r = types.SimpleNamespace(residuals=np.zeros(n), niter=niter, npar=k,
                              cov_matrix=np.eye(k) * (2.0 / n))
    if metodo is not None:
        r.se_method = metodo
    return r


# ───────────── la lógica, sin motor ─────────────

def test_sin_metodo_todo_sigue_como_estaba():
    """fue < 0.1.17: niter=0 y la semilla siguen siendo degeneración."""
    r = _res()
    assert D.metodo_se(r) is None
    assert D.covariance_is_degenerate(r)
    assert D.degenerate_variance_indices(r) == [0, 1, 2]


def test_con_fdhess_no_hay_semilla_que_buscar():
    """La misma covarianza, declarada como curvatura en el óptimo, no se marca:
    con fdhess, niter=0 (arrancar en el óptimo) ya no significa nada."""
    r = _res("fdhess")
    assert D.se_del_hessiano(r)
    assert not D.covariance_is_degenerate(r)
    assert D.degenerate_variance_indices(r) == []
    assert D.near_seed_variance_indices(r) == []


def test_si_fue_cae_al_bfgs_las_defensas_vuelven():
    r = _res("bfgs (fdhess: the Hessian is not positive definite)")
    assert not D.se_del_hessiano(r)
    assert D.covariance_is_degenerate(r)
    assert D.aviso_covarianza(r) == D.AVISO_COV_DEGENERADA


def test_sin_errores_tipicos_se_dice_eso_y_no_la_semilla():
    r = _res("none (fdhess: the Hessian is not positive definite; the search "
             "did not move, so it built no BFGS Hessian)", k=2)
    r.cov_matrix = np.full((2, 2), np.nan)
    assert D.se_ausentes(r)
    assert D.covariance_is_degenerate(r)
    assert D.aviso_covarianza(r) == D.AVISO_SE_AUSENTES
    assert "semilla" not in D.AVISO_SE_AUSENTES


def test_estimar_rechaza_el_pre_con_un_fue_anterior(tmp_path, monkeypatch):
    """La negativa de BUG-0159 sigue en pie donde tiene razón de ser."""
    f = tmp_path / "X.pre"
    f.write_text("no importa: se rechaza antes de leer\n")
    monkeypatch.setattr(D, "fue_calcula_hessiano", lambda: False)
    with pytest.raises(P.ErrorDeContrato, match=r"No se estima desde un"):
        P.estimar(str(f))


# ───────────── con el motor ─────────────

@pytest.fixture(scope="module")
def par(tmp_path_factory):
    """El modelo de BUG-0090 por las dos vías: estimado desde el .inp y desde
    su .pre (con fue ≥ 0.1.17, `estimar` acepta los dos)."""
    d = tmp_path_factory.mktemp("b15")
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.standard_normal(150) * 0.4) + 100.0
    y[80:] += 4.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="R15")
    itv = fue.Intervention("step", at=80, omega=[0.0, 0.0],
                           omega_free=[True, True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=False, interventions=[itv],
                  refactor=P._RESCALE_FACTOR)
    f_inp = str(d / "R15.inp")
    P._write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m_inp = P.estimar(f_inp)
        f_pre = str(d / "R15.pre")
        m_inp.write_pre(f_pre)
        m_inp.write_out(str(d / "R15.out"))
        _, m_pre = P.estimar(f_pre) if D.fue_calcula_hessiano() else P.mirar(f_pre)
    return m_inp, m_pre, f_inp, f_pre, str(d / "R15.out")


@nuevo
def test_estimar_acepta_el_pre_y_las_se_coinciden(par):
    """La razón del rechazo era que las SE del `.pre` no servían. Con fdhess
    coinciden con las del `.inp` — ésa es la prueba de que se puede aceptar."""
    m_inp, m_pre, _, _, _ = par
    assert D.se_del_hessiano(m_inp._result) and D.se_del_hessiano(m_pre._result)
    assert P.viene_de_pre(m_pre)
    np.testing.assert_allclose(m_pre._result.std_errors,
                               m_inp._result.std_errors, rtol=1e-3)
    assert P.aviso_se_no_fiable(m_pre) == ""


@nuevo
def test_el_out_nuevo_dice_fdhess_y_no_se_avisa(par):
    *_, f_out = par
    r = lee_out(f_out)
    assert r.metodo_se == "fdhess" and r.se_del_hessiano
    assert aviso_out(r) == ""


def test_un_out_sin_la_linea_es_del_bfgs_y_se_avisa(par, tmp_path):
    """Un `.out` de un fue anterior: se lee igual (es el registro) y se dice
    de dónde vienen sus desviaciones típicas."""
    *_, f_out = par
    viejo = tmp_path / "viejo.out"
    viejo.write_text("\n".join(l for l in open(f_out).read().splitlines()
                               if not l.startswith("Standard errors:")) + "\n")
    r = lee_out(str(viejo))
    assert r.metodo_se is None and r.parametros
    assert aviso_out(r) == AVISO_OUT_BFGS
