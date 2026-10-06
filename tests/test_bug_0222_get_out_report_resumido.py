"""BUG-0222 — `get_out_report` sólo devolvía el `.out` entero (≈ 40 KB).

En el carril autónomo se lee decenas de veces para tres cifras, y cada lectura
entera —la serie tipificada línea a línea, el histograma, la ACF/PACF dibujadas
y la calibración de la FAS— satura el contexto. `resumen=True` devuelve, del
MISMO fichero, lo que decide un nodo: parámetros con e.t. y t, σ̂ₐ, ℓ/AIC/BIC,
correlaciones altas, raíces, Q en 12/24/36/39 con g.l. y p, JB y anómalos con
fecha. Validación pedida: < 3 KB con todas esas cifras.

De paso: el lector daba `residuos.n = 2` para «175 observations: from 2/2011»
—cogía el mes de la fecha—, y con él el BIC habría salido mal.
"""
import math
import os
import re
import shutil
import warnings

import numpy as np
import pytest

fue = pytest.importorskip("fue")
os.environ.setdefault("ART_NO_VIEWER", "1")

import art.mcp_server as srv
from art.outfile import lee_out, lee_texto_out, resumen_out
from art.pipeline import _RESCALE_FACTOR, _load_fitted, _write_inp

GOR = getattr(srv.get_out_report, "fn", srv.get_out_report)


@pytest.fixture(scope="module")
def terna(tmp_path_factory):
    """Mensual, ∇∇₁₂ con AR(1)·MA(1)·MA₁₂(1) y un anómalo en 6/2010."""
    d = tmp_path_factory.mktemp("b222")
    rng = np.random.default_rng(222)
    n = 192
    a = rng.standard_normal(n + 13)
    w = a[13:] - 0.5 * a[1:-12] - 0.6 * a[:-13]
    for s in range(12, n):                       # ∇₁₂⁻¹
        w[s] += w[s - 12]
    y = 100.0 + np.cumsum(w) * 0.1               # ∇⁻¹
    y[90] += 0.5                                 # 7/2007: ≈ 5σ, un anómalo
    ts = fue.TimeSeries(y.tolist(), freq=12, start=(2000, 1), name="R222")
    m = fue.Model(ts, d=1, D=1, ar=[[0.0]], ar_free=[[True]],
                  ma=[[0.0]], ma_free=[[True]], ma_s=[[0.0]], ma_s_free=[[True]],
                  mu=0.0, estimate_mu=False, refactor=_RESCALE_FACTOR)
    f_inp = str(d / "R222.inp")
    _write_inp(ts, m, f_inp)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, fit = _load_fitted(f_inp)
    f_pre, f_out = str(d / "R222.pre"), str(d / "R222.out")
    fit.write_pre(f_pre)
    fit.write_out(f_out)
    return f_inp, f_pre, f_out, fit, str(d)


def _txt(p, **kw):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return "\n".join(getattr(c, "text", "") for c in GOR(p, **kw))


def test_el_defecto_sigue_siendo_el_out_entero(terna):
    _, f_pre, f_out, _, _ = terna
    t = _txt(f_pre)
    assert "Standardized time series plot" in t
    assert open(f_out, encoding="utf-8").read().strip() in t


def test_el_resumen_cabe_en_3KB_y_es_una_fraccion_del_entero(terna):
    _, f_pre, _, _, _ = terna
    corto, largo = _txt(f_pre, resumen=True), _txt(f_pre)
    assert len(corto.encode()) < 3000, len(corto.encode())
    assert len(corto) < len(largo) / 10
    for fuera in ("Standardized time series plot", "Calibration of distortions",
                  "histogram", "u[ 1]"):
        assert fuera not in corto


def test_n_de_residuos_no_es_el_mes_de_la_fecha(terna):
    _, _, f_out, fit, _ = terna
    r = lee_out(f_out)
    assert r.residuos.n == len(fit._result.residuals)
    assert r.residuos.n > 100


def test_parametros_con_et_y_t(terna):
    _, f_pre, f_out, _, _ = terna
    t = _txt(f_pre, resumen=True)
    r = lee_out(f_out)
    assert len(r.parametros) == 3
    for p in r.parametros:
        assert f"{p.valor:.6f} | {p.se:.6f} | {p.t:.2f}" in t
    for etq in ("φ1 [AR regular 1]", "θ1 [MA regular 1]", "Θ1 [MA anual 1]"):
        assert etq in t


