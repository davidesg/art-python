"""BUG-0213 — «la Q falla en el retardo 12» no pide estructura estacional.

La Q(12) acumula los retardos 1…12. La alternativa se elegía por el retardo de
la Q que rechaza —y en mensual son 12, 24, 36 y 39—, así que cualquier fallo
salía «añadir estructura ESTACIONAL». En ES_CORE m01 = (0,1,0)(0,1,1)₁₂ falla
r₁ (0,26) con r₁₂ = −0,07, y se proponía P=1. Ahora deciden las barras de la
FAS/FAP fuera de banda: bajas ⇒ regular; s, 2s ⇒ estacional.
"""
import os
import re
import warnings
from types import SimpleNamespace

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


@pytest.fixture(scope="module")
def m01(tmp_path_factory):
    """(1−B)(1−B¹²) ln y = (1+0.6B)(1−0.6B¹²) a: el (0,1,0)(0,1,1)₁₂ deja r₁
    fuerte y r₁₂ pequeño en los residuos."""
    d = tmp_path_factory.mktemp("b213")
    rng = np.random.default_rng(213)
    n, s = 216, 12
    a = 0.004 * rng.standard_normal(n + 30)
    w = a.copy()
    w[1:] += 0.6 * a[:-1]
    w[s:] -= 0.6 * a[:-s]
    w[s + 1:] -= 0.36 * a[:-s - 1]
    z = np.zeros_like(w)
    for t in range(len(w)):          # integra (1−B)(1−B¹²)
        z[t] = (w[t] + (z[t - 1] if t >= 1 else 0) + (z[t - s] if t >= s else 0)
                - (z[t - s - 1] if t >= s + 1 else 0))
    z = z[30:]
    ts = fue.TimeSeries(np.exp(4.5 + z).tolist(), freq=12, start=(2002, 1), name="CORE")
    f = str(d / "CORE.inp")
    _write_inp(ts, fue.Model(ts, d=1, D=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _T(fn(f, str(d / "m01.inp"), lam=0, d=1, D=1, p=0, q=0, P=0, Q=1,
                     estimate_mu=False, domain="price_index", modo="guiado"))


def test_el_caso_falla_en_r1_y_la_Q_rechaza_en_12(m01):
    assert "Ruido blanco (Q): ✗" in m01
    assert re.search(r"lag 12 \(", m01) or "Q(12" in m01


def test_propone_la_parte_regular_no_la_estacional(m01):
    sec4 = m01.split("## 4")[1]
    assert "Subir el orden regular" in sec4
    # el AR de relleno de un (0,1,0) no cuenta como orden (BUG-0216)
    assert "hoy AR(0) MA(0)" in sec4 and "p=1, q=0" in sec4
    assert "Añadir estructura ESTACIONAL" not in sec4, \
        "la Q(12) que rechaza por r₁ se lee otra vez como «falta lo estacional»"


def test_la_conclusion_no_dice_que_falla_el_retardo_12(m01):
    assert "acumula los retardos 1…k" in m01
    assert re.search(r"fuera de banda: 1\b", m01), "no nombra la barra que falla"


def _desc(fas, fap=()):
    return SimpleNamespace(data=dict(
        clean=False, white_noise=False, normal=True, centred=True,
        q_fails=["lag 12 (Q=30.1, p=0.0010)"], fas_fuera=list(fas),
        fap_fuera=list(fap), freq=12, nobs=200))


def test_barra_estacional_propone_lo_estacional():
    ts = SimpleNamespace(freq=12)
    m = SimpleNamespace(ar=None, ma=None)
    alts = " ".join(srv._alternativas_desde(_desc([12]), model=m, ts=ts))
    assert "ESTACIONAL" in alts and "Subir el orden regular" not in alts


def test_las_dos_regular_primero():
    ts = SimpleNamespace(freq=12)
    m = SimpleNamespace(ar=None, ma=None)
    alts = srv._alternativas_desde(_desc([1, 12]), model=m, ts=ts)
    i_reg = next(i for i, a in enumerate(alts) if "orden regular" in a)
    i_est = next(i for i, a in enumerate(alts) if "ESTACIONAL" in a)
    assert i_reg < i_est
