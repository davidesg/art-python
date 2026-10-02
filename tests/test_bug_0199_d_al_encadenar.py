"""BUG-0199 — con `base_pre_path`, la d pedida se ignoraba y la cabecera la anunciaba.

`confirm_and_estimate(base_pre_path=m02.pre, d=2, q=2)` estimaba con la d del
`.pre` (d=1) y la cabecera decía «ARIMA(0,2,2)»: el analista leía un modelo que
no era el estimado. Ahora:

- `lam`, `d`, `D` valen `None` por defecto: encadenando, `None` hereda del `.pre`;
- una d distinta se APLICA (el candidato d+1 conservando los deterministas), sin
  heredar la media del `.pre`, y la salida lo dice;
- una λ o una D distintas se RECHAZAN: son reformular, no encadenar;
- la cabecera, el escaneo y el guion leen d y D del MODELO estimado.
"""

import os
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


@pytest.fixture(scope="module")
def base_pre(tmp_path_factory):
    """Un modelo en log, d=1, con media y un escalón."""
    d = tmp_path_factory.mktemp("d199")
    rng = np.random.default_rng(199)
    n = 180
    y = np.exp(4.6 + np.cumsum(rng.standard_normal(n) * 0.01 + 0.003))
    y[120:] *= 1.05
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2005, 1), name="P")
    itvs = [fue.Intervention("step", at=120, omega=[0.0], omega_free=[True])]
    f = str(d / "P_m00.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, mu=0.003, estimate_mu=True,
                             refactor=_RESCALE_FACTOR, interventions=itvs), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")
    return str(d), f[:-4] + ".pre"


def _ce(src, out, **kw):
    fn = getattr(srv.confirm_and_estimate, "fn", srv.confirm_and_estimate)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(src, out, **kw)


def _texto(res):
    return "\n".join(r if isinstance(r, str) else getattr(r, "text", "")
                     for r in res)


def _modelo(inp):
    _, m = fue.load(inp[:-4] + ".pre")
    return m


def test_la_d_pedida_se_APLICA_y_la_cabecera_dice_la_del_modelo(base_pre):
    dd, pre = base_pre
    out = os.path.join(dd, "d2.inp")
    t = _texto(_ce(pre, out, base_pre_path=pre, d=2, p=0, q=2))
    m = _modelo(out)
    assert m.d == 2, "la d pedida sigue ignorándose"
    assert "ARIMA(0,2,2)" in t
    assert "d cambiada: 1 → 2" in t
    # Los deterministas se conservan.
    assert sum(1 for i in m.interventions if i.type == "step") == 1


def test_con_otra_d_la_media_del_pre_NO_se_hereda(base_pre):
    dd, pre = base_pre
    assert _modelo(pre[:-4] + ".inp").estimate_mu, "el testigo ya no trae μ"
    out = os.path.join(dd, "d2_sin_mu.inp")
    t = _texto(_ce(pre, out, base_pre_path=pre, d=2, p=0, q=1,
                   estimate_mu=True))
    m = _modelo(out)
    assert m.d == 2 and m.estimate_mu
    assert "se estima una nueva" in t
    out2 = os.path.join(dd, "d2_nada.inp")
    _ce(pre, out2, base_pre_path=pre, d=2, p=0, q=1)
    assert not _modelo(out2).estimate_mu


def test_sin_d_se_HEREDA_la_del_pre(base_pre):
    dd, pre = base_pre
    out = os.path.join(dd, "hereda.inp")
    t = _texto(_ce(pre, out, base_pre_path=pre, p=1, q=0))
    assert _modelo(out).d == 1
    assert "ARIMA(1,1,0)" in t
    assert "d cambiada" not in t


def test_la_misma_d_explicita_no_es_un_cambio(base_pre):
    dd, pre = base_pre
    out = os.path.join(dd, "misma.inp")
    t = _texto(_ce(pre, out, base_pre_path=pre, lam=0.0, d=1, D=0, p=1, q=0))
    assert _modelo(out).d == 1
    assert "d cambiada" not in t


@pytest.mark.parametrize("kw, palabra", [
    ({"lam": 1.0}, "λ=1"),
    ({"D": 1}, "D=1"),
])
def test_lambda_o_D_distintas_se_RECHAZAN(base_pre, kw, palabra):
    dd, pre = base_pre
    out = os.path.join(dd, f"rech_{list(kw)[0]}.inp")
    t = _texto(_ce(pre, out, base_pre_path=pre, p=1, q=0, **kw))
    assert palabra in t and "REFORMULAR" in t
    assert not os.path.exists(out), "se escribió un modelo que debía rechazarse"


def test_el_modelo_fresco_conserva_sus_defectos(base_pre):
    """Sin base_pre_path, None → λ=0, d=1, D=0, como antes."""
    dd, pre = base_pre
    out = os.path.join(dd, "fresco.inp")
    _ce(pre[:-4] + ".inp", out, p=1, q=0)
    m = _modelo(out)
    assert (m.boxlam, m.d, m.D) == (0.0, 1, 0)
