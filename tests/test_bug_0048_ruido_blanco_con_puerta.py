"""BUG-0048 — el ruido blanco entra por la misma puerta que los demás órdenes.

BUG-0044 admitió (0,0,0,0) en la papeleta, con razón. Lo que no vio es que
`_validate_ar(0, ...)` y `_validate_ma(0, ...)` devuelven True sin mirar nada, de
modo que quedaba como el único candidato sin filtro — y la bonificación de
parsimonia lo empuja hacia arriba.

El ruido blanco tiene su propio contraste, la Q de Ljung-Box, y es el que decide.
"""
import warnings

import numpy as np
import pytest

import fue
from fue.diagnostics import ljung_box
from art.model_detection import suggest_orders, _validate_white_noise

from datos_replica import REPLICA, REPLICA_DS, requiere_replica



def _serie(w, freq=4):
    return fue.TimeSeries(w.tolist(), freq=freq, start=(2000, 1), name="X")


def _hay_ruido_blanco(specs):
    return any(s.p == s.q == s.P == s.Q == 0 for s in specs)


def _pos_ruido_blanco(specs):
    return next((i for i, s in enumerate(specs, 1)
                 if s.p == s.q == s.P == s.Q == 0), None)


def test_la_puerta_usa_el_contraste_no_las_bandas():
    """Contar retardos fuera de banda es un sucedáneo; la Q es el contraste."""
    rng = np.random.default_rng(0)
    blanco = rng.standard_normal(200)
    assert _validate_white_noise(blanco, lags=15) is True

    ar = np.zeros(200)
    a = rng.standard_normal(200)
    for t in range(2, 200):
        ar[t] = 0.6 * ar[t - 1] - 0.3 * ar[t - 2] + a[t]
    assert _validate_white_noise(ar, lags=15) is False


def test_un_ar2_no_puede_quedar_por_debajo_del_ruido_blanco():
    """El síntoma que lo destapó, sobre datos sintéticos deterministas.

    Una serie con PACF significativa en dos retardos no admite «no hace falta
    modelo», por muy parsimonioso que sea ese candidato.
    """
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(7)
    a = rng.standard_normal(300)
    w = np.zeros(300)
    for t in range(2, 300):
        w[t] = 0.6 * w[t - 1] - 0.3 * w[t - 2] + a[t]
    w = w[100:]

    lb = ljung_box(w, lags=15, df_correction=0)
    assert float(lb["pvalue"][-1]) < 0.05, "el caso ya no rechaza; no mide nada"

    specs = suggest_orders(_serie(w), d=0, D=0, lam=1.0, top_n=10)
    assert not _hay_ruido_blanco(specs), (
        "la Q rechaza el ruido blanco y aun así entró en la papeleta")


def test_el_ruido_blanco_sigue_ganando_cuando_de_verdad_lo_es():
    """La corrección no puede deshacer BUG-0044: si la Q no rechaza, manda."""
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(3)
    w = rng.standard_normal(200)

    lb = ljung_box(w, lags=15, df_correction=0)
    assert float(lb["pvalue"][-1]) > 0.05, "la muestra no es blanca; cambia semilla"

    specs = suggest_orders(_serie(w), d=0, D=0, lam=1.0, top_n=10)
    assert _pos_ruido_blanco(specs) == 1, (
        "sobre ruido blanco de verdad, (0,0,0,0) tiene que encabezar")


@requiere_replica
def test_el_caso_real_que_lo_destapo():
    """∇ln PGAS: Q(15)=35.90, p=0.0018. El ruido blanco salía CUARTO."""
    warnings.simplefilter("ignore")
    import os
    inp = REPLICA + "PGAS.inp"
    if not os.path.exists(inp):
        pytest.skip("datos de la réplica no disponibles")
    from art.pipeline import _load_ts_model
    ts, _ = _load_ts_model(inp)
    specs = suggest_orders(ts, d=1, D=0, lam=0.0, top_n=10)
    assert not _hay_ruido_blanco(specs)
