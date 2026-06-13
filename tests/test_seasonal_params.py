"""Tests for describe_seasonal_params (Bloque G)."""
import math
import pytest
import numpy as np
import fue
from art.describe import describe_seasonal_params, Description


# ---------------------------------------------------------------------------
# Synthetic model helpers
# ---------------------------------------------------------------------------

def _make_harmonic_model(n_harmonics: int = 2, freq: int = 12):
    """Build and fit a monthly model with n_harmonics cos+sin pairs + MA(1)."""
    rng = np.random.default_rng(42)
    n = 144
    t = np.arange(n)
    truth_cos = [0.30, -0.15, 0.10][:n_harmonics]
    truth_sin = [0.20,  0.08, -0.05][:n_harmonics]
    y = np.zeros(n)
    for k, (c, s) in enumerate(zip(truth_cos, truth_sin), start=1):
        omega = 2 * math.pi * k / freq
        y += c * np.cos(omega * t) + s * np.sin(omega * t)
    # Add I(1) noise with MA(1)
    noise = rng.normal(0, 0.05, n)
    for i in range(1, n):
        noise[i] += noise[i - 1] - 0.4 * rng.normal(0, 0.05)
    y += np.cumsum(rng.normal(0, 0.02, n))

    ts = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1], name="TEST")

    itvs = []
    for k in range(1, n_harmonics + 1):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
    itvs.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))

    m = fue.Model(
        ts, d=1, D=0, boxlam=1.0,
        ar=[], ar_free=[],
        ma=[[-0.3]], ma_free=[[True]],
        ar_s=[], ma_s=[],
        interventions=itvs,
        ifadf=[0] * (freq // 2 + 1),
        mu=0.0, estimate_mu=False,
    )
    m.fit()
    return m


def _make_alter_only_model(freq: int = 12):
    """Model with only an 'alter' (Nyquist) intervention."""
    rng = np.random.default_rng(7)
    n = 120
    t = np.arange(n)
    y = 0.25 * ((-1.0) ** t) + np.cumsum(rng.normal(0, 0.05, n))

    ts = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1], name="ALTER_TEST")
    itvs = [fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True])]

    m = fue.Model(
        ts, d=1, D=0, boxlam=1.0,
        ar=[], ar_free=[],
        ma=[[-0.3]], ma_free=[[True]],
        ar_s=[], ma_s=[],
        interventions=itvs,
        ifadf=[0] * (freq // 2 + 1),
        mu=0.0, estimate_mu=False,
    )
    m.fit()
    return m


def _make_arma_no_harmonics():
    """Plain ARIMA(0,1,1) model with no harmonic interventions."""
    rng = np.random.default_rng(99)
    n = 60
    ts = fue.TimeSeries(data=np.cumsum(rng.normal(0, 1, n)).tolist(),
                        freq=12, start=[2000, 1], name="NO_HARM")
    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=[],
                  ifadf=[0] * 7, mu=0.0, estimate_mu=False)
    m.fit()
    return m


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class TestDescribeSeasonalParamsAPI:
    def test_returns_description(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert isinstance(result, Description)

    def test_has_figure(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert result.figure_b64 is not None
        assert len(result.figure_b64) > 100

    def test_summary_has_table(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert "k=" in result.summary or "cos_k" in result.summary

    def test_raises_if_not_fitted(self):
        rng = np.random.default_rng(0)
        ts = fue.TimeSeries(data=np.cumsum(rng.normal(size=60)).tolist(),
                            freq=12, start=[2000, 1])
        itvs = [fue.Intervention("cos", at=0, omega=[0.1], omega_free=[True], harmonic=1.0)]
        m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                      ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                      ar_s=[], ma_s=[], interventions=itvs,
                      ifadf=[0] * 7, mu=0.0, estimate_mu=False)
        with pytest.raises(RuntimeError, match="not been fitted"):
            describe_seasonal_params(m)

    def test_no_harmonics_returns_empty(self):
        m = _make_arma_no_harmonics()
        result = describe_seasonal_params(m)
        assert result.figure_b64 is None
        assert "No hay parámetros" in result.summary


# ---------------------------------------------------------------------------
# Data content tests
# ---------------------------------------------------------------------------

class TestDescribeSeasonalParamsContent:
    def test_data_has_correct_keys(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert "freq" in result.data
        assert "harmonics" in result.data
        assert result.data["freq"] == 12

    def test_data_harmonics_count(self):
        """2 harmonics + alter → 3 entries in harmonics list."""
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert len(result.data["harmonics"]) == 3  # k=1, k=2, k=6 (alter)

    def test_harmonics_have_cos_and_sin(self):
        m = _make_harmonic_model(n_harmonics=1)
        result = describe_seasonal_params(m)
        h1 = next(x for x in result.data["harmonics"] if x["k"] == 1)
        assert h1["cos_v"] is not None
        assert h1["sin_v"] is not None
        assert isinstance(h1["A_k"], float)

    def test_amplitude_nonnegative(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        for h in result.data["harmonics"]:
            assert h["A_k"] >= 0.0

    def test_alter_maps_to_nyquist(self):
        m = _make_alter_only_model()
        result = describe_seasonal_params(m)
        nyquist = 12 // 2
        ks = [h["k"] for h in result.data["harmonics"]]
        assert nyquist in ks

    def test_alter_has_cos_only(self):
        """alter intervention has cos component but no sin."""
        m = _make_alter_only_model()
        result = describe_seasonal_params(m)
        nyquist = 12 // 2
        h = next(x for x in result.data["harmonics"] if x["k"] == nyquist)
        assert h["cos_v"] is not None
        assert h["sin_v"] is None

    def test_significant_and_droppable_lists_partition_k(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        sig = set(result.data["significant_k"])
        drop = set(result.data["droppable_k"])
        all_k = {h["k"] for h in result.data["harmonics"]}
        assert sig | drop == all_k
        assert sig & drop == set()

    def test_recommendation_present(self):
        m = _make_harmonic_model(n_harmonics=2)
        result = describe_seasonal_params(m)
        assert len(result.recommendation) > 0


# ---------------------------------------------------------------------------
# MCP tool smoke test
# ---------------------------------------------------------------------------

def test_seasonal_param_analysis_mcp_missing_file():
    """MCP tool returns an error TextContent when file does not exist."""
    from art.mcp_server import seasonal_param_analysis

    result = seasonal_param_analysis("/nonexistent/path/model.inp")
    assert len(result) >= 1
    assert hasattr(result[0], "text")
    # _err() wraps with "❌ Error:"
    assert "Error" in result[0].text or "error" in result[0].text.lower()
