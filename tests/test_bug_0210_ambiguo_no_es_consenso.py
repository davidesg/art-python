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


# ── Addendum: el nodo d cita la regla que pone la d ─────────────────────────
# IPC_ES_SA (el IPC desestacionalizado de la P02): el ADF con constante rechaza
# en niveles (p=0,036, la serie es cóncava) y `decide_d` sube 0→1 porque una
# recta explica el 91 % del nivel. El texto citaba la plantilla del tope de un
# paso («la estacionalidad sesga el ADF hacia NO rechazar»), y la línea del
# paso 2 daba la d cruda (0) debajo de un punto de partida d=1.

from art import policy


def _sube():
    rng = np.random.default_rng(2100)
    t = np.arange(216)
    y = np.exp(4 + 0.004 * t - 0.000008 * t ** 2
               + 0.002 * rng.standard_normal(216))
    return fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="SA")


_AMBIGUO_EN_NIVELES = [_fila(0, 0.0363, 0.01), _fila(1, 0.0000, 0.01)]


def test_regla_de_la_tendencia_se_dice_como_tal(monkeypatch):
    monkeypatch.setattr(D_, "unit_root_tests",
                        lambda *a, **k: _AMBIGUO_EN_NIVELES)
    out = D_.describe_unit_root(_sube(), lam=0.0, max_d=1)
    s = out.summary
    assert out.data["recommended_d"] == 0
    assert out.data["recommended_d_policy"] == 1
    assert out.data["trend_r2"] > policy.THRESHOLDS["trend_dominates"]
    assert "Punto de partida: d = 1." in s
    assert "tendencia clara" in s and "no tiene potencia" in s
    # ni la plantilla del tope ni el sesgo estacional: aquí el ADF RECHAZÓ
    assert "Un paso cada vez" not in s
    assert "sesga el contraste hacia NO" not in s
    # una fila que se contradice no es un hallazgo de estacionariedad
    assert "estacionaria en niveles" not in s
    linea = next(l for l in s.splitlines() if l.startswith("**Lo que encuentran"))
    assert "d = 0" not in linea and "sin consenso" in linea
    assert "Procede con d=0" not in out.recommendation
    assert "confirmar d=0" not in out.recommendation
    assert "d=1" in out.recommendation


def test_tope_de_un_paso_conserva_su_plantilla(monkeypatch):
    filas = [_fila(0, 0.99, 0.01), _fila(1, 0.40, 0.01), _fila(2, 0.001, 0.30)]
    monkeypatch.setattr(D_, "unit_root_tests", lambda *a, **k: filas)
    s = D_.describe_unit_root(_sube(), lam=0.0, max_d=2).summary
    assert "Punto de partida recomendado: d = 1, no 2" in s
    assert "Un paso cada vez" in s
    assert "tendencia clara" not in s


@pytest.mark.parametrize("rec,r2,seasonal,cur,step", [
    (0, 0.9, None, 0, 1), (0, 0.1, None, 0, 1), (2, 0.9, None, 0, 1),
    (2, 0.1, True, 0, None), (1, 0.9, None, 0, 1), (3, 0.0, None, 1, 1),
    (0, 0.9, True, 0, 1),
])
def test_razon_d_sigue_a_decide_d(rec, r2, seasonal, cur, step):
    data = {"recommended_d": rec, "trend_r2": r2}
    d = policy.decide_d(data, seasonal=seasonal, current_d=cur, max_step=step)
    r = policy.razon_d(data, seasonal=seasonal, current_d=cur, max_step=step)
    assert (r == "") == (d == rec)
    if rec == 0 and r2 > policy.THRESHOLDS["trend_dominates"]:
        assert r == "tendencia"


def test_el_paso_2_da_la_d_de_la_politica(monkeypatch, tmp_path):
    import warnings
    import art.mcp_server as srv
    from art.pipeline import _write_inp
    ts = _sube()
    f = str(tmp_path / "SA.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0), f)
    monkeypatch.setattr(D_, "unit_root_tests",
                        lambda *a, **k: _AMBIGUO_EN_NIVELES)
    fn = getattr(srv.guided_identification, "fn", srv.guided_identification)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = fn(f, lam=0, domain="price_index")
    t = "\n".join(getattr(x, "text", "") or "" for x in out)
    assert "**Recomendación:** d = 1 (la tabla ADF+KPSS, sola, apuntaría a d=0" in t
    assert "Recomendación ADF+KPSS:** d = 0" not in t
    rec = next(l for l in t.splitlines() if "← **recomendado**" in l)
    assert "d=1)" in rec
