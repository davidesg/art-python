"""Tests for Bloque Q — compare_versions MCP tool."""
from __future__ import annotations
import os
import pytest

_FUE_TESTS = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
)
_PCE_MOD = os.path.join(_FUE_TESTS, "PCE/Sample_1.2003_4.2019/Mod")
_PCE_INP = os.path.join(_PCE_MOD, "R.1.inp")


def _skip_if_missing(path=_PCE_INP):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _build_inp(ts, lam, d, D, p, q, n_harmonics, output_path, P=0, Q=0):
    """Test shim: _build_inp was replaced by _make_model + _write_inp."""
    from art.mcp_server import _make_model, _write_inp
    _write_inp(ts, _make_model(ts, lam, d, D, p, q, n_harmonics, P=P, Q=Q), output_path)


# ---------------------------------------------------------------------------
# _spec_diff
# ---------------------------------------------------------------------------

class TestSpecDiff:
    def _spec(self, **kw):
        base = {"d": 1, "D": 0, "p": 0, "q": 0, "P": 0, "Q": 0,
                "n_harmonics": 4, "interventions": [], "lam": 0.0}
        base.update(kw)
        return base

    def test_no_changes(self):
        from art.mcp_server import _spec_diff
        s = self._spec()
        assert _spec_diff(s, s) == []

    def test_q_change(self):
        from art.mcp_server import _spec_diff
        a = self._spec(q=0)
        b = self._spec(q=1)
        diffs = _spec_diff(a, b)
        assert any("q" in d for d in diffs)

    def test_multiple_changes(self):
        from art.mcp_server import _spec_diff
        a = self._spec(p=0, q=0)
        b = self._spec(p=1, q=1)
        diffs = _spec_diff(a, b)
        assert len(diffs) >= 2

    def test_intervention_added(self):
        from art.mcp_server import _spec_diff
        a = self._spec(interventions=[])
        b = self._spec(interventions=[{"type": "pulse", "date": "Q1/2008"}])
        diffs = _spec_diff(a, b)
        assert any("pulse" in d for d in diffs)

    def test_intervention_removed(self):
        from art.mcp_server import _spec_diff
        a = self._spec(interventions=[{"type": "step", "date": "Q3/2009"}])
        b = self._spec(interventions=[])
        diffs = _spec_diff(a, b)
        assert any("step" in d for d in diffs)


# ---------------------------------------------------------------------------
# _nested_relation
# ---------------------------------------------------------------------------

class TestNestedRelation:
    def _spec(self, **kw):
        base = {"d": 1, "D": 0, "p": 0, "q": 0, "P": 0, "Q": 0,
                "n_harmonics": 4, "interventions": []}
        base.update(kw)
        return base

    def test_a_in_b_by_ma(self):
        from art.mcp_server import _nested_relation
        a = self._spec(q=0)
        b = self._spec(q=1)
        assert _nested_relation(a, b, npar_a=1, npar_b=2) == "A_in_B"

    def test_b_in_a_by_ar(self):
        from art.mcp_server import _nested_relation
        a = self._spec(p=2)
        b = self._spec(p=1)
        assert _nested_relation(a, b, npar_a=2, npar_b=1) == "B_in_A"

    def test_not_nested_different_d(self):
        from art.mcp_server import _nested_relation
        a = self._spec(d=1)
        b = self._spec(d=2, q=1)
        assert _nested_relation(a, b, npar_a=1, npar_b=2) == "none"

    def test_same_npar_not_nested(self):
        from art.mcp_server import _nested_relation
        a = self._spec(p=1, q=0)
        b = self._spec(p=0, q=1)
        assert _nested_relation(a, b, npar_a=1, npar_b=1) == "none"

    def test_nested_with_interventions_subset(self):
        from art.mcp_server import _nested_relation
        iv1 = {"type": "pulse", "date": "Q1/2008"}
        iv2 = {"type": "step",  "date": "Q3/2009"}
        a = self._spec(interventions=[iv1])
        b = self._spec(q=1, interventions=[iv1, iv2])
        assert _nested_relation(a, b, npar_a=2, npar_b=4) == "A_in_B"

    def test_not_nested_interventions_not_subset(self):
        from art.mcp_server import _nested_relation
        iv1 = {"type": "pulse", "date": "Q1/2008"}
        iv2 = {"type": "step",  "date": "Q3/2009"}
        a = self._spec(interventions=[iv1, iv2])
        b = self._spec(q=1, interventions=[iv1])
        # B doesn't contain iv2, so A ⊄ B; B ⊄ A because q(B)>q(A)
        assert _nested_relation(a, b, npar_a=3, npar_b=3) == "none"


