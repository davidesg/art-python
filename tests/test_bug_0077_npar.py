"""BUG-0077 — la corrección de g.l. del Ljung-Box cuenta lo que no debe.

`_npar` contaba coeficientes ARMA **fijos** —incluido el artificio `ar=[[0.0]]`
con `ar_free=[[False]]` que la interfaz mete cuando no hay ARMA que estimar— y
además contaba **μ**, que el motor no resta.

El sesgo era sistemático y crecía con el modelo: cada determinista y cada
coeficiente fijo restaba un grado de libertad de más, así que **cuantos más
deterministas llevaba un modelo, más inadecuado parecía**.

El árbitro es el `.out` del motor, como en BUG-0074 y BUG-0075.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")
from art.diagnosis import diagnose, _npar


def _ts(n=120, semilla=4):
    y = np.cumsum(np.random.default_rng(semilla).standard_normal(n))
    return fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="S")


def test_un_coeficiente_FIJO_no_consume_grado_de_libertad():
    """El artificio `ar=[[0.0]]` con flag False aparece constantemente."""
    m = fue.Model(_ts(), d=1, mu=0.0, estimate_mu=False,
                  ar=[[0.0]], ar_free=[[False]])
    m.fit()
    assert _npar(m) == 0


def test_un_coeficiente_LIBRE_si_lo_consume():
    m = fue.Model(_ts(), d=1, mu=0.0, estimate_mu=False,
                  ar=[[0.3]], ar_free=[[True]])
    m.fit()
    assert _npar(m) == 1


def test_la_media_NO_se_resta():
    """La corrección clásica es m − p − q: los órdenes ARMA. El motor no
    resta μ, y su `.out` sobre ITCER m01 (μ libre, sin ARMA) da DF = lags."""
    m = fue.Model(_ts(), d=1, estimate_mu=True, ar=[[0.0]], ar_free=[[False]])
    m.fit()
    assert _npar(m) == 0, "μ no entra en la corrección"
    dg = diagnose(m)
    assert [l - dg.npar for l in dg.q_lags] == list(dg.q_lags)


def test_una_mezcla_de_libres_y_fijos_cuenta_solo_los_libres():
    m = fue.Model(_ts(), d=1, mu=0.0, estimate_mu=False,
                  ar=[[0.3, 0.0]], ar_free=[[True, False]])
    m.fit()
    assert _npar(m) == 1


def test_ar_y_ma_libres_suman():
    m = fue.Model(_ts(), d=1, mu=0.0, estimate_mu=False,
                  ar=[[0.3]], ar_free=[[True]],
                  ma=[[0.2]], ma_free=[[True]])
    m.fit()
    assert _npar(m) == 2


def test_el_sesgo_crecia_con_los_deterministas():
    """Lo que el bug hacía: μ + artificio fijo restaban 2 g.l. de un modelo
    que no tiene ningún parámetro ARMA libre. Sobre ITCER invertía el
    veredicto — p=0,0337 con df=2 frente a p=0,1478 con df=4."""
    m = fue.Model(_ts(), d=1, estimate_mu=True, ar=[[0.0]], ar_free=[[False]])
    m.fit()
    dg = diagnose(m)
    from scipy import stats
    q4 = dg.q_stats[0]
    p_bien = float(stats.chi2.sf(q4, dg.q_lags[0]))
    p_mal = float(stats.chi2.sf(q4, dg.q_lags[0] - 2))
    assert dg.q_pvalues[0] == pytest.approx(p_bien, abs=1e-9)
    assert p_mal < p_bien, "el bug siempre empujaba hacia 'inadecuado'"


# ───────────────── la regla, enunciada y fijada ─────────────────
#
#   «Solamente tiene que restar los parámetros ARMA libres. La media y los
#    parámetros de intervención y/o estacionalidad determinista no cuentan.»
#
# Se fija caso a caso porque es exactamente lo que un refactor de `_npar`
# rompería sin enterarse: los tres bloques viven en sitios distintos del
# modelo —μ en `mu0`, intervenciones y armónicos en `interventions`, ARMA en
# `ar`/`ma`— y sólo el último entra.

def _con(**kw):
    m = fue.Model(_ts(), d=1, **kw)
    m.fit()
    return m


def test_la_media_libre_no_cuenta():
    assert _npar(_con(ar=[[0.0]], ar_free=[[False]], estimate_mu=True)) == 0


def test_las_intervenciones_no_cuentan():
    m = _con(ar=[[0.0]], ar_free=[[False]], estimate_mu=True,
             interventions=[
                 fue.Intervention("impulse", at=40, omega=[0.0], omega_free=[True]),
                 fue.Intervention("step", at=60, omega=[0.0, 0.0],
                                  omega_free=[True, True])])
    assert _npar(m) == 0, "tres ω libres de intervención, y ninguno cuenta"


def test_la_estacionalidad_determinista_no_cuenta():
    m = _con(ar=[[0.0]], ar_free=[[False]], estimate_mu=True,
             interventions=[fue.Intervention("cos", harmonic=1.0, omega=[0.1]),
                            fue.Intervention("sin", harmonic=1.0, omega=[0.1]),
                            fue.Intervention("alter", omega=[0.1])])
    assert _npar(m) == 0


def test_solo_el_ARMA_libre_cuenta_con_todo_lo_demas_presente():
    m = _con(ar=[[0.3]], ar_free=[[True]], estimate_mu=True,
             interventions=[fue.Intervention("impulse", at=40, omega=[0.0],
                                             omega_free=[True]),
                            fue.Intervention("cos", harmonic=1.0, omega=[0.1])])
    assert _npar(m) == 1, "μ, una intervención y un armónico presentes; sólo el AR"


def test_arma_estacional_tambien_cuenta():
    m = _con(ar=[[0.3, 0.2]], ar_free=[[True, True]],
             ma=[[0.2]], ma_free=[[True]], estimate_mu=True)
    assert _npar(m) == 3
