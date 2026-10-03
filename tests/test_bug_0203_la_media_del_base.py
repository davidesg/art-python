"""BUG-0203 — «t=+0.83 → Sí, estimate_mu=True».

Con μ en el modelo base, la línea de la media decidía por ESA μ y citaba el t
de la serie diferenciada: una regla (|t|>2) contradicha por su propio número.
Ahora cita el t de la μ del base, con su nombre, y el de la serie va aparte
como contexto.
"""
import os
import re
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """Deriva débil en la serie, pero una caída intervenida la hace visible:
    el t de la μ del base supera 2 y el de la serie diferenciada no."""
    d = tmp_path_factory.mktemp("b203")
    rng = np.random.default_rng(203)
    n = 220
    e = rng.standard_normal(n) * 0.04
    z = np.cumsum(e + 0.008)
    z[150:] -= 0.9
    ts = fue.TimeSeries(np.exp(4 + z).tolist(), freq=12, start=(2002, 1),
                        name="W")
    f = str(d / "W.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0, mu=0.8, estimate_mu=True,
                             refactor=_RESCALE_FACTOR,
                             interventions=[fue.Intervention(
                                 "impulse", at=150, omega=[0.0],
                                 omega_free=[True])]), f)
    _, fit = estimar(f)
    fit.write_pre(f[:-4] + ".pre")
    return f, f[:-4] + ".pre"


def _bloque(inp, pre):
    fn = getattr(srv.guided_identification, "fn", srv.guided_identification)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(inp, lam=0, d=1, D=0, pre_path=pre)
    txt = "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                    for x in out)
    i = txt.find("¿Incluir media")
    assert i >= 0
    return txt[i:i + 900]


def test_cita_el_t_de_la_mu_del_BASE(base):
    inp, pre = base
    _, m = srv._mirar(pre)
    mu, se, t = srv._mu_del_base(m)
    b = _bloque(inp, pre)
    linea = b.split("\n")[0]
    assert "Sí, `estimate_mu=True`" in linea
    assert f"t={t:+.2f}" in linea, "no cita el t de la μ del base"
    assert os.path.basename(pre) in linea


def test_el_t_de_la_serie_va_aparte_como_contexto(base):
    inp, pre = base
    b = _bloque(inp, pre)
    linea, resto = b.split("\n", 1)
    assert "Contexto" in resto and re.search(r"μ̄=", resto)
    assert "μ̄=" not in linea, "las dos medidas vuelven a ir en la misma línea"


def test_sin_mu_en_el_base_la_linea_no_cambia(base):
    inp, _ = base
    fn = getattr(srv.guided_identification, "fn", srv.guided_identification)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(inp, lam=0, d=1, D=0)
    txt = "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                    for x in out)
    i = txt.find("¿Incluir media")
    assert re.search(r"Deriva de .*t=[-+]\d+\.\d+ → \*\*(Sí|No)", txt[i:i + 400])


def test_mu_del_base_esta_en_la_escala_de_la_serie(base):
    _, pre = base
    _, m = srv._mirar(pre)
    mu, se, t = srv._mu_del_base(m)
    assert 0.0 < mu < 0.05, "μ̂ no está en la escala de ∇ln y"
    assert t == pytest.approx(mu / se)
