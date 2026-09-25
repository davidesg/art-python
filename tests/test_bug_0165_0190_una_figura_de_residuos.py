"""
BUG-0165 y BUG-0190 — una sola figura de residuos, con la Q bien rotulada.

BUG-0165: había dos constructores de la figura de residuos + ACF/PACF. El carril
guiado dibujaba con pyfug; `record_version`, `build_model`, `full_report` y
`save_diagnosis_report` con `fue.plots`, en otro formato y con otra Q.

BUG-0190: a pyfug no le llegaba lo que sólo sabe el modelo. Con `npar=0` el
paréntesis de la Q eran los RETARDOS, no los grados de libertad; en
`guided_identification` con `pre_path` los residuos iban sin pasar a fracción
(σ ×100); y el recuento de ARMA del texto se dejaba los factores de frecuencia
fija.

Los tres `.pre` son modelos reales del run 3 de SF_MEG (IPC de España):

    A_m00   10 armónicos, AR(1) FIJO en 0     → 0 ARMA estimados → Q(39)
    A_m02   10 armónicos, MA(1) libre         → 1                → Q(38)
    A_m06   AR(1) + MA(2) de frecuencia fija  → 2                → Q(37)
"""

import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
from scipy import stats

import fue

FIX = Path(__file__).parent / "fixtures" / "bug_0190"


def _modelo(stem):
    out = fue.load(str(FIX / f"ES_CPI_{stem}.pre"))
    m = next(x for x in (out if isinstance(out, tuple) else (out,))
             if hasattr(x, "fit"))
    m._inp_stem = f"ES_CPI_{stem}"
    m.fit()
    return m


def _etiqueta_q(fig):
    """El rótulo de la Q: el xlabel del panel de la ACF que empieza por 'Q('."""
    for ax in fig.axes:
        lbl = ax.get_xlabel()
        if lbl.startswith("Q"):
            return lbl
    raise AssertionError("la figura no rotula ninguna Q")


# ── la figura: el paréntesis son los grados de libertad ──────────────────────

@pytest.mark.parametrize("stem,q", [
    ("A_m00", "Q(39)"),
    ("A_m02", "Q(38)"),
    ("A_m06", "Q(37)"),
])
def test_la_q_de_la_figura_lleva_los_gl_del_modelo(stem, q):
    from art.diagnosis import figura_residuos
    fig = figura_residuos(_modelo(stem))
    try:
        assert _etiqueta_q(fig).startswith(q + " ")
    finally:
        plt.close(fig)


def test_la_serie_de_residuos_va_en_fraccion_y_fechada():
    """pyfug rotula ×100 %: los residuos le llegan en fracción, fechados."""
    import numpy as np
    from fue.diagnostics import residuals_start
    from art.diagnosis import serie_residuos_pyfug
    m = _modelo("A_m02")
    serie = serie_residuos_pyfug(m)
    assert np.std(serie.data) == pytest.approx(
        np.std(np.asarray(m.residuals.data)) / m.refactor)
    assert (serie.begyear, serie.begtime) == residuals_start(m)


# ── el texto: el recuento de ARMA cuenta los factores de frecuencia fija ─────

def test_el_texto_cuenta_el_factor_de_frecuencia_fija():
    from art.diagnosis import diagnose
    m = _modelo("A_m06")
    d = diagnose(m)
    for lag, q, p in zip(d.q_lags, d.q_stats, d.q_pvalues):
        assert p == pytest.approx(1 - stats.chi2.cdf(q, lag - 2), abs=1e-9)


# ── todas las rutas pasan por el mismo constructor ───────────────────────────

@pytest.fixture
def llamadas(monkeypatch):
    """Cuenta las figuras hechas por el constructor único, y prohíbe fue.plots.

    Con pyfug instalado nadie debe dibujar residuos con fue.plots. Contar las
    llamadas —y no sólo prohibir la vieja— es necesario: `record_version`
    se traga la excepción de su figura, y la prohibición sola no se vería.
    """
    import art.diagnosis as dg
    import fue.plots as fp
    cuenta = {"n": 0}
    real = getattr(dg, "figura_residuos", None)

    def _cuenta(*a, **k):
        cuenta["n"] += 1
        return real(*a, **k)

    def _prohibido(*a, **k):
        raise AssertionError("se dibujó la figura de residuos con fue.plots")
    monkeypatch.setattr(dg, "figura_residuos", _cuenta, raising=False)
    monkeypatch.setattr(fp, "plot_model_diagnostics", _prohibido)
    return cuenta


def test_record_version_usa_la_figura_del_guiado(tmp_path, llamadas):
    from art.mcp_server import record_version
    inp = tmp_path / "ES_CPI_A_m02.pre"
    shutil.copy(FIX / "ES_CPI_A_m02.pre", inp)
    record_version(inp_path=str(inp), guion_path=str(tmp_path / "g.json"),
                   decision="adoptado", rationale="test")
    assert llamadas["n"] == 1


def test_full_report_usa_la_figura_del_guiado(tmp_path, llamadas):
    from art.full_report import save_full_report
    save_full_report(_modelo("A_m02"), str(tmp_path / "r.html"), run_meg=False)
    assert llamadas["n"] == 1


def test_save_diagnosis_report_usa_la_figura_del_guiado(tmp_path, llamadas):
    from art.diagnosis import save_diagnosis_report
    save_diagnosis_report(_modelo("A_m02"), str(tmp_path / "d.html"))
    assert llamadas["n"] == 1


# ── guided_identification con pre_path: gl del modelo y fracción ────────────

def test_la_identificacion_sobre_residuos_lleva_npar(monkeypatch):
    import art.describe as ds
    visto = {}
    real = ds._pyfug_combined

    def _espia(ser, **kw):
        visto.update(kw)
        return real(ser, **kw)
    monkeypatch.setattr(ds, "_pyfug_combined", _espia)
    m = _modelo("A_m02")
    res = fue.TimeSeries([v / m.refactor for v in m.residuals.data],
                         freq=12, start=(2002, 2), name="Resid")
    ds.describe_identification(res, d=0, D=0, lam=1.0, npar=1)
    assert visto["npar"] == 1
    assert visto["nlags"] == 39
