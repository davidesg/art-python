"""BUG-0090 — estimar desde un `.pre` deja las desviaciones típicas mal.

El convenio: `.inp(t−1) → .pre(t−1) → .inp(t) → .pre(t)`. **Sólo el `.inp` se
usa para estimar**; el `.pre` sirve para modificar y crear el `.inp` siguiente.

Estimar desde un `.pre` arranca EN el óptimo, así que BFGS no itera y la
covarianza se queda en la semilla. Y lo que hace el fallo peligroso es que el
invariante del `.pre` **sí se cumple** sobre los valores: misma ℓ, mismos
coeficientes, misma ecuación. El fichero parece hacer round-trip.

La guarda no lo prohíbe —mirar residuos desde un `.pre` es legítimo— sino que
avisa DONDE SE IMPRIME una SE, que es lo que hace que el aviso responda su propia
pregunta: si estás viendo un error típico, te afecta.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import (_RESCALE_FACTOR, _load_fitted, _write_inp,
                          aviso_se_no_fiable, viene_de_pre)


@pytest.fixture(scope="module")
def par(tmp_path_factory):
    """El mismo modelo por las dos vías: (m_inp, m_pre, rutas)."""
    d = tmp_path_factory.mktemp("b90")
    rng = np.random.default_rng(7)
    y = np.cumsum(rng.standard_normal(150) * 0.4) + 100.0
    y[80:] += 4.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1985, 1), name="R90")
    itv = fue.Intervention("step", at=80, omega=[0.0, 0.0],
                           omega_free=[True, True])
    m = fue.Model(ts, d=1, ar=[[0.0]], ar_free=[[True]], mu=0.0,
                  estimate_mu=False, interventions=[itv],
                  refactor=_RESCALE_FACTOR)
    f_inp = str(d / "R90.inp")
    _write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, m_inp = _load_fitted(f_inp)
        f_pre = str(d / "R90.pre")
        m_inp.write_pre(f_pre)
        _, m_pre = _load_fitted(f_pre)
    return m_inp, m_pre, f_inp, f_pre


# ───────────── el defecto que se está cubriendo ─────────────

def test_los_valores_coinciden_y_por_eso_es_invisible(par):
    """El invariante del `.pre` se cumple sobre los valores. Ése es el problema:
    no hay nada en el modelo que delate la diferencia."""
    m_inp, m_pre, _, _ = par
    assert abs(m_inp._result.loglik - m_pre._result.loglik) < 1e-6
    assert np.allclose(m_inp._result.params, m_pre._result.params, atol=1e-6)


def test_las_desviaciones_tipicas_no_coinciden(par):
    m_inp, m_pre, _, _ = par
    a = np.asarray(m_inp._result.std_errors, dtype=float)
    b = np.asarray(m_pre._result.std_errors, dtype=float)
    peor = float(np.max(np.abs(b / np.where(a > 0, a, np.nan) - 1.0)))
    assert peor > 0.10, f"la fixture ya no separa las dos vías (peor {peor:.3f})"


# ───────────── la guarda ─────────────

def test_estimar_desde_un_pre_avisa(par):
    _, _, _, f_pre = par
    with pytest.warns(RuntimeWarning, match=r"\.pre"):
        _load_fitted(f_pre)


def test_estimar_desde_un_inp_no_avisa(par):
    _, _, f_inp, _ = par
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        _load_fitted(f_inp)


def test_el_modelo_lleva_su_origen(par):
    """En el OBJETO y no en una global: una global mutable ya se demostró el
    canal equivocado para esto mismo (BUG-0081)."""
    m_inp, m_pre, _, _ = par
    assert viene_de_pre(m_pre)
    assert not viene_de_pre(m_inp)


def test_un_modelo_sin_sello_no_dispara_nada():
    """Compatibilidad: un modelo construido a mano no viene de ningún fichero."""
    class _M:
        pass
    assert not viene_de_pre(_M())
    assert aviso_se_no_fiable(_M()) == ""


# ───────────── el aviso responde su propia pregunta ─────────────

@pytest.mark.parametrize("clave", ["valores", "figuras", "razones t", "`.out`",
                                   "`.inp`"])
def test_el_aviso_dice_a_que_afecta_y_a_que_no(par, clave):
    """Sin esto el LLM gasta tokens averiguando si el aviso le concierne, que es
    el coste que motivó todo esto."""
    _, m_pre, _, _ = par
    assert clave in aviso_se_no_fiable(m_pre)


def test_el_aviso_no_sale_cuando_no_toca(par):
    m_inp, _, _, _ = par
    assert aviso_se_no_fiable(m_inp) == ""


# ───────────── donde se imprime una SE ─────────────

def test_test_interventions_lo_dice(par):
    """Su salida es ENTERA razones t y un Wald: no hay nada que se salve."""
    import art.mcp_server as srv
    _, _, f_inp, f_pre = par
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t_pre = "\n".join(getattr(c, "text", "") for c in fn(f_pre))
        t_inp = "\n".join(getattr(c, "text", "") for c in fn(f_inp))
    assert "NO son fiables" in t_pre
    assert "NO son fiables" not in t_inp


def test_la_ecuacion_lo_dice(par):
    """El embudo de seis herramientas: la ecuación imprime cada coeficiente con
    su error típico debajo."""
    import art.mcp_server as srv
    _, m_pre, _, _ = par
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = srv._equation_for_prompt(m_pre.series, m_pre)
    assert "NO son fiables" in t


def test_el_origen_es_la_causa_no_el_sintoma(par):
    """La maquinaria de BUG-0027/0041 detecta que la covarianza SE PARECE a la
    semilla — una heurística que sobre FOOD_UEM m06 no salta porque las SE sólo
    se mueven un 12%. El sello sabe de qué fichero vino, que es exacto. Son
    complementarios, no redundantes."""
    from art.diagnosis import covariance_is_degenerate
    _, m_pre, _, _ = par
    assert viene_de_pre(m_pre)
    # el síntoma puede o no dispararse; el origen siempre es exacto
    covariance_is_degenerate(m_pre._result)   # no debe reventar


# ───────────── el hallazgo del repro: la guarda que se tragaba otra guarda ────

def test_no_se_dice_que_no_hay_intervenciones_cuando_las_hay(par):
    """El defecto de verdad, y es peor que una SE mal.

    `test_intervention` YA detecta la covarianza degenerada y levanta un
    ValueError cuyo mensaje nombra esta situación exacta —«la estimación arrancó
    ya en el óptimo, que es lo que un `.pre` es por diseño»—. Y
    `simplify_interventions` lo capturaba con un `except Exception: pass`.

    Resultado: sobre un modelo estimado desde un `.pre`, `test_interventions`
    respondía «No hay intervenciones no-estructurales en el modelo» teniendo una
    delante. art sabía lo que pasaba y lo tiraba tres líneas más allá.
    """
    import art.mcp_server as srv
    _, _, _, f_pre = par
    fn = getattr(srv.test_interventions, "fn", srv.test_interventions)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = "\n".join(getattr(c, "text", "") for c in fn(f_pre))
    assert "No hay intervenciones" not in t
    assert "no se pudo contrastar" in t or "NINGUNA se pudo contrastar" in t


def test_los_fallos_se_recogen_con_su_motivo(par):
    """Una guarda que calla convierte un fallo en una ausencia, y una ausencia
    se lee como «no hay nada que ver»."""
    from art.interventions import simplify_interventions
    _, m_pre, _, _ = par
    fallos: list = []
    res = simplify_interventions(m_pre, fallos=fallos)
    assert not res
    assert fallos
    i, tipo, motivo = fallos[0]
    assert tipo == "step"
    assert "BUG-0027" in motivo or "semilla" in motivo


def test_sin_la_lista_el_comportamiento_no_cambia(par):
    """Compatibilidad: `fallos` es opcional y los 5 llamantes de las pruebas
    existentes no lo pasan."""
    from art.interventions import simplify_interventions
    m_inp, _, _, _ = par
    assert len(simplify_interventions(m_inp)) == 1
