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
    return _fn("overparameterization_analysis")(p)[0].text


def test_el_pre_tiene_la_covarianza_degenerada():
    if not os.path.exists(RATIO_PRE):
        pytest.skip("datos de la réplica no disponibles")
    warnings.simplefilter("ignore")
    from art.mcp_server import _load_fitted
    from art.diagnosis import covariance_is_degenerate
    _, m = _load_fitted(RATIO_PRE)
    assert covariance_is_degenerate(m._result), (
        "el caso ya no reproduce la degeneración; el test no mide nada")


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
