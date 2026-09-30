"""BUG-0192: the MA template in the Box-Jenkins convention, as the C.

The C (ARMA.c, calcular_coeficientes_psi) has psi_j = -theta_j: (1 - theta B)
(1 - Theta B^s), so its representative theta = 0.3 gives a NEGATIVE bar. The
port passed the same theta > 0 to statsmodels' ArmaProcess as (1 + theta B),
and on Box-Jenkins' series G the airline came fourth.
"""
import os

import numpy as np
import pandas as pd
import pytest

fue = pytest.importorskip("fue")
import art  # noqa: E402
from art.model_detection import _theoretical_acf_pacf  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0192")


def _ts(name, col, start):
    x = pd.read_csv(os.path.join(F, name))[col].values.astype(float)
    return fue.TimeSeries(x, 12, start)


def _orders(ts, n):
    return [(m.p, m.q, m.P, m.Q) for m in art.suggest_orders(ts, d=1, D=1, lam=0.0, top_n=n)]


def test_the_ma_template_has_negative_bars_as_the_c():
    acf, _ = _theoretical_acf_pacf(0, 1, 0, 1, 12, 39)
    assert acf[0] < 0 and acf[11] < 0          # the port had +0.275 at both
    acf, _ = _theoretical_acf_pacf(1, 0, 0, 0, 12, 39)
    assert acf[0] > 0                          # the AR was right, and stays


def test_series_g_proposes_the_airline_first():
    assert _orders(_ts("airline_serie_G.csv", "pasajeros", (1949, 1)), 3)[0] == (0, 1, 0, 1)


def test_spain_cpi_seasonal_ma_the_regular_part_is_the_known_ambiguity():
    """r1 = +0.37 and both ACF and PACF cut at 1: AR(1) and MA(1) are both
    legitimate (a known ambiguity of this series). The seasonal part is not
    ambiguous: ACF cuts at 12, PACF decays. The template's theta > 0 cannot
    make a positive bar, so the airline is not first here; that is the C's
    behaviour too, and it is left so."""
    top = _orders(_ts("IPC_ES_2002_2019.csv", "value", (2002, 1)), 3)
    # BUG-0198: with fitted templates the two readings of the known ambiguity
    # come first, the airline ahead (the pattern ties them; parsimony and the
    # fit settle it) — before, the airline was not first here.
    assert top[:2] == [(0, 1, 0, 1), (1, 0, 0, 1)]
