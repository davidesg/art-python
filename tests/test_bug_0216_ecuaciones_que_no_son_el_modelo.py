"""BUG-0216 — ecuaciones que no son el modelo estimado.

Un (0,1,0) se escribe en el `.inp` con un AR de relleno `[0.0]` FIJO. La
ecuación de `confirm_and_estimate` lo imprimía como «(1 − 0·B)», y la forma del
guion lo contaba como p=1: «∇[ln y_t] = μ + [1-φ(B)]⁻¹·a_t». Además
`record_version` daba sólo esa forma, sin un coeficiente: ahora da la ecuación
estimada (sin errores típicos, porque mira un `.pre`) y la forma corregida.
"""
import json
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


def _fn(tool):
    return getattr(tool, "fn", tool)


@pytest.fixture(scope="module")
def paseo(tmp_path_factory):
    d = tmp_path_factory.mktemp("b216")
    rng = np.random.default_rng(216)
    z = np.cumsum(0.002 + 0.004 * rng.standard_normal(216))
    ts = fue.TimeSeries(np.exp(4.5 + z).tolist(), freq=12, start=(2002, 1), name="W")
    f = str(d / "W.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    out = str(d / "w0.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(_fn(srv.confirm_and_estimate)(
            f, out, lam=0, d=1, D=0, p=0, q=0, n_harmonics=0, seasonal=False,
            estimate_mu=True, domain="price_index", modo="autonomo"))
    return d, t, out[:-4] + ".pre"


def test_confirm_sin_factor_ar_vacio(paseo):
    _, t, _ = paseo
    eq = re.search(r"\(2\)[^\n]*", t).group(0)
    assert "0·B" not in eq, eq
    assert re.search(r"\(∇Nₜ − \d+\.\d+\) = aₜ", eq), eq


def test_record_version_da_la_ecuacion_estimada(paseo):
    d, _, pre = paseo
    g = str(d / "g.json")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(_fn(srv.record_version)(pre, g))
    sec2 = t.split("## 2")[1].split("## 3")[0]
    assert "MODELO ESTIMADO" in sec2 and re.search(r"∇Nₜ − \d+\.\d+", sec2)
    assert "φ(B)" not in sec2, "la forma cuenta un AR que el modelo no tiene"
    # Mira un `.pre`: los coeficientes sí, los errores típicos no (BUG-0090).
    assert not re.search(r"^\s+\(\d+\.\d+\)\s*$", sec2, re.M)
    eq_guion = json.load(open(g))["entries"][-1]["equation"]
    assert "φ(B)" not in eq_guion and "μ" in eq_guion, eq_guion


def test_un_ar_real_sigue_en_la_forma(paseo):
    d, _, _ = paseo
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _fn(srv.confirm_and_estimate)(
            str(d / "W.inp"), str(d / "w1.inp"), lam=0, d=1, D=0, p=1, q=0,
            n_harmonics=0, seasonal=False, estimate_mu=True,
            domain="price_index", modo="autonomo")
    from art.pipeline import mirar
    _, m = mirar(str(d / "w1.pre"))
    assert "φ(B)" in srv._forma_estructural(m, 0.0)
