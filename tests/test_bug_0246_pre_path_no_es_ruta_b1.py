"""BUG-0246 — la llamada 4 con `pre_path` etiquetaba el nodo estacional como B1.

`guided_identification(..., D=0, pre_path=...)` escribía el nodo
`estacionalidad` con `_texto_D(D, b1=bool(pre_path))`: tener un `.pre` se leía
como ruta B1 (armónicos), cuando la Decisión A también calibra anómalos con un
base y vuelve con su `.pre`. En GAPGDPD salía «D=0 (B1, armónicos
deterministas)» en un modelo sin armónicos, y como nodo nuevo, duplicando el
«D=0 (sin estacionalidad)» ya confirmado. La ruta la dice el `.pre`.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv

_fn = lambda t: getattr(t, "fn", t)


def _inp(tmp_path):
    rng = np.random.default_rng(246)
    n = 80
    w = 0.005 + rng.standard_normal(n) * 0.01
    ts = fue.TimeSeries(np.exp(4.0 + np.cumsum(w)).tolist(), freq=4,
                        start=(2003, 1), name="G")
    f = str(tmp_path / "G.inp")
    _fn(srv.create_inp)(list(ts.data), f, name="G", freq=4, start_year=2003,
                        start_period=1)
    return f


def _nodos_estacionales(g):
    return [e.decision for e in srv._abre_guion(g).entries
            if e.is_node and (e.node or {}).get("nodo") == "estacionalidad"]


def _llamada4(inp, pre, g):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _fn(srv.guided_identification)(inp, lam=0, d=1, D=0, pre_path=pre,
                                       guion_path=g)


def _base(tmp_path, n_harmonics):
    inp = _inp(tmp_path)
    g = str(tmp_path / "g.json")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _fn(srv.confirm_and_estimate)(
            inp, str(tmp_path / "m00.inp"), lam=0, d=1, D=0, p=0, q=0,
            n_harmonics=n_harmonics, seasonal=bool(n_harmonics),
            estimate_mu=True)
    return inp, g, str(tmp_path / "m00.pre")


def test_decision_a_con_pre_path_no_escribe_b1_ni_duplica(tmp_path):
    inp, g, pre = _base(tmp_path, n_harmonics=0)
    srv._nodo_pendiente(g, "estacionalidad", "sin estacionalidad (D=0)", valor="A")
    srv._confirma_nodo(g, "estacionalidad", "D=0 (sin estacionalidad)", valor=0,
                       coincide_fn=srv._coincide_D)
    _llamada4(inp, pre, g)
    assert _nodos_estacionales(g) == ["estacionalidad = D=0 (sin estacionalidad)"]


def test_ruta_b1_con_pre_path_se_etiqueta_b1(tmp_path):
    inp, g, pre = _base(tmp_path, n_harmonics=1)
    srv._nodo_pendiente(g, "estacionalidad", "estacional (B1: D=0 + armónicos)",
                        valor="B1")
    _llamada4(inp, pre, g)
    assert _nodos_estacionales(g) == [
        "estacionalidad = D=0 (B1, armónicos deterministas)"]


def test_la_ruta_la_dice_el_pre(tmp_path):
    _, _, pre = _base(tmp_path, n_harmonics=0)
    assert srv._ruta_estacional_del_pre(pre) == "A"
