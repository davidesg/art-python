"""BUG-0219 — escalas y rótulos de dos figuras de pyfug.

1. Serie del paso 2 en log: «w̄ (σ̂w̄) = 429,39 % (0,66 %)» para ln IPC_ES. pyfug
   multiplica por 100 porque fug dibuja TASAS; un nivel en log no lo es. Ahora,
   fuera de log + diferencias, la línea va en la escala de la serie, sin %.
2. Histograma de residuos: eje «%» que es 100·densidad (barra central > 100).
   Ahora en densidad, rotulado «densidad».
"""
import os

import numpy as np
import pytest

fue = pytest.importorskip("fue")
pytest.importorskip("pyfug")
os.environ.setdefault("ART_NO_VIEWER", "1")

import matplotlib
matplotlib.use("Agg")

import art.describe as D_
import art.mcp_server as srv
from art.pipeline import _write_inp, estimar


def _ts():
    rng = np.random.default_rng(219)
    y = np.exp(4.6 + np.cumsum(0.002 + 0.004 * rng.standard_normal(216)))
    return fue.TimeSeries(y.tolist(), freq=12, start=(2002, 1), name="P")


def _linea_w(monkeypatch, lam, d):
    figs = []
    real = D_._fig_b64
    monkeypatch.setattr(D_, "_fig_b64",
                        lambda fig, *a, **k: figs.append(fig) or real(fig, *a, **k))
    assert srv._plot_series_at_d(_ts(), lam=lam, d=d)
    txt = [t.get_text() for t in figs[0].texts if r"\bar{w}" in t.get_text()]
    assert txt, "pyfug ya no escribe la línea de w̄"
    return txt[0]


def test_nivel_en_log_sin_porcentaje(monkeypatch):
    t = _linea_w(monkeypatch, 0.0, 0)
    assert "%" not in t
    z = np.log(np.asarray(_ts().data))
    assert f"{z.mean():.2f}" in t                    # ≈4.6, no 460 %


def test_la_tasa_sigue_en_porcentaje(monkeypatch):
    t = _linea_w(monkeypatch, 0.0, 1)
    assert "%" in t


def test_niveles_sin_log_sin_porcentaje(monkeypatch):
    assert "%" not in _linea_w(monkeypatch, 1.0, 1)


@pytest.fixture(scope="module")
def modelo(tmp_path_factory):
    ts = _ts()
    f = str(tmp_path_factory.mktemp("b219") / "P.inp")
    _write_inp(ts, fue.Model(ts, d=1, boxlam=0.0), f)
    _, m = estimar(f)
    return m


def _comprueba_densidad(fig):
    ax = fig.axes[0]
    assert ax.get_ylabel() == "densidad"
    alturas = [p.get_height() for p in ax.patches]
    # densidad de una variable tipificada: el área de las barras es 1
    assert sum(alturas) * 0.5 == pytest.approx(1.0, abs=0.02)
    curva = [ln for ln in ax.lines if len(ln.get_xdata()) > 2][0]
    assert max(curva.get_ydata()) == pytest.approx(0.3989, abs=1e-3)
    assert ax.get_ylim()[1] < 2


def test_histograma_de_la_diagnosis_en_densidad(modelo, monkeypatch):
    figs = []
    real = D_._fig_b64
    monkeypatch.setattr(D_, "_fig_b64",
                        lambda fig, *a, **k: figs.append(fig) or real(fig, *a, **k))
    d = D_.describe_diagnosis(modelo)
    assert d.data.get("hist_b64")
    hist = [f for f in figs if f.axes and f.axes[0].get_ylabel() == "densidad"]
    assert hist, "el histograma sigue rotulado «%»"
    _comprueba_densidad(hist[0])


def test_plot_diagnosis_histogram_en_densidad(modelo):
    from art.diagnosis import plot_diagnosis_histogram
    _comprueba_densidad(plot_diagnosis_histogram(modelo))
