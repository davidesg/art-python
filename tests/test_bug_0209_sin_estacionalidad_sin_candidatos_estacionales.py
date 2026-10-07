"""BUG-0209 — tras la Decisión A (D=0, sin estacionalidad), el paso 4 la proponía.

Con una serie desestacionalizada (IPC_US, F-HAC p=0,78) el nodo 4 de
`guided_identification` listaba (0,1,1)(0,0,1)₁₂, (0,1,1)(1,0,0)₁₂… y su
«próximo paso» sugería `n_harmonics=5`. El nodo 4 no sabía qué había decidido el
3. Ahora repite el mismo contraste: sin estacionalidad, ni candidatos con parte
estacional ni armónicos; con ella, la ruta B1 sigue igual.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.describe import describe_identification
from art.pipeline import _write_inp
from art.seasonal_detection import detect_seasonality


def _ts(seasonal: bool, seed: int):
    rng = np.random.default_rng(seed)
    n = 216
    e = rng.standard_normal(n + 1) * 0.004
    w = 0.002 + e[1:] + 0.5 * e[:-1]               # ∇ln y: MA(1) con deriva
    if seasonal:
        w = w + 0.01 * np.cos(2 * np.pi * np.arange(n) / 12)
    return fue.TimeSeries(np.exp(4.6 + np.cumsum(w)).tolist(), freq=12,
                          start=(2002, 1), name="S")


@pytest.fixture(scope="module")
def sin_est(tmp_path_factory):
    ts = _ts(False, 209)
    assert not detect_seasonality(ts).seasonal_detected, "precondición"
    f = str(tmp_path_factory.mktemp("b209") / "S.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0), f)
    return ts, f


@pytest.fixture(scope="module")
def con_est(tmp_path_factory):
    ts = _ts(True, 209)
    assert detect_seasonality(ts).seasonal_detected, "precondición"
    f = str(tmp_path_factory.mktemp("b209s") / "E.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0), f)
    return ts, f


def _nodo4(f):
    fn = getattr(srv.guided_identification, "fn", srv.guided_identification)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, lam=0, d=1, D=0)
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "") or ""
                     for x in out)


def _estacionales(txt):
    return [m for m in re.findall(r"ARIMA\(\d,1,\d\)\((\d),0,(\d)\)_12", txt)
            if m != ("0", "0")]


def test_sin_estacionalidad_ningun_candidato_estacional(sin_est):
    _, f = sin_est
    t = _nodo4(f)
    assert "Candidatos ARMA" in t
    assert not _estacionales(t), _estacionales(t)


def test_sin_estacionalidad_el_proximo_paso_no_pide_armonicos(sin_est):
    _, f = sin_est
    t = _nodo4(f)
    assert "n_harmonics=5" not in t
    assert "n_harmonics=0, seasonal=False" in t
    assert "Si el nodo 3 detectó estacionalidad" not in t, \
        "vuelve a ofrecer las dos ramas"


def test_describe_identification_respeta_la_decision_A(sin_est):
    ts, _ = sin_est
    d = describe_identification(ts, d=1, D=0, lam=0.0, estacional=False)
    assert d.data["estacional"] is False
    assert not _estacionales(d.summary)
    assert "Decisión A" in d.recommendation
    assert "estacionalidad HÍBRIDA" not in d.summary


def test_la_busqueda_se_acota_a_la_parte_regular(sin_est, monkeypatch):
    """Lo que de verdad cierra la puerta: sin P/Q que buscar y sin restar
    armónicos que el modelo no va a llevar (en IPC_US el primero por AICc era
    el (0,1,1)(0,0,1)₁₂; una serie sintética no lo garantiza)."""
    import art.describe as D_
    visto = {}
    real = D_.suggest_orders

    def espia(*a, **k):
        visto.update(k)
        return real(*a, **k)

    monkeypatch.setattr(D_, "suggest_orders", espia)
    ts, _ = sin_est
    describe_identification(ts, d=1, D=0, lam=0.0, estacional=False)
    assert (visto.get("P_max"), visto.get("Q_max"), visto.get("n_harmonics")) \
        == (0, 0, 0)


def test_con_estacionalidad_la_ruta_B1_sigue_igual(con_est):
    _, f = con_est
    t = _nodo4(f)
    assert "n_harmonics=5" in t
    assert "ruta B1" in t


def test_sin_decision_conocida_el_texto_no_cambia(sin_est):
    ts, _ = sin_est
    d = describe_identification(ts, d=1, D=0, lam=0.0)
    assert d.data["estacional"] is None
    assert "Si el nodo 3 detectó estacionalidad (ruta B1)" in d.recommendation



def _listado(f):
    fn = getattr(srv.identification_analysis, "fn", srv.identification_analysis)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, d=1, D=0, lam=0.0)
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "") or ""
                     for x in out)


def test_identification_analysis_respeta_la_misma_decision(sin_est):
    """La herramienta suelta usa la decisión del nodo 3, como el paso 4."""
    t = _listado(sin_est[1])
    assert _estacionales(t) == [], _estacionales(t)
    assert "n_harmonics=5" not in t


def test_identification_analysis_con_estacionalidad_sigue_proponiendola(con_est):
    assert "n_harmonics=5" in _listado(con_est[1])
