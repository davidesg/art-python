"""Tests for Bloque L — unit_root_tests and describe_unit_root."""
import os
import pytest
import numpy as np
import fue
from art.identification import unit_root_tests, recommended_d, UnitRootResult

_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD  = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")
_IPC_TRIM = os.path.join(_FUE_TESTS, "IPC/Trimestral/Sample_1.2003_4.2019/Mod")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _load_ts(inp_path):
    _skip_if_missing(inp_path)
    ts, _ = fue.inp.load(inp_path)
    return ts


# ---------------------------------------------------------------------------
# UnitRootResult dataclass
# ---------------------------------------------------------------------------

def test_verdict_stationary():
    r = UnitRootResult(
        d=1, label="∇ln P", n=67,
        adf_stat=-5.0, adf_pvalue=0.001, adf_rejects=True,
        kpss_stat=0.10, kpss_pvalue=0.50, kpss_rejects=False,
        verdict="stationary",
    )
    assert r.verdict == "stationary"
    assert r.adf_rejects
    assert not r.kpss_rejects


def test_verdict_unit_root():
    r = UnitRootResult(
        d=0, label="ln P", n=68,
        adf_stat=-1.2, adf_pvalue=0.68, adf_rejects=False,
        kpss_stat=1.5, kpss_pvalue=0.01, kpss_rejects=True,
        verdict="unit_root",
    )
    assert r.verdict == "unit_root"


# ---------------------------------------------------------------------------
# recommended_d helper
# ---------------------------------------------------------------------------

def test_recommended_d_first_stationary():
    results = [
        UnitRootResult(0, "ln P", 68, -1.0, 0.7, False, 1.5, 0.01, True, "unit_root"),
        UnitRootResult(1, "∇ln P", 67, -5.0, 0.00, True, 0.1, 0.5, False, "stationary"),
        UnitRootResult(2, "∇²ln P", 66, -8.0, 0.00, True, 0.05, 0.7, False, "stationary"),
    ]
    assert recommended_d(results) == 1


def test_recommended_d_no_stationary():
    """If no level is stationary, returns last d tested."""
    results = [
        UnitRootResult(0, "y", 30, -1.0, 0.7, False, 1.5, 0.01, True, "unit_root"),
        UnitRootResult(1, "∇y", 29, -2.0, 0.08, False, 0.4, 0.04, True, "ambiguous"),
    ]
    assert recommended_d(results) == 1


def test_recommended_d_empty():
    assert recommended_d([]) == 0


def test_recommended_d_d0_stationary():
    results = [
        UnitRootResult(0, "ln P", 68, -5.0, 0.001, True, 0.1, 0.5, False, "stationary"),
    ]
    assert recommended_d(results) == 0


# ---------------------------------------------------------------------------
# unit_root_tests — PCE quarterly (n=68, s=4)
# ---------------------------------------------------------------------------

class TestPCE_UnitRoot:
    @pytest.fixture(autouse=True)
    def load(self):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))

    def test_returns_list(self):
        results = unit_root_tests(self.ts, lam=0.0, max_d=2)
        assert isinstance(results, list)
        assert len(results) == 3

    def test_d_values(self):
        results = unit_root_tests(self.ts, lam=0.0, max_d=2)
        assert [r.d for r in results] == [0, 1, 2]

    def test_n_shrinks(self):
        results = unit_root_tests(self.ts, lam=0.0, max_d=2)
        n0 = results[0].n
        assert results[1].n == n0 - 1
        assert results[2].n == n0 - 2

    def test_adf_stat_is_float(self):
        results = unit_root_tests(self.ts, lam=0.0)
        for r in results:
            assert isinstance(r.adf_stat, float)
            assert isinstance(r.kpss_stat, float)

    def test_pvalues_in_range(self):
        results = unit_root_tests(self.ts, lam=0.0)
        for r in results:
            assert 0.0 <= r.adf_pvalue <= 1.0
            assert 0.0 <= r.kpss_pvalue <= 1.0

    def test_verdict_is_valid(self):
        results = unit_root_tests(self.ts, lam=0.0)
        for r in results:
            assert r.verdict in ("stationary", "unit_root", "ambiguous")

    def test_d0_likely_unit_root(self):
        """PCE in log levels should not be stationary (typical economic series)."""
        results = unit_root_tests(self.ts, lam=0.0)
        d0 = results[0]
        # ADF likely fails to reject unit root at d=0
        assert d0.verdict in ("unit_root", "ambiguous")

    def test_d1_likely_stationary(self):
        """First-differenced log PCE should be stationary."""
        results = unit_root_tests(self.ts, lam=0.0)
        d1 = results[1]
        assert d1.verdict in ("stationary", "ambiguous")

    def test_label_contains_d(self):
        results = unit_root_tests(self.ts, lam=0.0)
        assert "ln" in results[0].label or "P" in results[0].label
        assert "∇" in results[1].label

    def test_max_d_zero(self):
        results = unit_root_tests(self.ts, lam=0.0, max_d=0)
        assert len(results) == 1
        assert results[0].d == 0

    def test_lam_one_no_transform(self):
        """With lam=1 the series is untransformed."""
        results = unit_root_tests(self.ts, lam=1.0)
        assert len(results) == 3

    def test_recommended_d_for_pce(self):
        results = unit_root_tests(self.ts, lam=0.0)
        rec = recommended_d(results)
        assert 0 <= rec <= 2


# ---------------------------------------------------------------------------
# describe_unit_root — output structure
# ---------------------------------------------------------------------------

class TestDescribeUnitRoot:
    @pytest.fixture(autouse=True)
    def load(self):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))

    def test_returns_description(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0)
        assert desc.summary
        assert desc.recommendation
        assert isinstance(desc.data, dict)

    def test_summary_has_table(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0)
        assert "ADF" in desc.summary
        assert "KPSS" in desc.summary
        assert "| d |" in desc.summary

    def test_figure_generated(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0)
        assert desc.figure_b64 is not None
        assert len(desc.figure_b64) > 100

    def test_data_has_recommended_d(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0)
        assert "recommended_d" in desc.data
        assert isinstance(desc.data["recommended_d"], int)

    def test_data_results_length(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0, max_d=2)
        assert len(desc.data["results"]) == 3

    def test_data_results_fields(self):
        from art.describe import describe_unit_root
        desc = describe_unit_root(self.ts, lam=0.0)
        r = desc.data["results"][0]
        for key in ("d", "label", "n", "adf_stat", "adf_pvalue", "adf_rejects",
                    "kpss_stat", "kpss_pvalue", "kpss_rejects", "verdict"):
            assert key in r, f"missing key: {key}"

    def test_mcp_error_path(self):
        """MCP tool returns error content on bad path."""
        from art.mcp_server import unit_root_analysis
        result = unit_root_analysis("/nonexistent/path.inp")
        assert len(result) == 1
        assert "error" in result[0].text.lower() or "Error" in result[0].text
