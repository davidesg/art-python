"""BUG-0042 — el pie de estado era un TERCER predicado de adecuación.

BUG-0036 encontró dos predicados con el mismo nombre y los unificó: el que
publica el veredicto (`DiagnosisResult.residuals_ok` / `.clean`) y el de la
guarda de `formal_tests`. Quedó un tercero sin tocar, en `_state_footer`, que
miraba Q, JB y extremos — y NO la media residual ni la estacionalidad.

Resultado medido sobre la réplica del TFM: modelos cuyo veredicto era
«REVISAR ✗» y a los que `formal_tests` bloqueaba salían con el pie diciendo
«falta: nada — diagnosis limpia · etapa: contrastes formales». ITCER con media
residual t=−2.17, RATIO con estacionalidad residual p=0.0492.

La regla: `limpio` se construye de los MISMOS componentes que `.clean`. Los
extremos se siguen NOMBRANDO —gobiernan el bucle de intervenciones— pero no
cuentan para «limpio», igual que en `residuals_ok` y por la misma razón: una
intervención arregla un residuo que se porta mal, no una media que falta.
"""
import numpy as np
import pytest

import fue
from art.diagnosis import diagnose
from art.mcp_server import _state_footer
from art.pipeline import _write_inp, _load_fitted


def _fit(ts, tmp_path, nombre, **kw):
    ruta = str(tmp_path / f"{nombre}.inp")
    m = fue.Model(ts, boxlam=1.0, **kw)
    _write_inp(ts, m, ruta)
    _, mf = _load_fitted(ruta)
    return mf, ruta


def test_a_drifting_mean_is_reported_as_missing(tmp_path):
    """Media residual descentrada: `.clean` es falso y el pie tiene que decirlo."""
    rng = np.random.default_rng(11)
    y = 100.0 + np.cumsum(rng.standard_normal(120) + 0.8)   # deriva sin μ
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="DERIVA")
    m, ruta = _fit(ts, tmp_path, "deriva", d=1, ma=[[0.0]], ma_free=[[True]],
                   mu=0.0, estimate_mu=False)
    dg = diagnose(m)
    if dg.centred:
        pytest.skip("este testigo sintético no descentró la media")
    pie = _state_footer(m, ruta)
    assert "media residual" in pie
    assert "nada — diagnosis limpia" not in pie
    assert "contrastes formales — la diagnosis está limpia" not in pie


def test_a_clean_model_still_reads_clean(tmp_path):
    """La otra cara: no romper el caso bueno."""
    rng = np.random.default_rng(5)
    y = 100.0 + np.cumsum(rng.standard_normal(120))
    ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name="RW")
    m, ruta = _fit(ts, tmp_path, "rw", d=1, ma=[[0.0]], ma_free=[[True]],
                   mu=0.0, estimate_mu=False)
    dg = diagnose(m)
    if not dg.clean:
        pytest.skip("este testigo sintético no salió limpio")
    pie = _state_footer(m, ruta)
    assert "nada — diagnosis limpia" in pie
    assert "contrastes formales" in pie


def test_the_footer_agrees_with_the_verdict(tmp_path):
    """La invariante que el bug rompía: el pie y el veredicto son el MISMO
    predicado. Si divergen, el analista recibe dos respuestas a una pregunta."""
    rng = np.random.default_rng(3)
    casos = {
        "limpia": 100.0 + np.cumsum(rng.standard_normal(120)),
        "deriva": 100.0 + np.cumsum(rng.standard_normal(120) + 0.8),
    }
    for nombre, y in casos.items():
        ts = fue.TimeSeries(y.tolist(), freq=4, start=(2000, 1), name=nombre.upper())
        m, ruta = _fit(ts, tmp_path, nombre, d=1, ma=[[0.0]], ma_free=[[True]],
                       mu=0.0, estimate_mu=False)
        dg = diagnose(m)
        pie = _state_footer(m, ruta)
        dice_limpio = "nada — diagnosis limpia" in pie
        assert dice_limpio == dg.clean, (
            f"{nombre}: el pie dice limpio={dice_limpio} y el veredicto "
            f"clean={dg.clean}")


def test_extremes_are_named_but_do_not_block(tmp_path):
    """Los extremos se nombran porque gobiernan el bucle de intervenciones, pero
    no cuentan para «limpio» — igual que en `residuals_ok`."""
    rng = np.random.default_rng(0)
    w = rng.standard_normal(100)
    w[60] += 3.6                       # un extremo aislado, JB y Q pasan
    ts = fue.TimeSeries((100.0 + np.cumsum(w)).tolist(), freq=4,
                        start=(2000, 1), name="UNEXT")
    m, ruta = _fit(ts, tmp_path, "unext", d=1, ma=[[0.0]], ma_free=[[True]],
                   mu=0.0, estimate_mu=False)
    dg = diagnose(m)
    if not (dg.clean and dg.extreme):
        pytest.skip("el testigo no produjo un extremo sobre un modelo limpio")
    pie = _state_footer(m, ruta)
    assert "anómalo" in pie, "el extremo debe nombrarse"
    assert "(nota:" in pie, "y debe ir como NOTA, no como falta"
    assert "nada — diagnosis limpia" in pie, "no bloquea, así que no falta nada"
    assert "contrastes formales" in pie, "y la etapa sigue siendo la suya"
