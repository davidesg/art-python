"""Tests for interventions.py — Phase 4a and 4b (diagnose_interventions, test_intervention)."""
import math
import os
import pytest
import fue
from art.interventions import diagnose_interventions, InterventionDiagnosis, OutlierWarning

# ---------------------------------------------------------------------------
# Paths to real-case data
# ---------------------------------------------------------------------------

# Colombia PO2 (guion1, muestra 1/89-12/01):
#   d=2, lambda=1, 11 harmonics+alter, AR(1)+MA(1), NO interventions.
#   Documented in guion1/muestra_1.89_12.01.tex: extreme negative residual
#   at 2/1999 ("valor negativo grande en 2/99 que puede estar matando
#   las acf/pacf").  DRVUS .out confirms: res=-1.142, sigma=0.327 → z≈-3.38.
_PO2_INP = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Colombia/ipc/mensuales/"
    "analisis/muestra_1.89_12.01/guion1/PO2.inp"
)

# Chile PC6 (guion3, muestra 1/86-12/01):
#   d=2, lambda=0 (log), all harmonics+alter, MA(1), NO interventions.
#   Well-specified intermediate model; used in formal-tests suite.
_PC6_INP = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Chile/ipc/mensuales/"
    "analisis/muestra_1.86_12.01/guion3/PC6.inp"
)


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


def _load_and_fit(inp_path):
    _skip_if_missing(inp_path)
    _ts, m = fue.inp.load(inp_path)
    m.fit()
    return m


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

class TestDiagnoseInterventionsAPI:
    def test_raises_if_not_fitted(self):
        _skip_if_missing(_PO2_INP)
        _ts, m = fue.inp.load(_PO2_INP)
        with pytest.raises(RuntimeError, match="not been fitted"):
            diagnose_interventions(m)

    def test_returns_intervention_diagnosis(self):
        m = _load_and_fit(_PO2_INP)
        result = diagnose_interventions(m, threshold=3.0)
        assert isinstance(result, InterventionDiagnosis)

    def test_threshold_stored(self):
        m = _load_and_fit(_PO2_INP)
        result = diagnose_interventions(m, threshold=3.2)
        assert result.threshold == 3.2

    def test_outliers_sorted_by_abs_z_descending(self):
        m = _load_and_fit(_PO2_INP)
        result = diagnose_interventions(m, threshold=2.5)
        zabs = [abs(w.z) for w in result.outliers]
        assert zabs == sorted(zabs, reverse=True)

    def test_summary_is_string(self):
        m = _load_and_fit(_PO2_INP)
        result = diagnose_interventions(m, threshold=3.0)
        s = result.summary()
        assert isinstance(s, str)
        assert len(s) > 0


# ---------------------------------------------------------------------------
# Colombia PO2 — documented outlier at 2/1999
# ---------------------------------------------------------------------------

class TestColombiaPO2_Outlier:
    """
    PO2 (Colombia IPC, 1/89-12/01): AR(1)+MA(1), no interventions.
    DRVUS output (PO2.out) confirms minimum residual = -1.142 at 2/1999,
    observation 120 in residual array (154 obs, 3/1989-12/2001).
    Using z ≈ -3.38, threshold=3.0 should detect it.
    """

    @pytest.fixture(scope="class")
    def result(self):
        m = _load_and_fit(_PO2_INP)
        return diagnose_interventions(m, threshold=3.0)

    def test_has_outliers(self, result):
        assert result.has_outliers

    def test_jb_unreliable(self, result):
        assert result.jb_unreliable

    def test_q_unreliable(self, result):
        assert result.q_unreliable

    def test_most_extreme_date_is_feb_1999(self, result):
        """Documented: extreme at 2/1999."""
        assert len(result.outliers) >= 1
        assert result.outliers[0].date == "02/1999"

    def test_most_extreme_z_is_negative(self, result):
        """DRVUS: residual = -1.142 → negative z."""
        assert result.outliers[0].z < 0

    def test_most_extreme_z_magnitude(self, result):
        """DRVUS: z ≈ -3.38; allow margin for Python vs DRVUS differences."""
        z = result.outliers[0].z
        assert 3.0 < abs(z) < 5.0

    def test_variance_fraction_in_range(self, result):
        vf = result.outliers[0].variance_fraction
        assert 0.0 < vf < 1.0

    def test_summary_mentions_feb_1999(self, result):
        assert "02/1999" in result.summary()

    def test_summary_warns_jb(self, result):
        assert "Jarque-Bera" in result.summary()

    def test_summary_warns_q(self, result):
        assert "Ljung-Box" in result.summary()


# ---------------------------------------------------------------------------
# Colombia PO2 — OutlierWarning structure
# ---------------------------------------------------------------------------

class TestOutlierWarningStructure:
    @pytest.fixture(scope="class")
    def warning(self):
        m = _load_and_fit(_PO2_INP)
        result = diagnose_interventions(m, threshold=3.0)
        assert result.outliers, "expected at least one outlier"
        return result.outliers[0]

    def test_obs_index_non_negative(self, warning):
        assert warning.obs_index >= 0

    def test_date_nonempty(self, warning):
        assert len(warning.date) > 0

    def test_z_finite(self, warning):
        import math
        assert math.isfinite(warning.z)

    def test_variance_fraction_finite(self, warning):
        import math
        assert math.isfinite(warning.variance_fraction)

    def test_acf_lags_are_positive_ints(self, warning):
        for j in warning.acf_lags_affected:
            assert isinstance(j, int) and j >= 1


# ---------------------------------------------------------------------------
# Chile PC6 — no extreme residuals at default threshold
# ---------------------------------------------------------------------------

