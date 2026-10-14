"""BUG-0223 — con d=0 el paso 3 no contrastaba la estacionalidad y aun así decidía.

`guided_identification(lam, d=0)` saltaba el test HAC (`if d > 0:`) y la rama
«sin estacionalidad» imprimía «Decisión A: D=0, sin armónicos» sobre una
bandera que nadie había calculado. BXE (X/M de Ecuador, d=0 por construcción)
tiene F-HAC = 9.58. Ahora el contraste corre también con d=0, sobre ∇y como
siempre, y la decisión sale de él.
"""
import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _write_inp


def _ts(seasonal: bool, seed: int = 223):
    """Estacionaria en niveles (AR(1) 0.5 alrededor de una media), trimestral."""
    rng = np.random.default_rng(seed)
    n = 80
    e = rng.standard_normal(n + 100) * 0.03
    x = np.zeros(n + 100)
    for t in range(1, n + 100):
        x[t] = 0.5 * x[t - 1] + e[t]
    x = x[100:]
    if seasonal:
        x = x + 0.08 * np.cos(2 * np.pi * np.arange(n) / 4)
    return fue.TimeSeries(np.exp(x).tolist(), freq=4, start=(2003, 1), name="R")


def _paso3(tmp_path, seasonal, objetivo="univariante"):
    ts = _ts(seasonal)
    f = str(tmp_path / "R.inp")
    _write_inp(ts, fue.Model(ts, d=0, boxlam=0.0), f)
    g = str(tmp_path / "g.json")
    fn = getattr(srv.guided_identification, "fn", srv.guided_identification)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, lam=0, d=0, objetivo=objetivo, guion_path=g)
    text = "\n".join(x if isinstance(x, str) else getattr(x, "text", "") or ""
                     for x in out)
    return text, g


def _propuesta_estacional(g):
    ult = srv._ultimo_nodo(srv._abre_guion(g), "estacionalidad")
    return (ult.node or {}).get("propuesta_valor")


def test_d0_con_estacionalidad_la_contrasta_y_ofrece_b1_b2(tmp_path):
    t, g = _paso3(tmp_path, seasonal=True)
    assert "Test HAC de estacionalidad" in t
    assert "Estacionalidad detectada: **Sí**" in t
    assert "Route B1" in t and "Route B2" in t
    assert "no hay estacionalidad que enrutar" not in t
    assert _propuesta_estacional(g) == "B1"


def test_d0_sin_estacionalidad_decide_a_con_el_contraste_delante(tmp_path):
    t, g = _paso3(tmp_path, seasonal=False)
    assert "Test HAC de estacionalidad" in t
    assert "Estacionalidad detectada: **No**" in t
    assert "Decisión A" in t
    assert _propuesta_estacional(g) == "A"


def test_d0_multivariante_imprime_la_nota_b1_requisito(tmp_path):
    t, _ = _paso3(tmp_path, seasonal=True, objetivo="multivariante")
    assert "Objetivo declarado: MULTIVARIANTE" in t
