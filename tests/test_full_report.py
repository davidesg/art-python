"""Tests for full_report.py — save_full_report (Phase 5)."""
import os
import pytest
import fue
from art.full_report import save_full_report, FullReport
from art.diagnosis import DiagnosisResult
from art.interventions import InterventionDiagnosis

_PC6_INP = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Chile/ipc/mensuales/"
    "analisis/muestra_1.86_12.01/guion3/PC6.inp"
)
_PO2_INP = os.path.expanduser(
    "~/Documents/Documentos/Tesis/Analisis/Colombia/ipc/mensuales/"
    "analisis/muestra_1.89_12.01/guion1/PO2.inp"
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
# API
# ---------------------------------------------------------------------------

class TestSaveFullReportAPI:
    def test_raises_if_not_fitted(self, tmp_path):
        _skip_if_missing(_PC6_INP)
        _, m = fue.inp.load(_PC6_INP)
        with pytest.raises(RuntimeError, match="not been fitted"):
            save_full_report(m, str(tmp_path / "out.html"))

    def test_returns_full_report(self, tmp_path):
        m = _load_and_fit(_PC6_INP)
        r = save_full_report(m, str(tmp_path / "out.html"))
        assert isinstance(r, FullReport)

    def test_html_file_created(self, tmp_path):
        m = _load_and_fit(_PC6_INP)
        out = str(tmp_path / "out.html")
        save_full_report(m, out)
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_path_in_result(self, tmp_path):
        m = _load_and_fit(_PC6_INP)
        out = str(tmp_path / "out.html")
        r = save_full_report(m, out)
        assert r.path == out


# ---------------------------------------------------------------------------
# Result fields
# ---------------------------------------------------------------------------

class TestFullReportFields:
    @pytest.fixture(scope="class")
    def report(self, tmp_path_factory):
        m = _load_and_fit(_PC6_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "pc6.html")
        return save_full_report(m, out)

    def test_diagnosis_type(self, report):
        assert isinstance(report.diagnosis, DiagnosisResult)

    def test_interventions_type(self, report):
        assert isinstance(report.interventions, InterventionDiagnosis)

    def test_dcd_results_list(self, report):
        assert isinstance(report.dcd_results, list)

    def test_meg_results_list(self, report):
        assert isinstance(report.meg_results, list)

    def test_rv_results_list(self, report):
        assert isinstance(report.rv_results, list)


# ---------------------------------------------------------------------------
# HTML structure
# ---------------------------------------------------------------------------

class TestHTMLStructure:
    @pytest.fixture(scope="class")
    def html(self, tmp_path_factory):
        m = _load_and_fit(_PC6_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "pc6.html")
        save_full_report(m, out)
        with open(out, encoding="utf-8") as f:
            return f.read()

    def test_is_valid_html(self, html):
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html

    def test_has_four_sections(self, html):
        assert html.count("<details") == 4

    def test_section_1_modelo(self, html):
        assert "1. Modelo estimado" in html

    def test_section_2_diagnosis(self, html):
        assert "2. Diagnosis" in html

    def test_section_3_formal_tests(self, html):
        assert "3. Contrastes formales" in html

    def test_section_4_interventions(self, html):
        assert "4. Intervenciones" in html

    def test_arima_spec_in_title(self, html):
        assert "ARIMA" in html

    def test_loglik_shown(self, html):
        assert "loglik" in html

    def test_aic_shown(self, html):
        assert "AIC" in html

    def test_param_table_has_se(self, html):
        assert "SE" in html

    def test_diagnosis_figure_embedded(self, html):
        assert "data:image/png;base64," in html

    def test_dcd_results_shown(self, html):
        # PC6 has MA(1), so DCD should appear
        assert "DCD" in html

    def test_meg_results_shown(self, html):
        # PC6: D=0, has harmonics → MEG runs
        assert "MEG" in html


# ---------------------------------------------------------------------------
# Chile PC6 — content checks
# ---------------------------------------------------------------------------

class TestChilePC6Content:
    @pytest.fixture(scope="class")
    def report(self, tmp_path_factory):
        m = _load_and_fit(_PC6_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "pc6.html")
        return save_full_report(m, out)

    def test_no_outliers_at_3p5(self, report):
        assert not report.interventions.has_outliers

    def test_dcd_has_one_result(self, report):
        # PC6 has one free MA factor
        assert len(report.dcd_results) == 1

    def test_dcd_rejects_invertibility(self, report):
        # PC6 MA(1) is clearly invertible (LR ≈ 149)
        assert report.dcd_results[0].lr > 4.41

    def test_meg_ran(self, report):
        # D=0 + harmonics → MEG should have run
        assert len(report.meg_results) > 0

    def test_freq1_stochastic(self, report):
        # PC6 freq=1 is stochastic (LR ≈ 4.32, just above 5% threshold)
        freq1 = next((r for r in report.meg_results if r.freq == 1), None)
        assert freq1 is not None
        assert freq1.stochastic


# ---------------------------------------------------------------------------
# Colombia PO2 — outlier in section 4
# ---------------------------------------------------------------------------

class TestColombiaPO2Content:
    @pytest.fixture(scope="class")
    def report(self, tmp_path_factory):
        m = _load_and_fit(_PO2_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "po2.html")
        return save_full_report(m, out, intervention_threshold=3.0)

    def test_has_outlier(self, report):
        assert report.interventions.has_outliers

    def test_outlier_date_in_html(self, tmp_path_factory):
        m = _load_and_fit(_PO2_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "po2.html")
        save_full_report(m, out, intervention_threshold=3.0)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        assert "02/1999" in html

    def test_section_4_opens_by_default(self, tmp_path_factory):
        # When there are outliers, section 4 should have 'open' attribute
        m = _load_and_fit(_PO2_INP)
        out = str(tmp_path_factory.mktemp("rpt") / "po2.html")
        save_full_report(m, out, intervention_threshold=3.0)
        with open(out, encoding="utf-8") as f:
            html = f.read()
        # The <details open> for section 4 should appear
        assert "<details open>" in html or "<details open\n" in html


# ---------------------------------------------------------------------------
# run_meg=False
# ---------------------------------------------------------------------------

class TestRunMegFalse:
    def test_meg_skipped(self, tmp_path):
        m = _load_and_fit(_PC6_INP)
        r = save_full_report(m, str(tmp_path / "out.html"), run_meg=False)
        assert r.meg_results == []
