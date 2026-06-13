"""Tests for seasonal_simplification_test (Bloque H)."""
import math
import pytest
import numpy as np
import fue
from art.formal_tests import seasonal_simplification_test, SeasonalSimplificationResult
from art.describe import describe_seasonal_simplification, Description


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

def _make_model_with_harmonics(n_harmonics: int = 3, freq: int = 12,
                                signal_k1: float = 0.30):
    """Monthly model with n_harmonics cos+sin + alter + MA(1).
    k=1 has a real signal (signal_k1); higher k are near-zero noise.
    """
    rng = np.random.default_rng(17)
    n   = 168
    t   = np.arange(n)
    y   = signal_k1 * np.cos(2 * math.pi / freq * t)   # only k=1 signal
    y  += np.cumsum(rng.normal(0, 0.03, n))

    ts = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1], name="SIM")

    itvs = []
    for k in range(1, n_harmonics + 1):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
    itvs.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))

    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=itvs,
                  ifadf=[0] * (freq // 2 + 1), mu=0.0, estimate_mu=False)
    m.fit()
    return m


def _make_alter_only_model(freq: int = 12):
    """Model with only an alter (Nyquist) intervention."""
    rng = np.random.default_rng(7)
    n   = 120
    t   = np.arange(n)
    y   = 0.25 * ((-1.0) ** t) + np.cumsum(rng.normal(0, 0.05, n))
    ts  = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1], name="ALT")
    itvs = [fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True])]
    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=itvs,
                  ifadf=[0] * (freq // 2 + 1), mu=0.0, estimate_mu=False)
    m.fit()
    return m


# ---------------------------------------------------------------------------
# formal_tests.seasonal_simplification_test — API tests
# ---------------------------------------------------------------------------

class TestSeasonalSimplificationAPI:
    def test_returns_result(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m)
        assert isinstance(r, SeasonalSimplificationResult)

    def test_raises_if_not_fitted(self):
        rng = np.random.default_rng(0)
        ts  = fue.TimeSeries(data=np.cumsum(rng.normal(size=60)).tolist(),
                             freq=12, start=[2000, 1])
        itvs = [fue.Intervention("cos", at=0, omega=[0.1], omega_free=[True], harmonic=1.0)]
        m = fue.Model(ts, d=1, D=0, boxlam=1.0, ar=[], ar_free=[],
                      ma=[[-0.3]], ma_free=[[True]], ar_s=[], ma_s=[],
                      interventions=itvs, ifadf=[0] * 7, mu=0.0, estimate_mu=False)
        with pytest.raises(RuntimeError, match="not been fitted"):
            seasonal_simplification_test(m)

    def test_raises_if_no_harmonics(self):
        rng = np.random.default_rng(0)
        ts  = fue.TimeSeries(data=np.cumsum(rng.normal(size=60)).tolist(),
                             freq=12, start=[2000, 1])
        m = fue.Model(ts, d=1, D=0, boxlam=1.0, ar=[], ar_free=[],
                      ma=[[-0.3]], ma_free=[[True]], ar_s=[], ma_s=[],
                      interventions=[], ifadf=[0] * 7, mu=0.0, estimate_mu=False)
        m.fit()
        with pytest.raises(ValueError, match="No free harmonic"):
            seasonal_simplification_test(m)

    def test_raises_for_unknown_freq(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        with pytest.raises(ValueError, match="not found in model"):
            seasonal_simplification_test(m, freq_list=[99])

    def test_default_tests_all_harmonics(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m)
        # 2 harmonics + alter = k=1,2,6 → df = 2+2+1 = 5
        assert r.df == 5
        assert sorted(r.harmonics_tested) == sorted({1, 2, 6})

    def test_explicit_freq_list(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m, freq_list=[2])
        assert r.harmonics_tested == [2]
        assert r.df == 2  # cos_2 + sin_2

    def test_alter_has_df_one(self):
        m = _make_alter_only_model()
        r = seasonal_simplification_test(m)
        assert r.df == 1  # only alter (cos), no sin


# ---------------------------------------------------------------------------
# formal_tests.seasonal_simplification_test — numeric content
# ---------------------------------------------------------------------------

class TestSeasonalSimplificationContent:
    def test_lr_nonnegative(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m)
        assert r.lr >= 0.0

    def test_pvalue_in_unit_interval(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m)
        assert 0.0 <= r.pvalue <= 1.0

    def test_loglik_free_ge_constrained(self):
        """Unrestricted model must have logL ≥ restricted model (ML property)."""
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m)
        assert r.loglik_free >= r.loglik_constrained - 1e-6

    def test_significant_harmonic_rejects(self):
        """k=1 has a real signal → testing k=1 alone should reject H₀."""
        m = _make_model_with_harmonics(n_harmonics=1, signal_k1=0.50)
        r = seasonal_simplification_test(m, freq_list=[1])
        assert r.rejects, f"Expected rejection: LR={r.lr:.3f}, p={r.pvalue:.4f}"

    def test_noise_only_harmonic_does_not_reject(self):
        """k=2,3 carry no signal → testing them alone should not reject H₀."""
        m = _make_model_with_harmonics(n_harmonics=3, signal_k1=0.0)
        r = seasonal_simplification_test(m, freq_list=[2, 3])
        # With no true signal at any k, p-value should be large
        # (not strictly guaranteed but very likely with n=168)
        assert r.pvalue > 0.01, f"Unexpected rejection: LR={r.lr:.3f}, p={r.pvalue:.4f}"

    def test_components_dict(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        r = seasonal_simplification_test(m, freq_list=[1, 2])
        assert 1 in r.components and 2 in r.components
        assert "cos" in r.components[1] and "sin" in r.components[1]

    def test_summary_contains_lr(self):
        m = _make_model_with_harmonics(n_harmonics=1)
        r = seasonal_simplification_test(m)
        s = r.summary()
        assert "LR" in s
        assert "p-value" in s

    def test_alpha_propagated(self):
        m = _make_model_with_harmonics(n_harmonics=1)
        r = seasonal_simplification_test(m, alpha=0.10)
        assert r.alpha == 0.10


# ---------------------------------------------------------------------------
# describe.describe_seasonal_simplification
# ---------------------------------------------------------------------------

class TestDescribeSeasonalSimplification:
    def test_returns_description(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m)
        assert isinstance(d, Description)

    def test_no_figure(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m)
        assert d.figure_b64 is None

    def test_summary_has_table(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m)
        assert "LR" in d.summary
        assert "p-value" in d.summary

    def test_data_keys(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m)
        for key in ("harmonics_tested", "df", "lr", "pvalue", "rejects"):
            assert key in d.data

    def test_recommendation_present(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m)
        assert len(d.recommendation) > 10

    def test_explicit_freq_list(self):
        m = _make_model_with_harmonics(n_harmonics=2)
        d = describe_seasonal_simplification(m, freq_list=[2])
        assert "k=2" in d.summary


# ---------------------------------------------------------------------------
# MCP tool smoke test
# ---------------------------------------------------------------------------

def test_test_seasonal_simplification_mcp_missing_file():
    """MCP tool returns an error when file does not exist."""
    from art.mcp_server import test_seasonal_simplification

    result = test_seasonal_simplification("/nonexistent/path.inp")
    assert len(result) >= 1
    assert hasattr(result[0], "text")
    assert "Error" in result[0].text or "error" in result[0].text.lower()
