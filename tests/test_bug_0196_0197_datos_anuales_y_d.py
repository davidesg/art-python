"""BUG-0196: annual data have no seasonal frequencies. BUG-0197: node 3 says
one thing about d.

The muskrat (Jenkins and Alavi 1981; annual, 1850-1911, 62 values):

* node 3 no longer publishes a HAC F with zero numerator degrees of freedom,
  an empty figure and the B1/B2 routes — D = 0 by construction;
* the identification listing does not recommend harmonics for annual data;
* the Q that decides keeps at least 2 degrees of freedom: with a long model
  the lag moves up instead of leaving 1 or 0;
* at d = 1 the ADF does not reject and the KPSS accepts (ambiguous): one
  decision, «se sigue con d=1», with the caveat — not «Considera d=2», «d = 1,
  no 2» and «Reentra con d=2» at once.
"""
import os
import shutil

import pytest

pytest.importorskip("fue")
import fue  # noqa: E402
from art.describe import describe_identification, describe_seasonality  # noqa: E402
from art.diagnosis import MIN_Q_DF, q_decisive  # noqa: E402
from art.mcp_server import _load_ts_model, guided_identification  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0196_0197")


@pytest.fixture(scope="module")
def muskrat(tmp_path_factory):
    d = tmp_path_factory.mktemp("muskrat")
    shutil.copy(os.path.join(F, "MUSKRAT.inp"), d)
    return str(d / "MUSKRAT.inp")


@pytest.fixture(scope="module")
def node3(muskrat):
    out = guided_identification(inp_path=muskrat, lam=0.0, d=1, objetivo="multivariante")
    return out[0].text, len(out) - 1


def test_no_seasonality_test_on_annual_data(muskrat):
    ts, _ = _load_ts_model(muskrat)
    sea = describe_seasonality(ts)
    assert sea.data["annual"] and sea.data["decision"] == "A" and sea.figure_b64 is None
    assert "D = 0 por construcción" in sea.summary


def test_node3_annual_says_it_and_publishes_no_f(node3):
    text, n_images = node3
    assert "Datos anuales" in text
    assert "F-test HAC" not in text and "F=0.00" not in text
    assert "Route B1" not in text and "picos en ACF/PACF a lags s, 2s" not in text
    assert n_images == 1                          # the series; no seasonality figure


def test_node3_one_decision_about_d(node3):
    text, _ = node3
    assert "Considera d=2" not in text
    assert "Punto de partida recomendado" not in text
    assert "Reentra con" not in text
    assert "Se sigue con d=1" in text


def test_identification_listing_no_harmonics_for_annual_data(muskrat):
    ts, _ = _load_ts_model(muskrat)
    r = describe_identification(ts, d=1, D=0, lam=0.0)
    assert "Añade armónicos" not in r.recommendation
    assert "Datos anuales: sin armónicos" in r.recommendation
    assert "SARIMA" not in r.recommendation


def test_the_decisive_q_keeps_two_degrees_of_freedom(muskrat):
    """AR(8) on the muskrat's differenced logs: 8 ARMA parameters; the 9 lags
    of the annual convention would leave 1 degree of freedom — the lag moves
    up to 10."""
    ts, _ = _load_ts_model(muskrat)
    m = fue.Model(ts, ar=[[0.1] * 8], d=1, boxlam=0.0, refactor=1.0)
    m.fit()
    lag, df, _q, _p = q_decisive(m)
    assert MIN_Q_DF == 2
    assert (lag, df) == (10, 2)
