"""Tests for Bloque M — multiplicative seasonality (D=1) support."""
import os
import pytest
import fue

_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _load_ts(inp_path):
    _skip_if_missing(inp_path)
    ts, _ = fue.inp.load(inp_path)
    return ts


def _build_inp(ts, lam, d, D, p, q, n_harmonics, output_path, P=0, Q=0):
    """Test shim: _build_inp was replaced by _make_model + _write_inp."""
    from art.mcp_server import _make_model, _write_inp
    m = _make_model(ts, lam, d, D, p, q, n_harmonics, P=P, Q=Q)
    _write_inp(ts, m, output_path)


# ---------------------------------------------------------------------------
# _make_model: D=0 vs D=1 structure
# ---------------------------------------------------------------------------

class TestMakeModelD0vsD1:
    """Internal helper _make_model builds correct structure for D=0 and D=1."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))

    def test_d0_has_harmonics(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=0, p=0, q=1,
                        n_harmonics=2)
        types = [itv.type for itv in (m.interventions or [])]
        assert "cos" in types
        assert "sin" in types
        assert "alter" in types

    def test_d0_no_ma_s(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=0, p=0, q=1,
                        n_harmonics=2)
        assert not m.ma_s

    def test_d1_no_harmonics(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                        n_harmonics=0, Q=1)
        types = [itv.type for itv in (m.interventions or [])]
        assert "cos" not in types
        assert "sin" not in types

    def test_d1_has_ma_s(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                        n_harmonics=0, Q=1)
        assert m.ma_s and len(m.ma_s[0]) == 1

    def test_d1_p1_has_ar_s(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                        n_harmonics=0, P=1, Q=1)
        assert m.ar_s and len(m.ar_s[0]) == 1
        assert m.ma_s and len(m.ma_s[0]) == 1

    def test_d1_zero_p_zero_q_no_seasonal_ops(self):
        from art.mcp_server import _make_model
        m = _make_model(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                        n_harmonics=0, P=0, Q=0)
        assert not m.ar_s
        assert not m.ma_s


# ---------------------------------------------------------------------------
# _build_inp: D=1 roundtrip (write + load)
# ---------------------------------------------------------------------------

class TestBuildInpD1:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
        self.out = str(tmp_path / "test_d1.inp")

    def test_d1_writes_and_loads(self):
        _build_inp(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                   n_harmonics=0, output_path=self.out, Q=1)
        assert os.path.exists(self.out)
        ts2, m2 = fue.inp.load(self.out)
        assert m2.D == 1

    def test_d1_fits_and_has_params(self):
        _build_inp(self.ts, lam=0.0, d=1, D=1, p=0, q=1,
                   n_harmonics=0, output_path=self.out, Q=1)
        ts2, m2 = fue.inp.load(self.out)
        m2.fit()
        assert m2._result is not None
        assert len(m2.params) == 2   # MA(1) + MA_S(1)

    def test_d0_writes_harmonics(self):
        _build_inp(self.ts, lam=0.0, d=1, D=0, p=0, q=1,
                   n_harmonics=2, output_path=self.out)
        ts2, m2 = fue.inp.load(self.out)
        types = [itv.type for itv in (m2.interventions or [])]
        assert "cos" in types
        assert "sin" in types


# ---------------------------------------------------------------------------
# describe_seasonality: B2 option mentioned when seasonality detected
# ---------------------------------------------------------------------------

def test_seasonality_mentions_b2():
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.describe import describe_seasonality
    desc = describe_seasonality(ts)
    # B2 option should be mentioned in summary
    assert "B2" in desc.summary or "multiplicat" in desc.summary.lower()


def test_seasonality_data_has_multiplicative_available():
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.describe import describe_seasonality
    desc = describe_seasonality(ts)
    assert "multiplicative_available" in desc.data


# ---------------------------------------------------------------------------
# describe_identification: D=1 recommendation mentions P, Q
# ---------------------------------------------------------------------------

def test_identification_d1_rec_mentions_seasonal():
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.describe import describe_identification
    desc = describe_identification(ts, d=1, D=1, lam=0.0)
    # Recommendation says "sin armónicos" (not to add them), not "añade armónicos"
    assert "sin armónicos" in desc.recommendation
    # Should mention P or Q for the seasonal spec
    assert "P=" in desc.recommendation or "Q=" in desc.recommendation or "D=1" in desc.recommendation


def test_identification_d0_rec_mentions_harmonics():
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.describe import describe_identification
    desc = describe_identification(ts, d=1, D=0, lam=0.0)
    assert "armónicos" in desc.recommendation or "n_harmonics" in desc.recommendation


# ---------------------------------------------------------------------------
# confirm_and_estimate with D=1
# ---------------------------------------------------------------------------

def test_confirm_and_estimate_d1(tmp_path):
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.mcp_server import confirm_and_estimate
    inp = os.path.join(_PCE_MOD, "R.1.inp")
    out = str(tmp_path / "ce_d1.inp")
    result = confirm_and_estimate(inp, out, lam=0.0, d=1, D=1, p=0, q=1,
                                  n_harmonics=0, Q=1)
    # Should return text + possibly a figure
    assert len(result) >= 1
    assert "SARIMA" in result[0].text or "D=1" in result[0].text


def test_confirm_and_estimate_spec_line_d1_only_ma_s(tmp_path):
    """D=1 with Q=1 (no AR_s) — SARIMA(0,1,1)(0,1,1)_s equivalent."""
    ts = _load_ts(os.path.join(_PCE_MOD, "R.1.inp"))
    from art.mcp_server import confirm_and_estimate
    inp = os.path.join(_PCE_MOD, "R.1.inp")
    out = str(tmp_path / "ce_d1_q1.inp")
    result = confirm_and_estimate(inp, out, lam=0.0, d=1, D=1, p=0, q=1,
                                  n_harmonics=0, P=0, Q=1)
    text = result[0].text
    # Spec line should show SARIMA notation with P=0, Q=1
    assert "SARIMA" in text
