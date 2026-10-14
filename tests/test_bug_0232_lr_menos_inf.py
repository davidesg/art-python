"""BUG-0232 — LR = −inf publicado como testigo, y «adecuado» bajo un par que no cierra.

Salamanca y Chamartín, AR(4) con μ en d = 1: la subdiferenciación daba
θ̂ ≈ 0,66, LR = −inf y «testigo NO invertible (θ→+1) → con d−1 bastaba».
Con θ = 1 el AR(4) libre ponía una raíz EXACTAMENTE en 1, se cancelaba con el
MA y la verosimilitud restringida se iba a +∞ (la misma causa que BUG-0224).
Y el cierre decía «El modelo es adecuado» debajo de «por ABAJO no cierra».
"""
import os
import math
import warnings

import pytest

pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.describe as describe
from art.describe import describe_formal_tests
from art.formal_tests import DCDResult, ShinFullerResult, dcd_underdiff_regular

PRE = os.path.join(os.path.dirname(__file__), "..", "bugs", "BUG-0232-repro",
                   "Chamartin_m02.pre")


@pytest.fixture(scope="module")
def chamartin():
    from art.mcp_server import _load_fitted
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return _load_fitted(PRE)[1]


def test_chamartin_el_lr_es_finito(chamartin):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = dcd_underdiff_regular(chamartin)
    assert math.isfinite(r.lr) and math.isfinite(r.loglik_constrained)
    assert r.calculable
    assert r.ar_acotado                   # la raíz que se iba a 1, acotada en ρₘ
    assert r.lr >= r._crit["5%"]          # θ̂ ≈ 0,67: la ∇ es genuina


def test_chamartin_el_informe_no_publica_menos_inf(chamartin):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = describe_formal_tests(chamartin, run_meg=False,
                                  subdiferenciacion=True).summary
    assert "LR=-inf" not in s
    assert "bastaba" not in s


def _ud(theta, lr):
    return DCDResult(factor_index=0, freq=None, coef_free=theta, coef_null=1.0,
                     loglik_free=0.0, loglik_constrained=-lr / 2, lr=lr, n=188)


def test_un_lr_no_finito_no_es_un_veredicto():
    r = _ud(0.66, -math.inf)
    assert not r.calculable
    assert not r.rejects_5pct and not r.rejects_10pct
    assert "NO CALCULABLE" in r.summary()


def _sf_ok(n=188):
    return ShinFullerResult(
        phi_null=1 - 4 / n, phi_free=[0.5], loglik_free=0.0,
        loglik_constrained=-5.0, phi_1u=5.0, crit_10pct=1.07, crit_5pct=1.76,
        crit_1pct=3.43, df=1, pvalue=0.01, n=n, s=12, phi_dominant=0.5)


def _od_ok():
    return DCDResult(factor_index=0, freq=None, coef_free=0.999, coef_null=1.0,
                     loglik_free=0.0, loglik_constrained=0.0, lr=0.0, n=188)


def _informe(monkeypatch, m, ud):
    monkeypatch.setattr(describe, "shin_fuller", lambda _m: _sf_ok())
    monkeypatch.setattr(describe, "dcd_overdiff_regular", lambda _m: _od_ok())
    monkeypatch.setattr(describe, "dcd_underdiff_regular", lambda _m: ud)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return describe_formal_tests(m, run_meg=False, subdiferenciacion=True)


def test_menos_inf_se_dice_no_calculable_y_no_cierra(chamartin, monkeypatch):
    d = _informe(monkeypatch, chamartin, _ud(0.6587, -math.inf))
    assert "no calculable" in d.summary
    assert "con d−1 bastaba" not in d.summary
    assert "El modelo es adecuado" not in d.recommendation
    assert d.data["underdiff_regular"]["estado"] == "no_calculable"


def test_por_abajo_no_cierra_y_el_cierre_no_dice_adecuado(chamartin, monkeypatch):
    d = _informe(monkeypatch, chamartin, _ud(0.99, 0.1))
    assert "Pero por ABAJO no cierra" in d.summary
    assert "El modelo es adecuado" not in d.recommendation
    assert "no cierran" in d.recommendation