def test_sigma_loglik_aic_bic_cuadran_con_fue(terna):
    _, f_pre, _, fit, _ = terna
    t = _txt(f_pre, resumen=True)
    assert "σ̂ₐ = " in t and "ℓ = " in t
    aic = float(re.search(r"AIC = (-?\d+\.\d+)", t).group(1))
    bic = float(re.search(r"BIC = (-?\d+\.\d+)", t).group(1))
    assert abs(aic - float(fit.aic)) < 0.01
    assert abs(bic - float(fit.bic)) < 0.01


def test_ljung_box_en_12_24_36_39_con_gl_y_p(terna):
    _, f_pre, _, _, _ = terna
    t = _txt(f_pre, resumen=True)
    lags = [int(x) for x in re.findall(r"Q\((\d+)\) = \d+\.\d+, g\.l\. \d+, p ", t)]
    assert lags == [12, 24, 36, 39]
    # g.l. = retardo − parámetros ARMA (3)
    for lag, gl in re.findall(r"Q\((\d+)\) = \d+\.\d+, g\.l\. (\d+)", t):
        assert int(gl) == int(lag) - 3


def test_jarque_bera_con_p(terna):
    _, f_pre, f_out, _, _ = terna
    t = _txt(f_pre, resumen=True)
    jb = lee_out(f_out).residuos.jarque_bera
    assert f"**Jarque-Bera:** {jb:.2f}, p " in t


def test_anomalos_con_fecha(terna):
    _, f_pre, _, _, _ = terna
    t = _txt(f_pre, resumen=True)
    linea = next(L for L in t.split("\n") if L.startswith("**Anómalos"))
    assert "7/2007" in linea


def test_raices_por_factor_y_la_anual_en_B12(terna):
    _, f_pre, f_out, _, _ = terna
    t = _txt(f_pre, resumen=True)
    assert "**Raíces**" in t
    assert re.search(r"MA anual 1 \(en B\^12\): -?\d+\.\d+ \(\|z\|=", t)
    # la raíz del AR(1) es 1/φ
    phi = lee_out(f_out).parametros[0].valor
    m = re.search(r"AR regular 1 \(en B\): (-?\d+\.\d+)", t)
    assert abs(float(m.group(1)) - 1 / phi) < 1e-3 * max(1, abs(1 / phi))


def test_correlaciones_altas_con_nombre():
    """Un `.out` con la sección poblada: los índices se traducen a nombres."""
    texto = ("Coefficients for regular AR factor 1:\n"
             "     -0.029371  (0.206820) [ 1]\n"
             "Coefficients for regular MA factor 1:\n"
             "     -0.389709  (0.190444) [ 2]\n"
             "Mean parameter (mu):\n      0.000000\n\n"
             "Box-Cox lambda     :  0.0\n"
             "Correlations greater than or equal to 0.7 in absolute value:\n\n"
             "corr[ 2][ 1] =  0.93\n\n")
    t = resumen_out(lee_texto_out(texto, "x.out"))
    assert "θ1 [MA regular 1] ~ φ1 [AR regular 1]: +0.93" in t


def test_sin_out_resume_la_reestimacion_y_lo_dice(terna):
    f_inp, _, _, _, d = terna
    solo = os.path.join(d, "solo")
    os.makedirs(solo, exist_ok=True)
    g = os.path.join(solo, "S222.inp")
    shutil.copy(f_inp, g)
    t = _txt(g, resumen=True)
    assert "REESTIMADO" in t
    assert "**Resumen de `S222.out`**" in t
    assert "Q(12)" in t and len(t.encode()) < 3500


def test_por_encima_de_8_sigmas_no_hay_tabla_y_se_dice():
    """fue no publica la tabla de anómalos si alguno pasa de 8σ: el resumen no
    puede decir «ninguno», tiene que decir por qué falta."""
    texto = ("Unconditional residuals (seasonal period: 12)\n"
             "175 observations: from 2/2011 to 8/2025\n\n"
             "               Minimum:          -9.635111 at  4/2019 (observation  99)\n"
             "               Maximum:           4.510053 at  7/2024 (observation 162)\n\n"
             "Warning: at least one observation above 8 sigmas\n")
    t = resumen_out(lee_texto_out(texto, "x.out"))
    assert "8σ" in t and "4/2019" in t and "ninguno" not in t