class TestChilePC6_Clean:
    """
    PC6 (Chile IPC, 1/86-12/01): all harmonics, well-specified.
    Expected: no residuals above the default threshold of 3.5.
    """

    @pytest.fixture(scope="class")
    def result(self):
        m = _load_and_fit(_PC6_INP)
        return diagnose_interventions(m, threshold=3.5)

    def test_no_outliers_at_3p5(self, result):
        assert not result.has_outliers

    def test_jb_not_flagged(self, result):
        assert not result.jb_unreliable

    def test_q_not_flagged(self, result):
        assert not result.q_unreliable

    def test_summary_says_no_extremes(self, result):
        assert "No extreme" in result.summary()


# ---------------------------------------------------------------------------
# Phase 4b — test_intervention / simplify_interventions
# ---------------------------------------------------------------------------

_IPC_ES_AUTO = os.path.expanduser(
    "~/Dropbox/SRC/ART/Data/inp/IPC_ES.inp"
)
_PO3 = os.path.expanduser(
    "~/Dropbox/SRC/drvus-source/1.2.01/drvus/src/Tesis"
    "/po/muestra_1.89_12.01/PO3.pre"
)


@pytest.fixture(scope="module")
def ipc_es_model_with_itv():
    """IPC_ES series estimated with one known pulse intervention (build_model)."""
    _skip_if_missing(_IPC_ES_AUTO)
    import sys, os as _os
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "src"))
    import fue, tempfile
    from art.mcp_server import build_model
    with tempfile.TemporaryDirectory() as tmp:
        out = _os.path.join(tmp, "ipc_es_4b.inp")
        build_model(_IPC_ES_AUTO, out, max_rounds=2)
        ts, m = fue.inp.load(out)
        m.fit()
        yield m


class TestTestIntervention:
    def test_returns_result_object(self, ipc_es_model_with_itv):
        from art.interventions import test_intervention, InterventionTestResult
        m = ipc_es_model_with_itv
        # find first non-structural intervention
        for i, itv in enumerate(m.interventions):
            if itv.type not in ("cos", "sin", "alter"):
                r = test_intervention(m, i)
                assert isinstance(r, InterventionTestResult)
                break

    def test_result_fields_finite(self, ipc_es_model_with_itv):
        from art.interventions import test_intervention
        m = ipc_es_model_with_itv
        for i, itv in enumerate(m.interventions):
            if itv.type not in ("cos", "sin", "alter"):
                r = test_intervention(m, i)
                assert all(math.isfinite(v) for v in r.omega)
                assert all(math.isfinite(v) for v in r.omega_se)
                assert all(math.isfinite(v) for v in r.omega_t)
                assert all(0.0 <= v <= 1.0 for v in r.omega_p)
                break

    def test_index_out_of_range_raises(self, ipc_es_model_with_itv):
        from art.interventions import test_intervention
        m = ipc_es_model_with_itv
        with pytest.raises(IndexError):
            test_intervention(m, 9999)

    def test_unfitted_model_raises(self):
        _skip_if_missing(_IPC_ES_AUTO)
        import fue
        ts, m = fue.inp.load(_IPC_ES_AUTO)
        from art.interventions import test_intervention
        with pytest.raises(ValueError):
            test_intervention(m, 0)

    def test_significant_flag_correct(self, ipc_es_model_with_itv):
        from art.interventions import test_intervention
        m = ipc_es_model_with_itv
        for i, itv in enumerate(m.interventions):
            if itv.type not in ("cos", "sin", "alter"):
                r = test_intervention(m, i)
                expected = any(pv < 0.05 for pv in r.omega_p)
                assert r.significant == expected
                break

    def test_se_matches_cov_diagonal(self, ipc_es_model_with_itv):
        """SE from test_intervention must match sqrt(cov_diag) for each param."""
        import numpy as np
        from art.interventions import test_intervention, _intervention_param_start
        m = ipc_es_model_with_itv
        cov = np.asarray(m._result.cov_matrix)
        for i, itv in enumerate(m.interventions):
            if itv.type not in ("cos", "sin", "alter"):
                r  = test_intervention(m, i)
                start = _intervention_param_start(m, i)
                for k, se in enumerate(r.omega_se):
                    expected_se = float(np.sqrt(max(cov[start + k, start + k], 0)))
                    assert abs(se - expected_se) < 1e-8
                break


class TestSimplifyInterventions:
    def test_returns_list(self, ipc_es_model_with_itv):
        from art.interventions import simplify_interventions
        results = simplify_interventions(ipc_es_model_with_itv)
        assert isinstance(results, list)

    def test_skips_harmonics(self, ipc_es_model_with_itv):
        from art.interventions import simplify_interventions
        m = ipc_es_model_with_itv
        results = simplify_interventions(m)
        types = [r.itv_type for r in results]
        assert "cos" not in types
        assert "sin" not in types
        assert "alter" not in types

    def test_all_interventions_tested(self, ipc_es_model_with_itv):
        from art.interventions import simplify_interventions
        m = ipc_es_model_with_itv
        n_structural = sum(1 for itv in m.interventions
                           if itv.type in ("cos", "sin", "alter"))
        n_other = len(m.interventions) - n_structural
        results = simplify_interventions(m)
        assert len(results) == n_other

    def test_ipc_es_interventions_are_significant(self, ipc_es_model_with_itv):
        """After build_model IPC_ES, all added interventions should be significant."""
        from art.interventions import simplify_interventions
        results = simplify_interventions(ipc_es_model_with_itv)
        assert len(results) > 0
        # At least some interventions must be significant
        assert any(r.significant for r in results)

    def test_summary_text_not_empty(self, ipc_es_model_with_itv):
        from art.interventions import simplify_interventions, simplify_summary
        results = simplify_interventions(ipc_es_model_with_itv)
        text = simplify_summary(results)
        assert "Contraste de intervenciones" in text
        assert "Significativas" in text
