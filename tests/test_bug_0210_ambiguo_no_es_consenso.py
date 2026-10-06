"""BUG-0210 — nodo d: la tabla dice «ambiguo ⚠» y el resumen «con consenso».

En Retiro y Salamanca la fila de ∇ln salía «ambiguo» (ADF y KPSS rechazan) y el
resumen concluía «d = 1 (primera diferencia con consenso)»; en IPC_ES, «d = 0
(serie ya estacionaria en niveles)» con d=0 ambiguo y d=2 la única fila con
consenso. Y el soporte del nodo 3 decía «El ADF sobre ∇log(y) no rechaza» con
ADF p=0,031 o p=0,000. La d que se informa no cambia (el ADF manda, BUG-0002);
cambia que el texto lee el veredicto de su fila y su propio p.
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.describe as D_
import art._raiz_unitaria as RU
from art.identification import UnitRootResult


def _fila(d, adf_p, kpss_p):
    a, k = adf_p < 0.05, kpss_p < 0.05
    v = ("stationary" if a and not k else "unit_root" if k and not a
         else "ambiguous")
    return UnitRootResult(d=d, label=f"d{d}", n=200 - d, adf_stat=-3.0,
                          adf_pvalue=adf_p, adf_rejects=a, kpss_stat=0.9,
                          kpss_pvalue=kpss_p, kpss_rejects=k, verdict=v)


def _ts():
    rng = np.random.default_rng(210)
    y = np.exp(4 + np.cumsum(0.003 + 0.01 * rng.standard_normal(200)))
    return fue.TimeSeries(y.tolist(), freq=12, start=(2010, 1), name="R")


def _resumen(monkeypatch, filas, **kw):
    monkeypatch.setattr(D_, "unit_root_tests", lambda *a, **k: filas)
    out = D_.describe_unit_root(_ts(), lam=0.0, **kw)
    linea = next(l for l in out.summary.splitlines()
                 if l.startswith("**Lo que encuentran"))
    return out, linea


def test_retiro_ambiguo_no_es_consenso(monkeypatch):
    out, linea = _resumen(monkeypatch, [_fila(0, 0.9987, 0.01),
                                        _fila(1, 0.0230, 0.01)], max_d=1)
    assert out.data["recommended_d"] == 1          # la d no cambia
    assert "con consenso" not in linea
    assert "ambigua" in linea and "sin consenso" in linea
    assert "p=0.0230" in linea


def test_ipc_es_nombra_el_unico_orden_con_consenso(monkeypatch):
    out, linea = _resumen(monkeypatch, [_fila(0, 0.0363, 0.01),
                                        _fila(1, 0.0000, 0.01),
                                        _fila(2, 0.0000, 0.0739)], max_d=2,
                          current_d=1)
    assert out.data["recommended_d"] == 0
    assert "estacionaria en niveles" not in linea
    assert "único orden con consenso" in linea and "d=2" in linea


def test_con_consenso_la_frase_de_siempre(monkeypatch):
    _, linea = _resumen(monkeypatch, [_fila(0, 0.99, 0.01),
                                      _fila(1, 0.001, 0.30)], max_d=1)
    assert "d = 1 (primera diferencia con consenso)" in linea


def test_la_frase_del_adf_lee_su_propio_p(monkeypatch):
    """Soporte del nodo 3: ADF rechaza (p=0,031), KPSS rechaza."""
    monkeypatch.setattr(RU, "adf", lambda x: (-3.04, 0.0314, 0, len(x), {}))
    monkeypatch.setattr(RU, "kpss", lambda x: (1.03, 0.0100, 4, {}))
    txt = D_.describe_seasonality(_ts()).summary
    assert "no rechaza la raíz unitaria" not in txt
    assert "rechaza la raíz unitaria (p=0.0314)" in txt
    assert "el KPSS rechaza la estacionariedad (p=0.0100)" in txt


def test_cuando_el_adf_no_rechaza_lo_sigue_diciendo(monkeypatch):
    monkeypatch.setattr(RU, "adf", lambda x: (-1.5, 0.52, 0, len(x), {}))
    monkeypatch.setattr(RU, "kpss", lambda x: (0.2, 0.10, 4, {}))
    txt = D_.describe_seasonality(_ts()).summary
    assert "no rechaza la raíz unitaria (p=0.5200)" in txt
