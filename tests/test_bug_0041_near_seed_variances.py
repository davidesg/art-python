"""BUG-0041 — la guarda de covarianza degenerada sólo cazaba la semilla EXACTA.

BUG-0027 detecta los errores típicos que son la semilla del BFGS (c·I, con
c = 2/n) en vez del hessiano, comparando con tolerancia `1e-5`: igualdad. Eso
caza la dirección que el optimizador no tocó nunca (`niter=0`) y nada más. Una
dirección que se movió un 7% tampoco lleva información del hessiano.

Testigo real: ITCER de la réplica, dos parámetros, `niter=2`. La varianza de μ
salió 0.022473 contra una semilla de 0.024096 — el 93%. El error típico publicado
fue 0.1499 cuando el correcto, para un modelo sin ARMA, es σ_a/√n = 0.2864: la
mitad, sin aviso. Con `niter=5` el mismo modelo dio 0.2687, que sí coincide.

Es SOSPECHA y no veredicto: una varianza puede valer 2/n legítimamente, y
marcarla como inválida sería un falso positivo caro. Lo que se publica es la
distancia relativa.
"""
import numpy as np
import pytest

from art.diagnosis import (BANDA_CASI_SEMILLA, bfgs_seed_var,
                           covariance_is_degenerate,
                           degenerate_variance_indices,
                           near_seed_distances,
                           near_seed_variance_indices)


class _Res:
    def __init__(self, n, varianzas, niter=1):
        self.residuals = np.zeros(n)
        self.cov_matrix = np.diag(np.asarray(varianzas, dtype=float))
        self.niter = niter
        self.npar = len(varianzas)


N = 83
SEMILLA = 2.0 / N


def test_the_seed_is_two_over_n():
    assert bfgs_seed_var(_Res(N, [1.0])) == pytest.approx(SEMILLA)


def test_the_witness_at_93_percent_is_flagged():
    """El caso real: no es la semilla exacta, así que BUG-0027 lo dejaba pasar."""
    r = _Res(N, [3.404577, 0.022473], niter=2)
    assert degenerate_variance_indices(r) == []
    assert not covariance_is_degenerate(r)
    assert near_seed_variance_indices(r) == [1]
    assert near_seed_distances(r)[1] == pytest.approx(-0.0673, abs=1e-3)


def test_an_exact_seed_is_not_reported_twice():
    """La degeneración exacta ya tiene su veredicto; no debe salir además como
    sospecha, o el mismo parámetro se avisaría dos veces con fuerzas distintas."""
    r = _Res(N, [SEMILLA], niter=0)
    assert degenerate_variance_indices(r) == [0]
    assert near_seed_variance_indices(r) == []


def test_a_variance_that_really_moved_is_clean():
    r = _Res(N, [5.992264, 0.072188], niter=5)
    assert degenerate_variance_indices(r) == []
    assert near_seed_variance_indices(r) == []


def test_the_band_is_relative_and_symmetric():
    """Dentro de la banda por arriba y por abajo; fuera, nada."""
    dentro_bajo = SEMILLA * (1 - BANDA_CASI_SEMILLA * 0.5)
    dentro_alto = SEMILLA * (1 + BANDA_CASI_SEMILLA * 0.5)
    fuera = SEMILLA * (1 + BANDA_CASI_SEMILLA * 2)
    r = _Res(N, [dentro_bajo, dentro_alto, fuera])
    assert near_seed_variance_indices(r) == [0, 1]


def test_no_result_no_crash():
    assert near_seed_variance_indices(None) == []
    assert near_seed_distances(None) == {}


def test_the_real_witness_end_to_end(tmp_path):
    """Sobre el fichero de la réplica, si sigue estando."""
    import os
    import fue
    ruta = ("/home/david/Dropbox/TFM_UCM/Tesis_Michael/replica/limpio/"
            "ITCER/ITCER_m01.inp")
    if not os.path.exists(ruta):
        pytest.skip("el testigo de la réplica no está en esta máquina")
    _ts, m = fue.load(ruta)
    m.fit()
    casi = near_seed_variance_indices(m._result)
    assert casi, "el testigo dejó de disparar la sospecha"
    # y el error típico sospechoso es, en efecto, la mitad del correcto
    r = np.asarray(m.residuals.data, float)
    correcto = r.std(ddof=1) / np.sqrt(len(r))
    publicado = list(m.std_errors)[casi[0]]
    assert publicado < 0.7 * correcto
