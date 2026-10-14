"""BUG-0250 — encadenar p = q = 0 sobre un base con AR conservaba el AR.

`_build_arma_on_model` promete SUSTITUIR el ARMA del base por (p, q, P, Q).
Con p = q = P = Q = 0 copiaba `m_base.ar` y `m_base.ar_free`: el AR(1) libre
del base seguía libre en el modelo «sin ARMA», y `confirm_and_estimate(...,
base_pre_path=..., p=0, q=0)` devolvía el mismo modelo. El relleno que fue
necesita es un AR(1) FIJO a cero.
"""
import numpy as np

from art.pipeline import _build_arma_on_model, _make_model


def _ts(n=120, seed=3):
    import fue
    rng = np.random.default_rng(seed)
    e = rng.normal(0, 1.0, n)
    w = np.zeros(n)
    for t in range(1, n):
        w[t] = 0.5 * w[t - 1] + e[t]
    return fue.TimeSeries(list(np.cumsum(w) + 100.0), freq=12, start=(2000, 1),
                          name="X")


def _libres(m):
    return [f for fac in (m.ar_free or []) for f in fac if f]


def test_p0_q0_sobre_un_ar1_no_deja_ar_libre():
    m = _make_model(_ts(), lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=0,
                    estimate_mu=False)
    m.fit()
    assert _libres(m), "precondición: el base tiene un AR libre"
    m2 = _build_arma_on_model(m, p=0, q=0)
    assert not _libres(m2), "p = q = 0 debe quitar el AR del base"
    assert [[float(c) for c in fac] for fac in m2.ar] == [[0.0]]


def test_p0_q0_el_modelo_estimado_no_lleva_ar():
    m = _make_model(_ts(), lam=1.0, d=1, D=0, p=1, q=0, n_harmonics=0,
                    estimate_mu=False)
    m.fit()
    m2 = _build_arma_on_model(m, p=0, q=0)
    m2.fit()
    assert all(abs(float(c)) == 0.0 for fac in m2.ar for c in fac)
