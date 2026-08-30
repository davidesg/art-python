"""BUG-0034 — encadenar ARMA perdía los operadores de FRECUENCIA FIJA.

`fue` guarda en bloques propios del `.inp` —"AR(2)/MA(2) operators with fixed
frequency"— los factores anclados a una frecuencia estacional, que en el modelo
son `m.ar_f` y `m.ma_f` (listas de `FixedFreqFactor`), NO dentro de `ar_s`/`ma_s`.

Ahí vive el **testigo MA_f** que `meg_reformulate` añade junto a `ifadf[f]=1`, y
los dos son un solo objeto: la raíz unitaria estacional MÁS su testigo libre es
el modelo S de estacionalidad estocástica que contrasta el MEG; la misma raíz
sin testigo es la forma AR-only, que sobrediferencia la estacional.

`_build_arma_on_model` heredaba `interventions`, `ifadf` y `mu`, y no mencionaba
`ar_f` ni `ma_f`, así que los perdía en TODO encadenamiento.

Testigo real: RATIO (Gasto/PIB Bolivia) de la réplica del TFM. Añadir un MA(1)
regular al modelo reformulado por el MEG daba σ̂ₐ 4,1153% → 5,5173%, AIC
474,40 → 519,21 y un Q-test que pasaba de fallar en un retardo a fallar en 2, 4,
8 y 12 — en silencio. Con el arreglo el mismo paso da AIC 470,95 y Q p-mín
0,2730: el modelo que el analista quería y no podía construir.
"""
import os

import numpy as np
import pytest

import fue
from art.pipeline import _build_arma_on_model, _write_inp, _load_fitted
from art.diagnosis import diagnose


def _serie(n=120, seed=4):
    rng = np.random.default_rng(seed)
    a = np.cumsum(rng.standard_normal(n)) * 0.6
    b = np.cumsum(rng.standard_normal(n)) * 0.6
    t = np.arange(n)
    est = a * np.cos(np.pi / 2 * t) + b * np.sin(np.pi / 2 * t)
    nivel = 100.0 + np.cumsum(rng.standard_normal(n)) + est
    return fue.TimeSeries(nivel.tolist(), freq=4, start=(2000, 1), name="SEASTOC")


def _modelo_S(ts, ruta):
    """ifadf[1]=1 + testigo MA_f libre: el modelo S que contrasta el MEG."""
    m = fue.Model(ts, d=1, boxlam=1.0, ifadf=[0, 1, 0],
                  ma_f=[fue.FixedFreqFactor(freq=1.0, coef=-0.5, free=True)],
                  mu=0.0, estimate_mu=False)
    _write_inp(ts, m, ruta)
    _, m_fit = _load_fitted(ruta)
    return m_fit


def test_the_ma_f_witness_survives_the_chain(tmp_path):
    ts = _serie()
    m_S = _modelo_S(ts, str(tmp_path / "S.inp"))
    assert len(m_S.ma_f or []) == 1, "el modelo de partida no llegó a tener testigo"

    m_new = _build_arma_on_model(m_S, p=0, q=1)
    assert len(m_new.ma_f or []) == 1, (
        "el testigo MA_f se perdió al encadenar: eso deja el ifadf sin su "
        "testigo, que es la forma sobrediferenciada")
    assert m_new.ma_f[0].freq == pytest.approx(1.0)
    # y la raíz unitaria que lo acompaña sigue ahí
    assert list(m_new.ifadf) == [0, 1, 0]


def test_the_witness_is_not_governed_by_Q(tmp_path):
    """Q nombra el MA de RETARDO estacional, no el de frecuencia fija. Pedir
    Q=0 no puede borrar el testigo: son bloques distintos del .inp."""
    ts = _serie()
    m_S = _modelo_S(ts, str(tmp_path / "S.inp"))
    for Q in (0, 1):
        m_new = _build_arma_on_model(m_S, p=0, q=1, Q=Q)
        assert len(m_new.ma_f or []) == 1, f"el testigo desapareció con Q={Q}"


def test_dropping_the_witness_over_differences_the_seasonal(tmp_path):
    """Por qué importa: sin testigo, el mismo ifadf sobrediferencia."""
    ts = _serie()
    m_S = _modelo_S(ts, str(tmp_path / "S.inp"))

    def _fit(m, nombre):
        ruta = str(tmp_path / nombre)
        _write_inp(ts, m, ruta)
        _, mf = _load_fitted(ruta)
        r = np.asarray(mf.residuals.data, float)
        return r.std(ddof=1), mf.loglik

    con = _build_arma_on_model(m_S, p=0, q=1)
    sd_con, ll_con = _fit(con, "con.inp")

    # la forma desnuda, construida a mano: mismo ifadf, sin testigo
    sin = fue.Model(ts, d=1, boxlam=1.0, ifadf=[0, 1, 0],
                    ma=[[0.0]], ma_free=[[True]], mu=0.0, estimate_mu=False)
    sd_sin, ll_sin = _fit(sin, "sin.inp")

    assert ll_con > ll_sin, (
        "quitar el testigo debería empeorar el ajuste — si no, este testigo "
        "sintético no discrimina y el test no vale")
    assert sd_sin > sd_con


def test_a_fixed_frequency_AR_is_inherited_too(tmp_path):
    """El mismo bloque existe para el AR: `ar_f`. Se hereda igual."""
    ts = _serie()
    m = fue.Model(ts, d=1, boxlam=1.0,
                  ar_f=[fue.FixedFreqFactor(freq=1.0, coef=-0.4, free=True)],
                  mu=0.0, estimate_mu=False)
    ruta = str(tmp_path / "arf.inp")
    _write_inp(ts, m, ruta)
    _, m_fit = _load_fitted(ruta)
    assert len(m_fit.ar_f or []) == 1

    m_new = _build_arma_on_model(m_fit, p=0, q=1)
    assert len(m_new.ar_f or []) == 1, "el AR de frecuencia fija se perdió"


def test_a_model_without_fixed_frequency_operators_is_unaffected(tmp_path):
    """La otra cara: no inventar bloques donde no los había."""
    ts = _serie()
    m = fue.Model(ts, d=1, boxlam=1.0, ma=[[0.3]], ma_free=[[True]],
                  mu=0.0, estimate_mu=False)
    ruta = str(tmp_path / "plain.inp")
    _write_inp(ts, m, ruta)
    _, m_fit = _load_fitted(ruta)

    m_new = _build_arma_on_model(m_fit, p=1, q=0)
    assert not (m_new.ar_f or [])
    assert not (m_new.ma_f or [])
