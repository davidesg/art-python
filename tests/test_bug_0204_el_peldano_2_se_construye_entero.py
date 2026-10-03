"""BUG-0204 — con form="auto" y el peldaño 2 elegido se construía UN ω.

`n_omega=0` («no pedido») se normalizaba a 1 ANTES de leerse como pedido, así
que la cláusula de BUG-0079 —lo que el analista pide manda— se disparaba siempre
y devolvía a 1 los N escalones de la configuración que la escalera había
elegido. Sobre WTI (12/2014): elegido 3 escalones, AIC 1482.95; construido un
escalón de un ω, AIC 1497.90.
"""
import os
import re
import tempfile
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as A
from art.pipeline import _RESCALE_FACTOR, _write_inp, estimar

fn = lambda t: getattr(t, "fn", t)  # noqa: E731


def _txt(out):
    return "\n".join(x if isinstance(x, str) else getattr(x, "text", "")
                     for x in out)


@pytest.fixture(scope="module")
def tres_tramos(tmp_path_factory):
    """Una caída en tres trimestres seguidos: la escalera sube al peldaño 2."""
    d = str(tmp_path_factory.mktemp("b204"))
    rng = np.random.default_rng(5)
    n, T = 120, 60
    y = 100 + np.cumsum(rng.standard_normal(n) * 0.5)
    y[T:] += -3.0
    y[T + 1:] += -4.0
    y[T + 2:] += -3.0
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(1995, 1), name="X")
    f = os.path.join(d, "X.inp")
    _write_inp(ts, fue.Model(ts, d=1, mu=0.0, estimate_mu=False,
                             refactor=_RESCALE_FACTOR, ar=[[0.0]],
                             ar_free=[[True]]), f)
    _, m = estimar(f)
    m.write_pre(f[:-4] + ".pre")
    return d, f[:-4] + ".pre", f"Q{T % 4 + 1}/{1995 + T // 4}"


def _sugiere(pre, out, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        t = _txt(fn(A.suggest_intervention_form)(pre, out, form="auto", **kw))
    _, m = fue.load(out[:-4] + ".pre")
    m.fit()
    step = [i for i in m.interventions if i.type == "step"][-1]
    return t, m, step


def _peldano_2(t):
    l2 = next(l for l in t.splitlines() if l.startswith("- `2`"))
    n = int(re.search(r"(\d+) escalones", l2).group(1))
    aic = float(re.search(r"AIC ([\d.]+)", l2).group(1))
    return l2, n, aic


def test_el_peldano_2_elegido_se_construye_con_sus_N_omegas(tres_tramos):
    d, pre, fecha = tres_tramos
    t, m, step = _sugiere(pre, os.path.join(d, "auto.inp"), date=fecha)
    l2, n, aic = _peldano_2(t)
    assert "elegido" in l2, "el testigo dejó de valer: no se elige el peldaño 2"
    assert n > 1
    assert len(step.omega) == n, (
        f"la escalera eligió {n} escalones y se construyeron {len(step.omega)}")
    assert float(m.aic) == pytest.approx(aic, abs=0.01)


def test_un_n_omega_EXPLICITO_sigue_mandando(tres_tramos):
    """BUG-0079 no se toca: lo que el analista pide manda sobre la escalera."""
    d, pre, fecha = tres_tramos
    _, _, step = _sugiere(pre, os.path.join(d, "uno.inp"), date=fecha,
                          n_omega=1)
    assert len(step.omega) == 1


CSV = ("/home/david/Dropbox/Nivel de Precios y Energia/passthrough_multiart"
       "/data/levels_2002_2019.csv")


@pytest.mark.skipif(not os.path.exists(CSV), reason="CSV del pass-through")
def test_el_caso_del_informe_WTI_2014():
    d = tempfile.mkdtemp()
    f = lambda n: os.path.join(d, n)  # noqa: E731
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fn(A.load_data)(CSV, f("WTI.inp"), column="WTI", series_name="WTI",
                        freq=12, start_year=2002, start_period=2)
        fn(A.confirm_and_estimate)(f("WTI.inp"), f("m00.inp"), lam=0, d=1, D=0,
                                   p=0, q=0, n_harmonics=0, seasonal=False)
        fn(A.suggest_intervention_form)(f("m00.pre"), f("m01.inp"),
                                        date="10/2008", form="step", n_omega=3)
    t, m, step = _sugiere(f("m01.pre"), f("m02.inp"), date="12/2014")
    _, n, aic = _peldano_2(t)
    assert (len(step.omega), round(float(m.aic), 2)) == (n, aic) == (3, 1482.95)
