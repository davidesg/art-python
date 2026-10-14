"""BUG-0244 — encadenar con `p` como lista de factores daba un TypeError.

El modo nuevo de `confirm_and_estimate` acepta `p=[1, 2]` —(1−φB)(1−φ₁B−φ₂B²)—
y el incremental (`base_pre_path`) lo pasaba tal cual a `_arma_starts`, que
sólo acepta enteros: «orden p debe ser un entero, recibido list». El
sobreajuste factorizado sobre un modelo con intervenciones no se podía hacer
sin reconstruirlo a mano.
"""
import os

import numpy as np

os.environ.setdefault("ART_NO_VIEWER", "1")

from art.pipeline import _build_arma_on_model, _make_model

HERE = os.path.dirname(os.path.abspath(__file__))
REPRO = os.path.join(HERE, "..", "bugs", "BUG-0244-repro")


def _ts(n=120, seed=7):
    import fue
    rng = np.random.default_rng(seed)
    e = rng.normal(0, 1.0, n)
    w = np.zeros(n)
    for t in range(2, n):
        w[t] = 0.6 * w[t - 1] - 0.3 * w[t - 2] + e[t]
    y = np.cumsum(w) + 100.0
    y[60:] += 8.0
    return fue.TimeSeries(list(y), freq=12, start=(2000, 1), name="X")


def _base():
    m = _make_model(_ts(), lam=1.0, d=1, D=0, p=2, q=0, n_harmonics=0,
                    extra_itvs=[(60, "step")], estimate_mu=False)
    m.fit()
    return m


def test_p_lista_construye_los_factores_y_conserva_la_intervencion():
    m2 = _build_arma_on_model(_base(), p=[1, 2], q=0)
    assert [len(f) for f in m2.ar] == [1, 2]
    assert all(all(f) for f in m2.ar_free)
    assert [i.type for i in m2.interventions] == ["step"]


def test_p_lista_usa_las_semillas_del_llamador():
    m2 = _build_arma_on_model(_base(), p=[1, 2], q=0,
                              ar_seeds=[[0.5], [0.3, -0.2]])
    assert [[float(c) for c in f] for f in m2.ar] == [[0.5], [0.3, -0.2]]


def test_un_entero_sigue_siendo_un_solo_operador():
    m2 = _build_arma_on_model(_base(), p=3, q=0)
    assert [len(f) for f in m2.ar] == [3]


def test_por_el_servidor_con_el_caso_del_informe(tmp_path):
    from art import mcp_server as M
    fn = getattr(M.confirm_and_estimate, "fn", M.confirm_and_estimate)
    out = fn(os.path.join(REPRO, "IPC_US_m06.inp"), str(tmp_path / "x.inp"),
             base_pre_path=os.path.join(REPRO, "IPC_US_m06.pre"),
             p=[1, 2], q=0, estimate_mu=True)
    txt = "\n".join(getattr(c, "text", "") or "" for c in out)
    assert "TypeError" not in txt
    _, m = M._load_ts_model(str(tmp_path / "x.pre"))
    assert [len(f) for f in m.ar] == [1, 2]
    assert sorted(i.type for i in m.interventions) == ["impulse", "step"]
