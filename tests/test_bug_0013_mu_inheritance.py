"""BUG-0013 — the mean was dropped between the deterministic fit and the ARMA.

Two defects, one symptom. In the reported cases a model was fitted with
harmonics AND a free mean, and the ARMA specification built on top of it came
back with no mean at all:

  1. `_build_arma_on_model` inherited the interventions and the `ifadf` from the
     base model but NOT `mu`/`estimate_mu`, so a fitted mean was silently
     discarded -- a violation of the `.pre` contract, which says a `.pre` is an
     OPTIMUM in re-runnable form.
  2. `run_full` had no way to ask for a mean: `ModelSpec.estimate_mu` defaulted
     to False and no policy decision ever reconsidered it, so EVERY autonomous
     model was fitted with mu pinned at zero.

The asymmetry in (1) is the tell, and the first test states it directly: the
eleven deterministics survived the rebuild identically while the mean did not.
"""
import os

import numpy as np
import pytest

from art.pipeline import _build_arma_on_model, _make_model
from art.policy import DefaultPolicy, ClaudePolicy, THRESHOLDS, decide_mu


def _drifting(n=180, freq=12, slope=0.60, seed=7):
    """A series with an unmistakable drift: mu must be estimated."""
    rng = np.random.default_rng(seed)
    return np.cumsum(slope + rng.normal(0, 1.0, n)) + 100.0


def _driftless(n=180, freq=12, seed=2):   # t = 0.19 on the differenced series
    rng = np.random.default_rng(seed)
    return np.cumsum(rng.normal(0, 1.0, n)) + 100.0


def _ts(values, freq=12, name="X"):
    import fue
    return fue.TimeSeries(list(values), freq=freq, start=(2000, 1), name=name)


# ── (1) the inheritance ────────────────────────────────────────────────────

def test_arma_rebuild_inherits_a_fitted_mean():
    """The invariant the bug report asks for: a free mean survives the rebuild."""
    ts = _ts(_drifting())
    m = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                    estimate_mu=True)
    m.fit()
    mu_fitted = float(m.mu0)
    assert mu_fitted != 0.0, "precondition: the base must have fitted a mean"

    m2 = _build_arma_on_model(m, p=1, q=0)
    assert m2.estimate_mu is True
    assert float(m2.mu0) == pytest.approx(mu_fitted, rel=1e-12), (
        "the fitted mean must be carried, not re-derived and not dropped")


def test_arma_rebuild_carries_mean_and_deterministics_alike():
    """The asymmetry that gave the bug away: both or neither."""
    ts = _ts(_drifting())
    m = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=2,
                    estimate_mu=True)
    m.fit()
    m2 = _build_arma_on_model(m, p=1, q=1)
    assert len(m2.interventions or []) == len(m.interventions or [])
    assert m2.estimate_mu is bool(m.estimate_mu)


def test_arma_rebuild_does_not_invent_a_mean():
    """A base fitted WITHOUT a mean must not acquire one by inheritance."""
    ts = _ts(_driftless())
    m = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                    estimate_mu=False)
    m.fit()
    m2 = _build_arma_on_model(m, p=1, q=0)
    assert m2.estimate_mu is False
    assert float(m2.mu0) == 0.0


def test_explicit_argument_still_overrides_in_both_directions():
    ts = _ts(_drifting())
    m = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                    estimate_mu=True)
    m.fit()
    assert _build_arma_on_model(m, p=1, q=0, estimate_mu=False).estimate_mu is False

    m0 = _make_model(ts, lam=1.0, d=1, D=0, p=0, q=0, n_harmonics=0,
                     estimate_mu=False)
    m0.fit()
    forced = _build_arma_on_model(m0, p=1, q=0, estimate_mu=True)
    assert forced.estimate_mu is True and float(forced.mu0) != 0.0  # seeded


# ── (2) the policy door ────────────────────────────────────────────────────

def test_decide_mu_detects_a_drift_and_ignores_its_absence():
    assert decide_mu(_ts(_drifting()), lam=1.0, d=1, D=0) is True
    assert decide_mu(_ts(_driftless()), lam=1.0, d=1, D=0) is False


def test_decide_mu_is_the_documented_t_statistic():
    """Not a black box: the threshold is a t on the differenced series."""
    ts = _ts(_drifting())
    w = np.diff(np.asarray(ts.data, float))
    t = abs(w.mean()) / (w.std(ddof=1) / np.sqrt(w.size))
    assert bool(t > THRESHOLDS["mu_drift"]) is decide_mu(ts, 1.0, 1, 0)


def test_policies_expose_the_decision():
    ts = _ts(_drifting())
    assert DefaultPolicy().decide_mu(ts, 1.0, 1, 0) is True
    # The analyst overrides; silence falls back to the rule (NOT to False).
    assert ClaudePolicy(estimate_mu=False).decide_mu(ts, 1.0, 1, 0) is False
    assert ClaudePolicy(estimate_mu=True).decide_mu(_ts(_driftless()), 1.0, 1, 0) is True
    assert ClaudePolicy().decide_mu(ts, 1.0, 1, 0) is True


def test_decide_mu_survives_degenerate_input():
    assert decide_mu(_ts([1.0, 2.0]), 1.0, 1, 0) is False
    assert decide_mu(_ts([5.0] * 40), 1.0, 1, 0) is False


def test_run_full_can_now_fit_a_mean(tmp_path):
    """The blocker the bug report names: before the fix this was always False."""
    from art.pipeline import run_full
    ts = _ts(_drifting(n=120))
    res = run_full(ts, str(tmp_path / "drift.inp"), max_rounds=1,
                   decision_policy=ClaudePolicy(estimate_mu=True, lam=1.0, d=1, D=0))
    assert res.estimate_mu is True
    assert bool(getattr(res.final_model, "estimate_mu", False)) is True


# ── the regression the bug report asks for ─────────────────────────────────
#
# "That single table is both the repro and the test -- it has a known answer on
# both sides of the rule." Eight monthly CPI indices, 2002-01…2019-12, fitted
# with a free mean in the report: seven significant at |t| > 5, and IPC_JP at
# t = 1.05, which is the control. A rule that only ever said True would pass
# seven of these; Japan is what makes it a test.
#
# The data are the analyst's, not the repository's, so the test skips when the
# workbook is absent -- as test_meg_hybrid_chile does for the thesis cases.

_IPC = os.path.expanduser("~/Dropbox/Nivel de Precios y Energia/IPC.xlsx")

# series -> should mu be estimated (from the fitted |t| in BUG-0013)
_EXPECTED = {"IPC_UK": True, "IPC_FR": True, "IPC_CA": True, "EMU": True,
             "IPC_DE": True, "CPI_USA": True, "IPC_ES": True,
             "IPC_JP": False}   # t = 1.05: the control


@pytest.mark.skipif(not os.path.exists(_IPC), reason="IPC.xlsx not present")
@pytest.mark.parametrize("series,expected", sorted(_EXPECTED.items()))
def test_decide_mu_reproduces_the_reported_table(series, expected):
    import pandas as pd
    df = pd.read_excel(_IPC)
    df["FECHA"] = pd.to_datetime(df["FECHA"])
    df = df[(df.FECHA >= "2002-01-01") & (df.FECHA <= "2019-12-31")]
    y = df[series].dropna().to_numpy(float)
    assert len(y) == 216
    # The report's spec: lambda = 0 (logs), d = 1, D = 0.
    assert decide_mu(_ts(y, name=series), lam=0.0, d=1, D=0) is expected
