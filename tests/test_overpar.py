"""Tests for Bloque I — over-parametrization detection via parameter correlation."""
import math
import pytest
import numpy as np
import fue
from art.diagnosis import diagnose, _build_param_labels, _compute_param_corr, DiagnosisResult
from art.describe import describe_diagnosis


# ---------------------------------------------------------------------------
# Model builders
# ---------------------------------------------------------------------------

def _make_arma_model(ar_val: float = 0.5, ma_val: float = -0.3, n: int = 120):
    """ARIMA(1,1,1) model — AR and MA often collinear when both near mid-range."""
    rng = np.random.default_rng(55)
    ts  = fue.TimeSeries(data=np.cumsum(rng.normal(0, 1, n)).tolist(),
                         freq=12, start=[2000, 1], name="ARMA")
    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[[ar_val]], ar_free=[[True]],
                  ma=[[ma_val]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=[],
                  ifadf=[0] * 7, mu=0.0, estimate_mu=False)
    m.fit()
    return m


def _make_ma_only_model(n: int = 60):
    """ARIMA(0,1,1) — single MA(1) parameter, no correlations possible."""
    rng = np.random.default_rng(99)
    ts  = fue.TimeSeries(data=np.cumsum(rng.normal(0, 1, n)).tolist(),
                         freq=12, start=[2000, 1], name="MA1")
    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=[],
                  ifadf=[0] * 7, mu=0.0, estimate_mu=False)
    m.fit()
    return m


def _make_harmonic_arma_model(n: int = 144):
    """Model with cos(k=1)/sin(k=1) + MA(1) — labels from multiple param types."""
    rng  = np.random.default_rng(42)
    freq = 12
    t    = np.arange(n)
    y    = (0.3 * np.cos(2 * math.pi / freq * t)
            + 0.2 * np.sin(2 * math.pi / freq * t)
            + np.cumsum(rng.normal(0, 0.05, n)))
    ts   = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1], name="HARM")
    itvs = [
        fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=1.0),
        fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=1.0),
    ]
    m = fue.Model(ts, d=1, D=0, boxlam=1.0,
                  ar=[], ar_free=[], ma=[[-0.3]], ma_free=[[True]],
                  ar_s=[], ma_s=[], interventions=itvs,
                  ifadf=[0] * 7, mu=0.0, estimate_mu=False)
    m.fit()
    return m


# ---------------------------------------------------------------------------
# _build_param_labels
# ---------------------------------------------------------------------------

class TestBuildParamLabels:
    def test_ma_only(self):
        m = _make_ma_only_model()
        labels = _build_param_labels(m)
        assert labels == ["MA(1)"]

    def test_arma(self):
        m = _make_arma_model()
        labels = _build_param_labels(m)
        assert labels == ["AR(1)", "MA(1)"]

    def test_harmonic_plus_ma(self):
        m = _make_harmonic_arma_model()
        labels = _build_param_labels(m)
        assert labels == ["cos(k=1)", "sin(k=1)", "MA(1)"]

    def test_length_matches_params(self):
        for m in [_make_ma_only_model(), _make_arma_model(), _make_harmonic_arma_model()]:
            labels = _build_param_labels(m)
            assert len(labels) == len(m.params)

    def test_alter_label(self):
        rng = np.random.default_rng(7)
        n, freq = 120, 12
        t = np.arange(n)
        y = 0.25 * ((-1.0) ** t) + np.cumsum(rng.normal(0, 0.05, n))
        ts = fue.TimeSeries(data=y.tolist(), freq=freq, start=[2000, 1])
        itvs = [fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True])]
        m = fue.Model(ts, d=1, D=0, boxlam=1.0, ar=[], ar_free=[],
                      ma=[[-0.3]], ma_free=[[True]], ar_s=[], ma_s=[],
                      interventions=itvs, ifadf=[0] * 7, mu=0.0, estimate_mu=False)
        m.fit()
        labels = _build_param_labels(m)
        assert "alter" in labels
        assert "MA(1)" in labels


# ---------------------------------------------------------------------------
# _compute_param_corr
# ---------------------------------------------------------------------------

