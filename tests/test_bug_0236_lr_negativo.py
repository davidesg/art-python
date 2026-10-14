"""BUG-0236 — DCD de sobrediferenciación: LR negativo y testigo negativo como «d confirmado ✓».

Batería de research/bateria_contrastes_d.py (N = 200, SEED = 2026): sobre el
AR(2) real (0,5; 0,3) con d = 1, θ̂ = 0,9667 y LR = −0,053 → «testigo NO
invertible (θ→+1) … d confirmado ✓». Un LR negativo dice que el libre no llegó
a su máximo —el restringido es un caso particular suyo—, y un testigo en
θ̂ < 0 mide la frecuencia π. El veredicto salía sólo de `lr < crit`.
"""
import os
import warnings

import numpy as np
import pytest

pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.describe as describe
from art.describe import describe_formal_tests
from art.formal_tests import (DCDResult, ShinFullerResult, _frontera_theta_uno,
                              dcd_overdiff_regular)

N, SEED = 200, 2026
_ESTR = [[], [0.6], [0.95], [0.5, 0.3], [1.0, -0.5], [], [0.6]]
_MA = [[], [], [], [], [], [0.5], [0.3]]


def _serie_de_la_bateria(d_obj, k_obj):
    """La misma serie que la batería: se recorre el generador en su orden."""
    from scipy.signal import lfilter
    rng = np.random.default_rng(SEED)
    for d in (0, 1, 2):
        for k, (phi, theta) in enumerate(zip(_ESTR, _MA)):
            a = rng.normal(size=N + 300)
            x = lfilter(np.r_[1, -np.array(theta, float)],
                        np.r_[1, -np.array(phi, float)], a)[300:]
            for _ in range(d):
                x = np.cumsum(x)
            if (d, k) == (d_obj, k_obj):
                return x - x.min() + 100.0


@pytest.fixture(scope="module")
def ar2_d1(tmp_path_factory):
    import art.mcp_server as s
    from art.mcp_server import _load_fitted
    w = tmp_path_factory.mktemp("bat")
    x = _serie_de_la_bateria(1, 3)              # d=1, AR(2) reales .5,.3
    inp, out = str(w / "S.inp"), str(w / "m.inp")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s.create_inp([float(v) for v in x], inp, name="S", freq=12,
                     start_year=2000, start_period=1)
        s.confirm_and_estimate(inp, out, lam=1.0, d=1, D=0, p=2, q=0,
                               n_harmonics=0, seasonal=False, estimate_mu=False,
                               domain="generic", modo="autonomo")
        return _load_fitted(out.replace(".inp", ".pre"))[1]


def test_la_bateria_ya_no_da_un_lr_negativo(ar2_d1):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = dcd_overdiff_regular(ar2_d1)
    assert r.calculable
    assert r.lr >= 0.0, f"LR={r.lr}: el libre sigue por debajo del restringido"
    assert r.loglik_free >= r.loglik_constrained - 1e-6


def test_un_libre_que_no_llego_se_reintenta_desde_el_restringido(ar2_d1):
    """Se le pasa a la frontera un ℓ libre deliberadamente malo y un testigo
    negativo: tiene que reintentar el libre y quedarse con el mejor."""
    import copy
    mc = copy.deepcopy(ar2_d1)
    mc._result = None
    mc.ma = [[1.0]]
    mc.ma_free = [[False]]
    malo = float(ar2_d1._result.loglik) - 5.0
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = _frontera_theta_uno(mc, 0, malo, -0.2)
    assert r.calculable and r.lr >= 0.0
    assert r.loglik_free > malo


def test_un_lr_negativo_que_no_se_arregla_no_es_un_veredicto():
    r = DCDResult(factor_index=0, freq=None, coef_free=0.97, coef_null=1.0,
                  loglik_free=-10.0, loglik_constrained=-9.0, lr=-2.0, n=200)
    assert not r.calculable and not r.rejects_5pct


# ── los titulares ──────────────────────────────────────────────────────────

def _sf(n=200):
    return ShinFullerResult(
        phi_null=1 - 4 / n, phi_free=[0.5], loglik_free=0.0,
        loglik_constrained=-5.0, phi_1u=5.0, crit_10pct=1.07, crit_5pct=1.76,
        crit_1pct=3.43, df=1, pvalue=0.01, n=n, s=12, phi_dominant=0.5)


def _od(theta, lr):
    return DCDResult(factor_index=0, freq=None, coef_free=theta, coef_null=1.0,
                     loglik_free=lr / 2, loglik_constrained=0.0, lr=lr, n=200)


def _titular(monkeypatch, m, od):
    monkeypatch.setattr(describe, "shin_fuller", lambda _m: _sf())
    monkeypatch.setattr(describe, "dcd_overdiff_regular", lambda _m: od)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        d = describe_formal_tests(m, run_meg=False)
    return d, d.summary.split("**DCD sobre-diferenciación regular**")[1].split("\n")[1]


def test_testigo_negativo_no_es_theta_a_mas_uno(ar2_d1, monkeypatch):
    d, t = _titular(monkeypatch, ar2_d1, _od(-0.1893, 0.5))
    assert "θ→+1" not in t and "d confirmado" not in t
    assert "no mide f=0" in t


def test_testigo_lejos_de_la_frontera_no_es_theta_a_mas_uno(ar2_d1, monkeypatch):
    d, t = _titular(monkeypatch, ar2_d1, _od(0.80, 1.0))
    assert "θ→+1" not in t and "d confirmado ✓" not in t


def test_testigo_en_la_frontera_sigue_confirmando(ar2_d1, monkeypatch):
    d, t = _titular(monkeypatch, ar2_d1, _od(0.999, 0.0))
    assert "d confirmado ✓" in t


def test_lr_negativo_se_dice_no_calculable(ar2_d1, monkeypatch):
    d, t = _titular(monkeypatch, ar2_d1, _od(0.9667, -1.8))
    assert "no calculable" in t
    assert d.data["f0_pair"] is None              # no entra en el par
    assert "El modelo es adecuado" not in d.recommendation
