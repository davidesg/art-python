"""BUG-0214 — el Jarque-Bera de la diagnosis no es el del `.out`.

IPC_US AR(2): diagnosis 367,742, `.out` 359,190. Mismos residuos (215) y mismos
momentos: el motor reproduce el programa en C, que calcula n/6 en enteros. La
diagnosis conserva el estadístico exacto —el que da el p-valor— y cita el del
`.out` con la razón cuando difieren.
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


def test_la_diagnosis_cita_el_jb_del_out_y_por_que(ajuste):
    t, jb_out, _ = ajuste
    linea = re.search(r"- Normalidad \(JB\):[^\n]*", t).group(0)
    assert f"el `.out` da {jb_out:.3f}" in linea, linea
    assert "⌊215/6⌋" in linea


def test_es_el_mismo_estadistico_salvo_el_factor(ajuste):
    _, jb_out, pre = ajuste
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        dg = diagnose(mirar(pre)[1])
    n = len(dg.residuals)
    assert n == 215
    assert abs(dg.jb_out - jb_out) < 1e-3
    assert abs(dg.jb_stat * (n // 6) / (n / 6) - jb_out) < 1e-3
