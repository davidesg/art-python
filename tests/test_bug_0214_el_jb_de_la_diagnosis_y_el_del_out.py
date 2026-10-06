"""BUG-0214 — el Jarque-Bera de la diagnosis no es el del `.out`.

IPC_US AR(2): diagnosis 367,742, `.out` 359,190. Mismos residuos (215) y mismos
momentos: fue copiaba del C antiguo n/6 en enteros. Ahora fue usa n/6 exacto
(fue/BUG-0026), como el C actual, scipy, pyfug y art: un solo JB en todas
partes, también con n = 215, que 6 no divide.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.diagnosis import diagnose
from art.pipeline import _RESCALE_FACTOR, _write_inp, mirar


def _T(r):
    return r if isinstance(r, str) else "\n".join(
        t for c in r if isinstance(t := getattr(c, "text", None), str))


@pytest.fixture(scope="module")
def ajuste(tmp_path_factory):
    d = tmp_path_factory.mktemp("b214")
    rng = np.random.default_rng(214)
    e = 0.003 * rng.standard_t(4, 216)             # colas gruesas: JB grande
    ts = fue.TimeSeries(np.exp(4.5 + np.cumsum(0.002 + e)).tolist(), freq=12,
                        start=(2002, 1), name="US")
    f = str(d / "US.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, refactor=_RESCALE_FACTOR), f)
    out = str(d / "us2.inp")
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _T(fn(f, out, lam=0, d=1, D=0, p=2, q=0, n_harmonics=0,
                  seasonal=False, estimate_mu=True, domain="price_index",
                  modo="autonomo"))
    jb_out = float(re.search(r"Jarque-Bera:\s*([0-9.]+)",
                             open(out[:-4] + ".out").read()).group(1))
    return t, jb_out, out[:-4] + ".pre"


def test_la_diagnosis_da_el_jb_del_out(ajuste):
    t, jb_out, _ = ajuste
    linea = re.search(r"- Normalidad \(JB\):[^\n]*", t).group(0)
    assert f"JB={jb_out:.3f}" in linea, linea
    assert "el `.out` da" not in linea


def test_un_solo_estadistico_con_n_que_6_no_divide(ajuste):
    _, jb_out, pre = ajuste
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dg = diagnose(mirar(pre)[1])
    assert len(dg.residuals) == 215
    assert abs(dg.jb_stat - jb_out) < 1e-3
