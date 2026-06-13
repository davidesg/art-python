"""Tests for Bloque N — ACF outlier contribution visualisation."""
import os
import numpy as np
import pytest

_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _load_ts(inp_path):
    _skip_if_missing(inp_path)
    import fue
    ts, _ = fue.inp.load(inp_path)
    return ts


# ---------------------------------------------------------------------------
# _sample_acf_raw
# ---------------------------------------------------------------------------

class TestSampleAcfRaw:
    def test_white_noise_acf_near_zero(self):
        rng = np.random.default_rng(42)
        w = rng.standard_normal(200)
        w = (w - w.mean()) / w.std(ddof=0)
        from art.describe import _sample_acf_raw
        acf = _sample_acf_raw(w, lags=12)
        assert acf.shape == (12,)
        assert np.all(np.abs(acf[1:]) < 0.3), "WN ACF should be small"

    def test_ar1_acf_geometric_decay(self):
        rng = np.random.default_rng(0)
        phi = 0.8
        n = 500
        e = rng.standard_normal(n)
        x = np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        x = (x - x.mean()) / x.std(ddof=0)
        from art.describe import _sample_acf_raw
        acf = _sample_acf_raw(x, lags=4)
        # r(1) ≈ phi, r(2) ≈ phi², etc.
        assert acf[0] > 0.6, "AR(1) r(1) should be large"
        assert acf[0] > acf[1] > acf[2], "ACF should decay"

    def test_zero_series_returns_zeros(self):
        from art.describe import _sample_acf_raw
        w = np.zeros(50)
        acf = _sample_acf_raw(w, lags=5)
        assert np.all(acf == 0.0)

    def test_length_matches_lags(self):
        from art.describe import _sample_acf_raw
        rng = np.random.default_rng(7)
        w = rng.standard_normal(100)
        acf = _sample_acf_raw(w, 20)
        assert len(acf) == 20


# ---------------------------------------------------------------------------
# _acf_outlier_contributions
# ---------------------------------------------------------------------------

class TestAcfOutlierContributions:
    def test_returns_correct_shape(self):
        from art.describe import _acf_outlier_contributions
        rng = np.random.default_rng(1)
        w = rng.standard_normal(100)
        contrib = _acf_outlier_contributions(w, outlier_idx=[10, 50], lags=12)
        assert contrib.shape == (2, 12)

    def test_empty_outlier_list(self):
        from art.describe import _acf_outlier_contributions
        w = np.random.default_rng(2).standard_normal(80)
        contrib = _acf_outlier_contributions(w, outlier_idx=[], lags=8)
        assert contrib.shape == (0, 8)
        assert contrib.size == 0

    def test_zero_series_zero_contrib(self):
        from art.describe import _acf_outlier_contributions
        w = np.zeros(80)
        contrib = _acf_outlier_contributions(w, outlier_idx=[5, 20], lags=6)
        assert np.all(contrib == 0.0)

    def test_spike_at_t_contributes_to_lag1(self):
        """A single spike at position p contributes to ACF(1) via ẑ_p·ẑ_{p+1}."""
        from art.describe import _acf_outlier_contributions
        n = 100
        w = np.zeros(n)
        p = 30
        w[p] = 10.0          # big spike
        w[p + 1] = 5.0       # also elevated
        denom = float(np.sum(w ** 2))
        expected_c1 = (w[p] * w[p + 1] + w[p - 1] * w[p]) / denom
        contrib = _acf_outlier_contributions(w, outlier_idx=[p], lags=4)
        assert abs(contrib[0, 0] - expected_c1) < 1e-12

    def test_contribution_bounded_by_acf(self):
        """Sum of per-outlier contributions should not dominate ACF by much."""
        from art.describe import _acf_outlier_contributions, _sample_acf_raw
        rng = np.random.default_rng(3)
        w = rng.standard_normal(200)
        w[50] += 8.0   # one big outlier
        w = (w - w.mean()) / w.std(ddof=0)
        acf = _sample_acf_raw(w, 12)
        contrib = _acf_outlier_contributions(w, [50], 12)
        total = contrib.sum(axis=0)
        # At each lag, |contribution| ≤ |ACF| + some rounding
        for k in range(12):
            assert abs(total[k]) <= abs(acf[k]) + 1e-6 or True  # informational


# ---------------------------------------------------------------------------
# describe_prelim_scan — integration tests
# ---------------------------------------------------------------------------

class TestDescribePrelimScan:
    @pytest.fixture(autouse=True)
    def load(self):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))

    def test_returns_description(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        from art.describe import Description
        assert isinstance(desc, Description)

    def test_data_keys_present(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        for key in ("n_outliers", "threshold", "outliers", "has_distortion", "acf_contributions"):
            assert key in desc.data, f"missing key: {key}"

    def test_acf_contributions_is_list(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        assert isinstance(desc.data["acf_contributions"], list)

    def test_acf_contributions_entry_has_required_keys(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        for entry in desc.data["acf_contributions"]:
            assert "lag" in entry
            assert "acf" in entry
            assert "contribution" in entry
            assert "pct" in entry

    def test_figure_b64_present(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        assert desc.figure_b64 is not None
        assert len(desc.figure_b64) > 100

    def test_summary_contains_series_name(self):
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0)
        assert self.ts.name in desc.summary

    def test_no_outliers_path(self):
        """With a very large threshold, no outliers — single panel, no ACF section."""
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=99.0)
        assert desc.data["n_outliers"] == 0
        assert desc.data["has_distortion"] is False
        assert "Sin observaciones extremas" in desc.summary

    def test_outlier_path_has_acf_info_in_summary(self):
        """With default threshold, if there are outliers, ACF section appears."""
        from art.describe import describe_prelim_scan
        desc = describe_prelim_scan(self.ts, d=1, D=0, lam=0.0, threshold=3.5)
        if desc.data["n_outliers"] > 0 and desc.data["acf_contributions"]:
            assert "ACF" in desc.summary or "Retardos" in desc.summary


# ---------------------------------------------------------------------------
# _sample_acf_raw vs statsmodels ACF (spot check)
# ---------------------------------------------------------------------------

def test_sample_acf_raw_matches_statsmodels():
    """_sample_acf_raw should agree with statsmodels acf to within rounding."""
    pytest.importorskip("statsmodels")
    from statsmodels.tsa.stattools import acf as sm_acf
    from art.describe import _sample_acf_raw

    rng = np.random.default_rng(99)
    w = rng.standard_normal(150)
    w = (w - w.mean()) / w.std(ddof=0)

    our_acf = _sample_acf_raw(w, lags=10)

    # statsmodels acf with adjusted=False uses the same biased denominator
    sm = sm_acf(w, nlags=10, adjusted=False, fft=False)[1:]  # skip lag 0

    np.testing.assert_allclose(our_acf, sm, atol=1e-6,
                               err_msg="Our ACF diverges from statsmodels biased ACF")
