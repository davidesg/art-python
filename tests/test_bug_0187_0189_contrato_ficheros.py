"""BUG-0187/0188/0189 — lo que `_write_inp` escribe y lo que art lee del modelo.

- 0187: la columna de cada determinista NO ESTÁNDAR va detrás de la serie.
- 0188: los datos de la serie releen idénticos (no `.6f`).
- 0189: la media se lee de `mu0`, que es el atributo de `fue.Model`.
"""
import numpy as np
import pytest

fue = pytest.importorskip("fue")

from art.pipeline import _RESCALE_FACTOR, _write_inp


def _modelo(mu=0.0, estimate_mu=False, con_regresor=True):
    rng = np.random.default_rng(11)
    # Datos con más de seis decimales: los que `.6f` estropeaba.
    y = 100.0 + np.cumsum(rng.standard_normal(60)) * 0.123456789
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2000, 1), name="C")
    itvs = [fue.Intervention("step", at=30, omega=[0.0], omega_free=[True])]
    if con_regresor:
        x = rng.standard_normal(60) / 3.0
        itvs.append(fue.Intervention("custom", at=0, data=x,
                                     omega=[0.0], omega_free=[True]))
    m = fue.Model(ts, ar=[[0.5]], ar_free=[[True]], interventions=itvs,
                  mu=mu, estimate_mu=estimate_mu, refactor=_RESCALE_FACTOR)
    return ts, m


def test_0187_la_columna_del_regresor_externo_se_escribe(tmp_path):
    ts, m = _modelo()
    f = str(tmp_path / "c.inp")
    _write_inp(ts, m, f)
    _, m2 = fue.load(f)
    assert np.array_equal(m2.interventions[1].data, m.interventions[1].data)


def test_0187_un_determinista_no_estandar_sin_datos_no_se_escribe(tmp_path):
    ts, m = _modelo()
    m.interventions[1].data = None
    with pytest.raises(ValueError, match="BUG-0187"):
        _write_inp(ts, m, str(tmp_path / "c.inp"))


def test_0188_los_datos_releen_identicos(tmp_path):
    ts, m = _modelo(con_regresor=False)
    f = str(tmp_path / "c.inp")
    _write_inp(ts, m, f)
    ts2, _ = fue.load(f)
    assert np.array_equal(ts2.data, ts.data)


def test_0188_el_escritor_hermano_tambien(tmp_path):
    from art.pipeline import _write_bare_inp
    ts, _ = _modelo(con_regresor=False)
    f = str(tmp_path / "b.inp")
    _write_bare_inp(ts, f)
    ts2, _ = fue.load(f)
    assert np.array_equal(ts2.data, ts.data)


def test_0189_el_guion_registra_la_media_de_verdad():
    from art.guion import _extract_spec
    _, m = _modelo(mu=-88.717979, estimate_mu=False, con_regresor=False)
    assert _extract_spec(m, m.boxlam)["mu"] == m.mu0 == -88.717979


def test_0189_los_clones_heredan_la_semilla_de_la_media():
    from art.escalera import _clona_con
    _, m = _modelo(mu=3.25, estimate_mu=True, con_regresor=False)
    assert _clona_con(m, list(m.interventions)).mu0 == 3.25


def test_0189_una_media_fija_no_nula_sobrevive_al_inp(tmp_path):
    ts, m = _modelo(mu=-7.5, estimate_mu=False, con_regresor=False)
    f = str(tmp_path / "c.inp")
    _write_inp(ts, m, f)
    _, m2 = fue.load(f)
    assert m2.mu0 == -7.5 and not m2.estimate_mu