class TestComputeParamCorr:
    def test_single_param_returns_none(self):
        m = _make_ma_only_model()
        corr, pairs, labels = _compute_param_corr(m)
        assert corr is None
        assert pairs == []

    def test_returns_symmetric_matrix(self):
        m = _make_arma_model()
        corr, pairs, labels = _compute_param_corr(m)
        assert corr is not None
        assert corr.shape == (2, 2)
        assert abs(corr[0, 1] - corr[1, 0]) < 1e-12

    def test_diagonal_is_one(self):
        m = _make_arma_model()
        corr, _, _ = _compute_param_corr(m)
        assert corr is not None
        np.testing.assert_allclose(np.diag(corr), 1.0, atol=1e-10)

    def test_labels_match_matrix_dim(self):
        m = _make_harmonic_arma_model()
        corr, pairs, labels = _compute_param_corr(m)
        if corr is not None:
            assert len(labels) == corr.shape[0]

    def test_custom_threshold(self):
        m = _make_arma_model()
        _, pairs_strict, _ = _compute_param_corr(m, threshold=0.99)
        _, pairs_loose,  _ = _compute_param_corr(m, threshold=0.10)
        # With threshold=0.99 we may get 0 or 1 pair; with 0.10 we should get more
        assert len(pairs_strict) <= len(pairs_loose)

    def test_pair_fields(self):
        m = _make_arma_model()
        _, pairs, labels = _compute_param_corr(m, threshold=0.0)
        assert len(pairs) == 1  # only (0,1) pair for 2×2
        i, j, r, lbl_i, lbl_j = pairs[0]
        assert i == 0 and j == 1
        assert isinstance(r, float)
        assert lbl_i == "AR(1)" and lbl_j == "MA(1)"

    def test_unfitted_returns_none(self):
        rng = np.random.default_rng(0)
        ts  = fue.TimeSeries(data=np.cumsum(rng.normal(size=60)).tolist(),
                             freq=12, start=[2000, 1])
        m = fue.Model(ts, d=1, D=0, boxlam=1.0, ar=[], ar_free=[],
                      ma=[[-0.3]], ma_free=[[True]], ar_s=[], ma_s=[],
                      interventions=[], ifadf=[0]*7, mu=0.0, estimate_mu=False)
        corr, pairs, labels = _compute_param_corr(m)
        assert corr is None


# ---------------------------------------------------------------------------
# diagnose() integration
# ---------------------------------------------------------------------------

class TestDiagnoseIntegration:
    def test_high_corr_pairs_field_present(self):
        m = _make_arma_model()
        result = diagnose(m)
        assert hasattr(result, "high_corr_pairs")
        assert result.high_corr_pairs is not None

    def test_param_labels_field_present(self):
        m = _make_arma_model()
        result = diagnose(m)
        assert result.param_labels is not None
        assert "AR(1)" in result.param_labels
        assert "MA(1)" in result.param_labels

    def test_param_corr_field_present(self):
        m = _make_arma_model()
        result = diagnose(m)
        assert result.param_corr is not None

    def test_single_param_no_pairs(self):
        m = _make_ma_only_model()
        result = diagnose(m)
        assert result.high_corr_pairs == []
        assert result.param_corr is None

    def test_high_corr_pairs_are_sorted(self):
        """Pairs must have i < j."""
        m = _make_arma_model()
        result = diagnose(m)
        for i, j, *_ in (result.high_corr_pairs or []):
            assert i < j


# ---------------------------------------------------------------------------
# describe_diagnosis integration
# ---------------------------------------------------------------------------

class TestDescribeDiagnosisOverpar:
    def test_returns_description(self):
        m = _make_arma_model()
        d = describe_diagnosis(m)
        assert d is not None

    def test_high_corr_warning_in_summary_when_detected(self):
        """When AR(1)+MA(1) are highly collinear, warning appears in summary."""
        m = _make_arma_model()
        result = diagnose(m)
        d = describe_diagnosis(m)
        if result.high_corr_pairs:
            assert "sobreparametrización" in d.summary.lower() or "corr(" in d.summary

    def test_data_has_high_corr_pairs(self):
        m = _make_arma_model()
        d = describe_diagnosis(m)
        assert "high_corr_pairs" in d.data
        assert isinstance(d.data["high_corr_pairs"], list)

    def test_data_has_param_labels(self):
        m = _make_arma_model()
        d = describe_diagnosis(m)
        assert "param_labels" in d.data
        assert isinstance(d.data["param_labels"], list)

    def test_no_overpar_warning_for_single_param(self):
        m = _make_ma_only_model()
        d = describe_diagnosis(m)
        assert d.data["high_corr_pairs"] == []
        assert "sobreparametrización" not in d.summary.lower()
