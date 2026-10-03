"""BUG-0202 — «TODOS los errores típicos de arriba NO son válidos» sin parámetros.

El modelo base de WTI —ARIMA(0,1,0), sin μ ni deterministas— no tiene ningún
parámetro. Con `niter=None` y `cov_matrix=[]` (no `None`),
`covariance_is_degenerate` daba verdadero y el aviso salía sobre una tabla
vacía: en el primer modelo de cualquier análisis.
"""
import os
import warnings
from types import SimpleNamespace

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.diagnosis import covariance_is_degenerate
from art.pipeline import _write_inp


def test_sin_parametros_la_covarianza_no_es_degenerada():
    r = SimpleNamespace(npar=0, params=[], niter=None, cov_matrix=[])
    assert covariance_is_degenerate(r) is False


def test_con_parametros_la_semilla_se_sigue_marcando():
    """La puerta de BUG-0027 sigue abierta: niter=0 con covarianza presente."""
    r = SimpleNamespace(npar=1, params=[0.1], niter=0,
                        cov_matrix=np.eye(1))
    assert covariance_is_degenerate(r) is True


def test_el_modelo_base_de_WTI_sale_sin_aviso(tmp_path):
    rng = np.random.default_rng(1)
    y = np.exp(4 + np.cumsum(rng.standard_normal(200) * 0.05))
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="W")
    f = str(tmp_path / "w.inp")
    _write_inp(ts, fue.Model(ts, d=1), f)
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, str(tmp_path / "w0.inp"), lam=0, d=1, D=0, p=0, q=0,
                 n_harmonics=0, seasonal=False, estimate_mu=False)
    txt = "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                    for x in out)
    assert "NO son válidos" not in txt