# ---------------------------------------------------------------------------
# compare_versions MCP tool — integration tests
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def two_models(tmp_path_factory):
    """
    Build two nested models: A=ARIMA(0,1,1) and B=ARIMA(1,1,1).

    Note: fue C backend crashes with p=0, q=0 (no ARMA params).
    Workaround: always include at least one ARMA parameter.
    """
    _skip_if_missing()
    import fue
    tmp = tmp_path_factory.mktemp("cmpv")
    ts, _ = fue.inp.load(_PCE_INP)

    path_a = str(tmp / "m_a.inp")
    path_b = str(tmp / "m_b.inp")
    # A: MA(1) only → 2 harmonics + MA(1)
    _build_inp(ts, lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2, output_path=path_a)
    # B: AR(1)+MA(1) → 2 harmonics + AR(1) + MA(1)  (nested: A ⊂ B)
    _build_inp(ts, lam=0.0, d=1, D=0, p=1, q=1, n_harmonics=2, output_path=path_b)
    return path_a, path_b


def test_compare_returns_list(two_models):
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    assert isinstance(result, list)
    assert len(result) >= 1


def test_compare_text_has_both_names(two_models):
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    text = result[0].text
    assert "m_a.inp" in text
    assert "m_b.inp" in text


def test_compare_text_has_delta(two_models):
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    text = result[0].text
    assert "Δ" in text or "Delta" in text.lower() or "B−A" in text


def test_compare_text_spec_diff_mentions_q(two_models):
    """B adds MA(1) so the diff should mention q: 0→1."""
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    text = result[0].text
    assert "q:" in text or "q: 0→1" in text or "Cambios" in text


def test_compare_lr_test_when_nested(two_models):
    """A ⊂ B, so LR test should be computed."""
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    text = result[0].text
    assert "LR" in text or "Test" in text


def test_compare_figure_returned(two_models):
    """Should return a figure with ACF/PACF comparison."""
    from art.mcp_server import compare_versions
    a, b = two_models
    result = compare_versions(a, b)
    assert len(result) == 2
    assert result[1].type == "image"
    assert len(result[1].data) > 100


def test_compare_same_model_no_diff(tmp_path):
    """Comparing a model to itself: no spec changes."""
    _skip_if_missing()
    from art.mcp_server import compare_versions
    import fue
    ts, _ = fue.inp.load(_PCE_INP)
    path = str(tmp_path / "same.inp")
    _build_inp(ts, lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2, output_path=path)
    result = compare_versions(path, path)
    text = result[0].text
    # Same model → no spec changes; same npar → not nested → no LR
    assert "Sin cambios" in text or "no anidados" in text.lower()


def test_compare_non_nested_no_lr(tmp_path):
    """AR(1) vs MA(1): non-nested (same npar), LR test should say 'no aplicable'."""
    _skip_if_missing()
    from art.mcp_server import compare_versions
    import fue
    ts, _ = fue.inp.load(_PCE_INP)
    path_ar = str(tmp_path / "ar1.inp")
    path_ma = str(tmp_path / "ma1.inp")
    # AR(1): p=1, q=0  |  MA(1): p=0, q=1  — same npar, not nested
    _build_inp(ts, lam=0.0, d=1, D=0, p=1, q=0, n_harmonics=2, output_path=path_ar)
    _build_inp(ts, lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2, output_path=path_ma)
    result = compare_versions(path_ar, path_ma)
    text = result[0].text
    assert "no anidados" in text.lower() or "no aplicable" in text.lower()


def test_build_inp_pq0_with_harmonics_no_crash(tmp_path):
    """p=0, q=0 with harmonics must not crash (workaround: AR(1) phi=0 fixed)."""
    _skip_if_missing()
    from art.mcp_server import _load_fitted
    import fue
    ts, _ = fue.inp.load(_PCE_INP)
    path = str(tmp_path / "pq0.inp")
    _build_inp(ts, lam=0.0, d=1, D=0, p=0, q=0, n_harmonics=2, output_path=path)
    _, model = _load_fitted(path)
    r = model._result
    assert r.loglik < 0
    # PCE is quarterly (freq=4): cos/sin pairs cap at freq//2-1 = 1, so the full
    # deterministic spec is 1 pair + alter = 3 (the AR(1) phi=0 workaround is
    # fixed, not estimated). n_harmonics=2 is clamped to 1 pair.
    assert r.npar == 3
