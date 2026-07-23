"""BUG-0008 — _forecast_table builds the 95% band from `level_std`, which fue
returns as the std of BoxCox_λ(y), NOT of the level.

For a λ=0 (log) model — every CPI model in this workflow — `level_std` is a
RELATIVE s.e. (a fraction of the level). The band must be converted to absolute
level units with the delta method, se_abs = level_std · level^(1−λ); for λ=0 that
is level_std · level. Without it the interval is ~level× (≈100×) too narrow.
"""
import re
import numpy as np
import fue
from art.pipeline import _make_model
from art.mcp_server import _forecast_table


def _forecast():
    rng = np.random.default_rng(3)
    t = np.arange(240)
    w = 0.0018 + 0.01 * np.cos(2 * np.pi * t / 12) + rng.normal(0.0, 0.004, 240)
    y = np.exp(np.cumsum(w) + 4.6)
    ts = fue.TimeSeries.from_array(y.tolist(), freq=12, start=(2002, 1), name="X")
    m = _make_model(ts, lam=0.0, d=1, D=0, p=1, q=0,
                    n_harmonics=2, P=0, Q=0, estimate_mu=True)
    m.fit()
    return ts, m, m.forecast_fuf(horizon=6)


def _first_row_band(table: str):
    # row 1: | 1 | date | lvl | [lo, hi] | ...
    m = re.search(r"\|\s*1\s*\|[^|]*\|\s*([\d.]+)\s*\|\s*\[\s*([\d.]+),\s*([\d.]+)\s*\]", table)
    assert m, table
    return float(m.group(1)), float(m.group(2)), float(m.group(3))


def test_band_is_in_absolute_level_units():
    ts, m, fr = _forecast()
    lvl0 = float(fr.level[0])
    se0  = float(fr.level_std[0])            # relative (fraction of level) for λ=0

    table = _forecast_table(ts, fr, 6, boxlam=0.0)
    lvl, lo, hi = _first_row_band(table)

    half = (hi - lo) / 2.0
    # correct absolute half-width uses se_abs = level_std · level
    assert np.isclose(half, 1.96 * se0 * lvl0, rtol=1e-3), (half, 1.96 * se0 * lvl0)
    # and it is emphatically NOT the old, ~level× too-narrow relative band
    assert half > 10 * (1.96 * se0), (half, 1.96 * se0)


def test_lambda_one_band_unchanged():
    # for λ=1 the std is already absolute; level^(1-λ)=1 leaves it untouched.
    ts, m, fr = _forecast()
    se0 = float(fr.level_std[0])
    table = _forecast_table(ts, fr, 6, boxlam=1.0)
    _, lo, hi = _first_row_band(table)
    # tiny band (~0.004) printed to 4 decimals -> compare with an atol that covers
    # the rounding rather than a tight rtol.
    assert np.isclose((hi - lo) / 2.0, 1.96 * se0, atol=5e-4)
