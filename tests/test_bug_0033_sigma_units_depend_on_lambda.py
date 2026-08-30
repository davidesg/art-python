"""BUG-0033 — el `%` de σ̂ₐ sólo es cierto si λ=0.

fue escala los residuos por `refactor` (×100 desde el escritor de ART). Qué
SIGNIFICA ese residuo escalado depende de λ:

    λ=0, refactor=100  →  ∇ln(y)·100   ES un porcentaje.
    λ=1, refactor=100  →  ∇y·100       son las UNIDADES de la serie ×100.

La regla miraba sólo `refactor` y ponía el `%` en los dos casos. En un modelo en
niveles eso publica un número 100× inflado con una etiqueta que miente.

Testigo real: PGAS de la réplica del TFM. El carril guiado (logs) salía con
«σ̂ₐ = 7.8695%» y el autónomo (niveles) con «σ̂ₐ = 2273.6533%», cuando la
innovación del segundo es de 22.87 USD/t sobre una media de 294.44 — un 7.8%,
casi exactamente lo mismo. El defecto hacía parecer que dos modelos con la misma
innovación diferían en dos órdenes de magnitud, y eso invalida la comparación
entre carriles, que es para lo que la réplica existe.
"""
import os

import numpy as np
import pytest

import fue
from art.describe import model_equation
from art.pipeline import _make_model, _write_inp


def _serie_positiva_con_deriva(seed=11, n=84):
    rng = np.random.default_rng(seed)
    w = 0.08 * rng.standard_normal(n)
    level = 300.0 * np.exp(np.cumsum(w))
    return fue.TimeSeries(level.tolist(), freq=4, start=(2004, 1), name="NIVEL")


def _fit_via_inp(ts, lam, tmp_path):
    """Hay que pasar POR EL .inp: el ×100 lo pone el escritor de ART, y es la
    rama donde vive el defecto. Un fue.Model a mano sale con refactor=1."""
    ruta = str(tmp_path / f"nivel_lam{lam:g}.inp")
    _write_inp(ts, _make_model(ts, lam, 1, 0, 0, 1, 0), ruta)
    ts_l, m = fue.load(ruta)
    m.fit()
    return ts_l, m


def _linea_sigma(ts, m):
    return [l.strip() for l in model_equation(ts, m).splitlines() if "σ̂ₐ" in l][0]


def test_a_log_model_keeps_the_percent_sign(tmp_path):
    ts = _serie_positiva_con_deriva()
    ts_l, m = _fit_via_inp(ts, 0.0, tmp_path)
    assert float(getattr(m, "refactor", 1.0)) >= 10, "el .inp no trae el ×100"
    linea = _linea_sigma(ts_l, m)
    assert "%" in linea, "un modelo en logs SÍ tiene la innovación en porcentaje"


def test_a_level_model_reports_units_not_a_percentage(tmp_path):
    ts = _serie_positiva_con_deriva()
    ts_l, m = _fit_via_inp(ts, 1.0, tmp_path)
    linea = _linea_sigma(ts_l, m)
    # separa la parte de sigma del resto de la línea
    sigma_txt = linea.split("|")[0].split("=")[1].strip()
    assert "%" not in sigma_txt, f"un modelo en NIVELES no tiene σ̂ₐ en %: {linea}"

    r = np.asarray(m.residuals.data, float)
    esperado = r.std(ddof=1) / float(m.refactor)
    assert float(sigma_txt) == pytest.approx(esperado, rel=0.02)


def test_the_two_lambdas_report_a_comparable_innovation(tmp_path):
    """La prueba que importa: la MISMA serie con la MISMA especificación en logs
    y en niveles tiene la misma innovación relativa. Si las dos líneas no son
    comparables, el defecto sigue."""
    ts = _serie_positiva_con_deriva()
    y = np.asarray(ts.data, float)

    _tsl, m_log = _fit_via_inp(ts, 0.0, tmp_path)
    _tsn, m_niv = _fit_via_inp(ts, 1.0, tmp_path)

    pct_log = np.asarray(m_log.residuals.data, float).std(ddof=1)
    pct_niv = 100.0 * (np.asarray(m_niv.residuals.data, float).std(ddof=1)
                       / float(m_niv.refactor)) / y.mean()

    assert pct_log == pytest.approx(pct_niv, abs=1.0), (
        f"logs {pct_log:.3f}% vs niveles {pct_niv:.3f}% — no son la misma serie")
