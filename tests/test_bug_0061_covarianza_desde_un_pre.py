"""BUG-0061 — leer la covarianza de un `.pre` pierde pares, y no se avisaba.

La regla de la escalera: para reestimar se usa el `.inp`; el `.pre` sólo
verifica. `overparameterization_analysis` lee la COVARIANZA, así que le afecta de
lleno — y no infla un número, hace desaparecer acoplamientos enteros.
"""
import os
import warnings

import pytest

from datos_replica import REPLICA, REPLICA_DS


RATIO_PRE = (REPLICA_DS + "run2/"
             "RATIO/RATIO_m23.pre")
RATIO_OUT = RATIO_PRE[:-4] + ".out"


def _fn(name):
    import art.mcp_server as M
    f = getattr(M, name)
    return getattr(f, "fn", f)


def _texto(p):
    if not os.path.exists(p):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    from art.diagnosis import covariance_is_degenerate
    if not covariance_is_degenerate(_load_fitted(p)[1]._result):
        pytest.skip("el testigo de la réplica ya no tiene la covarianza en la "
                    "semilla: no mide nada (lo guarda el caso sintético)")
    return _fn("overparameterization_analysis")(p)[0].text


def test_el_pre_tiene_la_covarianza_degenerada():
    if not os.path.exists(RATIO_PRE):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    from art.diagnosis import covariance_is_degenerate
    _, m = _load_fitted(RATIO_PRE)
    if not covariance_is_degenerate(m._result):
        # Ya no es un testigo: con fue >= 0.1.17 reejecutar el .pre da el
        # hessiano por diferencias, sin semilla. Lo guarda el caso sintético.
        pytest.skip("el testigo de la réplica ya no tiene la covarianza en la "
                    "semilla: no mide nada (la guarda el caso sintético)")


def test_se_avisa_de_que_la_covarianza_no_es_de_fiar():
    t = _texto(RATIO_PRE)
    assert "La covarianza NO es de fiar" in t
    assert "semilla del BFGS" in t


def test_el_aviso_dice_que_pueden_faltar_pares():
    """Lo grave no es el número distinto: es el par que no aparece."""
    t = _texto(RATIO_PRE)
    assert "no aparecen" in t or "incompleto" in t


def test_el_aviso_nombra_la_regla_de_la_escalera():
    t = _texto(RATIO_PRE)
    assert "no el `.pre`" in t
    assert ".out" in t


def test_el_out_publica_un_par_que_el_pre_pierde():
    """La medida del daño, leída de los dos ficheros."""
    if not (os.path.exists(RATIO_OUT) and os.path.exists(RATIO_PRE)):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    # pares del .out (estimación real)
    lineas, dentro = [], False
    for l in open(RATIO_OUT, encoding="utf-8", errors="replace"):
        if "Correlations greater" in l:
            dentro = True; continue
        if dentro and l.strip().startswith("corr["):
            lineas.append(l.strip())
        elif dentro and lineas and not l.strip():
            break
    # pares del .pre
    from art.mcp_server import _load_fitted
    from art.diagnosis import _compute_param_corr
    _, m = _load_fitted(RATIO_PRE)
    _, pares, _ = _compute_param_corr(m, threshold=0.7)
    if len(lineas) <= len(pares):
        pytest.skip("el testigo de la réplica ya no pierde pares: no mide nada "
                    "(lo guarda test_sintetico_la_semilla_borra_el_par)")
    assert len(lineas) > len(pares), (
        f"el .out da {len(lineas)} pares y el .pre {len(pares)}: "
        "el caso ya no ilustra la pérdida")


def test_sin_degeneracion_no_se_avisa(tmp_path):
    """El aviso sólo aparece donde hay algo que advertir."""
    import numpy as np
    import fue
    from art.pipeline import ModelSpec, build_and_fit
    from art.diagnosis import covariance_is_degenerate
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(4)
    a = rng.standard_normal(220)
    w = np.zeros(220)
    for t in range(2, 220):
        w[t] = 0.5 * w[t - 1] - 0.3 * w[t - 2] + a[t]
    ts = fue.TimeSeries((100 + np.cumsum(w) / 15).tolist(), freq=4,
                        start=(2000, 1), name="LIMPIO")
    inp = str(tmp_path / "L.inp")
    fr = build_and_fit(ts, ModelSpec(lam=1.0, d=1, D=0, p=2, q=0, P=0, Q=0,
                                     n_harmonics=0), inp, 3.5)
    if covariance_is_degenerate(fr.model._result):
        pytest.skip("la estimación dejó varianzas en la semilla")
    assert "La covarianza NO es de fiar" not in _fn(
        "overparameterization_analysis")(inp)[0].text


# ── el mismo caso, construido: no depende de la réplica ────────────────────
#
# Con fue >= 0.1.17 reejecutar un .pre da el hessiano por diferencias y la
# semilla ya no aparece; el aviso sigue haciendo falta cuando fue cae al BFGS.
# Un ARMA(1,1) cuyo AR y MA correlacionan > 0.7, puesto en ese estado: método
# BFGS y una varianza exactamente en la semilla 2/n.

def _arma11(seed=1):
    import numpy as np
    import fue
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(seed)
    n = 200
    a, w = rng.standard_normal(n), np.zeros(n)
    for t in range(1, n):
        w[t] = 0.7 * w[t - 1] + a[t] - 0.4 * a[t - 1]
    ts = fue.TimeSeries((100 + np.cumsum(w)).tolist(), freq=4, start=(2000, 1), name="S")
    m = fue.Model(ts, boxlam=1.0, d=1, ar=[[0.0]], ar_free=[[True]],
                  ma=[[0.0]], ma_free=[[True]], mu=0.0, estimate_mu=False)
    m.fit()
    return ts, m


def _a_la_semilla(m, i):
    import numpy as np
    r = m._result
    n = len(np.asarray(r.residuals, dtype=float))
    cov = np.array(r.cov_matrix, dtype=float, copy=True)
    cov[i, :] = 0.0
    cov[:, i] = 0.0
    cov[i, i] = 2.0 / n
    r.cov_matrix = cov
    r.std_errors = np.sqrt(np.diag(cov))
    r.se_method = "bfgs (fdhess: no salió)"
    return m


def test_sintetico_la_semilla_borra_el_par():
    """La medida del daño: el par alto que la covarianza buena da, la semilla lo
    hace desaparecer."""
    from art.diagnosis import _compute_param_corr, covariance_is_degenerate
    _, m = _arma11()
    _, antes, _ = _compute_param_corr(m, threshold=0.7)
    assert antes, "el AR y el MA de este ARMA(1,1) deberían correlacionar > 0.7"
    _a_la_semilla(m, 1)
    assert covariance_is_degenerate(m._result)
    _, despues, _ = _compute_param_corr(m, threshold=0.7)
    assert len(despues) < len(antes)


def test_sintetico_el_aviso_de_un_pre(tmp_path, monkeypatch):
    """Sobre un `.pre` con la covarianza en la semilla, el informe avisa: no es
    de fiar, pueden faltar pares, la regla de la escalera y el `.out`."""
    import art.mcp_server as M
    ts, m = _arma11()
    _a_la_semilla(m, 1)
    pre = str(tmp_path / "S_m01.pre")
    monkeypatch.setattr(M, "_load_fitted", lambda path, *a, **k: (ts, m))
    t = _fn("overparameterization_analysis")(pre)[0].text
    assert "La covarianza NO es de fiar" in t and "semilla del BFGS" in t
    assert "no aparecen" in t
    assert "no el `.pre`" in t and ".out" in t
