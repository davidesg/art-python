"""BUG-0195: one Q of the residuals, one label (lag AND degrees of freedom).

On HICP_ES_m02 (7 ARMA parameters) the diagnosis gave Q(39) p = 0.043, fails,
and the scan of the residuals Q(39) p = 0.179, "pasa", claiming to be the same
as the figure's, which said Q(32). The right one is the diagnosis': 39 lags
minus 7 ARMA parameters, 32 df.
"""
import os
import shutil

import pytest

pytest.importorskip("fue")
import fue  # noqa: E402
from art.describe import _resid_start, describe_prelim_scan  # noqa: E402
from art.diagnosis import diagnose, q_decisive, q_label  # noqa: E402
from art.mcp_server import _load_ts_model  # noqa: E402

F = os.path.join(os.path.dirname(__file__), "fixtures", "bug_0194_0195")


@pytest.fixture(scope="module")
def m02(tmp_path_factory):
    d = tmp_path_factory.mktemp("m02")
    shutil.copy(os.path.join(F, "HICP_ES_m02.pre"), d)
    ts, m = _load_ts_model(str(d / "HICP_ES_m02.pre"))
    m.fit()
    return ts, m


def test_diagnosis_and_scan_give_the_same_q(m02):
    ts, m = m02
    dg = diagnose(m)
    lag, df, q, p = q_decisive(m)
    assert (lag, df) == (39, 32) and dg.q_df_correction == 7
    assert q == pytest.approx(dg.q_stats[-1]) and p == pytest.approx(dg.q_pvalues[-1])
    assert p == pytest.approx(0.0428, abs=5e-4)
    rts = fue.TimeSeries(m.residuals.data, freq=ts.freq, start=_resid_start(m), name="R")
    txt = describe_prelim_scan(rts, d=0, D=0, lam=1.0, q_model=m).summary
    assert "Q(39 retardos, 32 g.l.)" in txt and "(p=0.043)" in txt and "RECHAZA" in txt
    assert "la misma que la figura" not in txt


def test_the_label_says_lag_and_df():
    assert q_label(39, 32) == "Q(39 retardos, 32 g.l.)"


def test_without_a_model_df_is_the_lag(m02):
    ts, m = m02
    rts = fue.TimeSeries(m.residuals.data, freq=ts.freq, start=_resid_start(m), name="R")
    txt = describe_prelim_scan(rts, d=0, D=0, lam=1.0).summary
    line = next(l for l in txt.splitlines() if "Q(" in l)
    lag = int(line.split("Q(")[1].split(" ")[0])
    assert f"Q({lag} retardos, {lag} g.l.)" in line and "sin modelo" in line
