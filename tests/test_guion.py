"""Tests for Bloque P — Guion de análisis (version log)."""
from __future__ import annotations
import json
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


def _load_fitted(inp_path):
    import fue
    ts, m = fue.inp.load(inp_path)
    m.fit()
    return ts, m


# ---------------------------------------------------------------------------
# GuionEntry / Guion dataclass roundtrip
# ---------------------------------------------------------------------------

class TestGuionRoundtrip:
    def _make_entry(self, version=1) -> "GuionEntry":
        from art.guion import GuionEntry, GuionStats
        stats = GuionStats(
            loglik=-100.0, aic=210.0, bic=220.0,
            sigma_a=0.005, q_pass=True, jb_pass=True,
            n_extreme=0, extreme=[],
        )
        return GuionEntry(
            version=version,
            name=f"PC{version}",
            inp_path=f"/tmp/v0{version}.inp",
            timestamp="2026-06-13T10:00:00",
            spec={"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 1,
                  "P": 0, "Q": 0, "n_harmonics": 4, "interventions": []},
            stats=stats,
            equation="∇[ln y_t] = D_t(4 arm.) + [1-θ(B)]·a_t",
            decision="Modelo inicial",
            rationale="d=1 por ACF",
            problems_found="Outlier en 03/2008",
            next_version="PC2: añadir pulse 03/2008",
        )

    def test_to_dict_has_required_keys(self):
        e = self._make_entry()
        d = e.to_dict()
        for k in ("version", "name", "inp_path", "timestamp", "spec",
                  "stats", "equation", "decision", "rationale",
                  "problems_found", "next_version"):
            assert k in d, f"missing key: {k}"

    def test_from_dict_roundtrip(self):
        from art.guion import GuionEntry
        e = self._make_entry()
        d = e.to_dict()
        e2 = GuionEntry.from_dict(d)
        assert e2.version == e.version
        assert e2.name == e.name
        assert e2.stats.loglik == e.stats.loglik
        assert e2.stats.q_pass == e.stats.q_pass
        assert e2.spec["lam"] == e.spec["lam"]

    def test_guion_to_dict_from_dict(self):
        from art.guion import Guion, GuionEntry
        e1 = self._make_entry(1)
        e2 = self._make_entry(2)
        g = Guion(series="IPC test", analyst="DG", created="2026-06-13", entries=[e1, e2])
        d = g.to_dict()
        g2 = Guion.from_dict(d)
        assert g2.series == "IPC test"
        assert len(g2.entries) == 2
        assert g2.entries[1].name == "PC2"

    def test_figure_b64_roundtrip(self):
        from art.guion import GuionEntry, GuionStats
        stats = GuionStats(-100, None, None, 0.01, None, None, 0)
        e = GuionEntry(
            version=1, name="PC1", inp_path="/tmp/v1.inp",
            timestamp="2026-06-13T00:00:00",
            spec={}, stats=stats, equation="y_t = a_t",
            decision="", rationale="", problems_found="", next_version="",
            figure_b64="abc123",
        )
        d = e.to_dict()
        e2 = GuionEntry.from_dict(d)
        assert e2.figure_b64 == "abc123"


# ---------------------------------------------------------------------------
# load_guion / save_guion
# ---------------------------------------------------------------------------

class TestLoadSave:
    def test_save_and_load(self, tmp_path):
        from art.guion import Guion, GuionEntry, GuionStats, save_guion, load_guion
        stats = GuionStats(-50.0, 110.0, 115.0, 0.003, True, True, 0)
        e = GuionEntry(1, "PC1", "/tmp/v1.inp", "2026-06-13T10:00:00",
                       {"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 0,
                        "P": 0, "Q": 0, "n_harmonics": 6, "interventions": []},
                       stats, "eq", "dec", "rat", "prob", "next")
        g = Guion("TestSeries", "DG", "2026-06-13", [e])

        path = str(tmp_path / "guion.json")
        save_guion(g, path)
        assert os.path.exists(path)

        g2 = load_guion(path)
        assert g2.series == "TestSeries"
        assert len(g2.entries) == 1
        assert g2.entries[0].stats.loglik == -50.0

    def test_save_creates_parent_dirs(self, tmp_path):
        from art.guion import Guion, save_guion
        g = Guion("X", "Y", "2026-06-13")
        path = str(tmp_path / "subdir" / "guion.json")
        save_guion(g, path)
        assert os.path.exists(path)

    def test_json_is_valid_and_readable(self, tmp_path):
        from art.guion import Guion, save_guion
        g = Guion("MyS", "A", "2026-01-01")
        path = str(tmp_path / "g.json")
        save_guion(g, path)
        with open(path) as f:
            d = json.load(f)
        assert d["series"] == "MyS"
        assert d["entries"] == []


# ---------------------------------------------------------------------------
# _extract_spec / _extract_stats
# ---------------------------------------------------------------------------

class TestExtractSpec:
    @pytest.fixture(autouse=True)
    def load(self):
        _skip_if_missing()
        _, self.m = _load_fitted(_PCE_INP)

    def test_extract_spec_has_keys(self):
        from art.guion import _extract_spec
        spec = _extract_spec(self.m, lam=0.0)
        for k in ("lam", "d", "D", "p", "q", "P", "Q", "n_harmonics", "interventions"):
            assert k in spec

    def test_extract_spec_lam_preserved(self):
        from art.guion import _extract_spec
        assert _extract_spec(self.m, lam=0.5)["lam"] == 0.5

    def test_extract_spec_d_D(self):
        from art.guion import _extract_spec
        spec = _extract_spec(self.m, lam=0.0)
        assert spec["d"] == self.m.d
        assert spec["D"] == self.m.D

    def test_extract_stats_has_loglik(self):
        from art.guion import _extract_stats
        from art.diagnosis import diagnose
        dr = diagnose(self.m)
        stats = _extract_stats(self.m, dr)
        assert abs(stats.loglik - self.m._result.loglik) < 1e-6

    def test_extract_stats_sigma_a_positive(self):
        from art.guion import _extract_stats
        from art.diagnosis import diagnose
        dr = diagnose(self.m)
        stats = _extract_stats(self.m, dr)
        assert stats.sigma_a > 0

    def test_extract_stats_q_jb_booleans(self):
        from art.guion import _extract_stats
        from art.diagnosis import diagnose
        dr = diagnose(self.m)
        stats = _extract_stats(self.m, dr)
        assert isinstance(stats.q_pass, bool)
        assert isinstance(stats.jb_pass, bool)


# ---------------------------------------------------------------------------
# _build_equation
# ---------------------------------------------------------------------------

class TestBuildEquation:
    def test_log_differenced(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 0,
                               "P": 0, "Q": 0, "n_harmonics": 0, "interventions": []}, 4)
        assert "ln" in eq
        assert "∇" in eq

    def test_identity_no_diff(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 1.0, "d": 0, "D": 0, "p": 0, "q": 0,
                               "P": 0, "Q": 0, "n_harmonics": 0, "interventions": []}, 4)
        assert "y_t" in eq
        assert "∇" not in eq

    def test_harmonics_appear(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 0.0, "d": 2, "D": 0, "p": 0, "q": 0,
                               "P": 0, "Q": 0, "n_harmonics": 6, "interventions": []}, 12)
        assert "arm." in eq

    def test_ma_part_appears(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 1,
                               "P": 0, "Q": 0, "n_harmonics": 4, "interventions": []}, 4)
        assert "θ" in eq

    def test_sarima_parts(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 0.0, "d": 1, "D": 1, "p": 0, "q": 1,
                               "P": 0, "Q": 1, "n_harmonics": 0, "interventions": []}, 12)
        assert "Θ" in eq
        assert "12" in eq

    def test_seasonal_diff_notation(self):
        from art.guion import _build_equation
        eq = _build_equation({"lam": 0.0, "d": 1, "D": 1, "p": 0, "q": 0,
                               "P": 0, "Q": 0, "n_harmonics": 0, "interventions": []}, 4)
        assert "∇_4" in eq


# ---------------------------------------------------------------------------
# export_guion_html
# ---------------------------------------------------------------------------

class TestExportHtml:
    def _make_guion(self):
        from art.guion import Guion, GuionEntry, GuionStats
        stats = GuionStats(-120.0, 250.0, 260.0, 0.006, True, False, 1,
                           [{"obs": 10, "date": "Q2/2005", "z": 3.9}])
        e = GuionEntry(1, "PC1", "/tmp/v1.inp", "2026-06-13T09:00:00",
                       {"lam": 0.0, "d": 1, "D": 0, "p": 0, "q": 1,
                        "P": 0, "Q": 0, "n_harmonics": 2, "interventions": []},
                       stats, "∇[ln y_t] = D_t + [1-θB]a_t",
                       "Modelo base", "d=1 ACF", "Outlier Q2/05", "PC2: pulse")
        return Guion("PCE", "DG", "2026-06-13", [e])

    def test_html_is_string(self):
        from art.guion import export_guion_html
        html = export_guion_html(self._make_guion())
        assert isinstance(html, str)
        assert len(html) > 100

    def test_html_has_series_name(self):
        from art.guion import export_guion_html
        html = export_guion_html(self._make_guion())
        assert "PCE" in html

    def test_html_has_version_name(self):
        from art.guion import export_guion_html
        html = export_guion_html(self._make_guion())
        assert "PC1" in html

    def test_html_has_equation(self):
        from art.guion import export_guion_html
        html = export_guion_html(self._make_guion())
        assert "θ" in html or "theta" in html.lower() or "D_t" in html

    def test_html_has_aic(self):
        from art.guion import export_guion_html
        html = export_guion_html(self._make_guion())
        assert "250" in html  # AIC = 250.0

    def test_empty_guion_html(self):
        from art.guion import Guion, export_guion_html
        g = Guion("Empty", "", "2026-01-01")
        html = export_guion_html(g)
        assert "Sin versiones" in html


# ---------------------------------------------------------------------------
# record_version MCP tool (integration)
# ---------------------------------------------------------------------------

def test_record_version_creates_guion(tmp_path):
    _skip_if_missing()
    from art.mcp_server import record_version
    guion_path = str(tmp_path / "guion.json")
    result = record_version(_PCE_INP, guion_path,
                            name="PC1", decision="Prueba",
                            rationale="Test", problems_found="Ninguno",
                            next_version="PC2: añadir MA")
    assert os.path.exists(guion_path)
    with open(guion_path) as f:
        d = json.load(f)
    assert len(d["entries"]) == 1
    assert d["entries"][0]["name"] == "PC1"
    assert d["entries"][0]["stats"]["loglik"] < 0


def test_record_version_auto_increments(tmp_path):
    _skip_if_missing()
    from art.mcp_server import record_version
    guion_path = str(tmp_path / "guion.json")
    record_version(_PCE_INP, guion_path, name="PC1")
    record_version(_PCE_INP, guion_path, name="PC2")
    with open(guion_path) as f:
        d = json.load(f)
    assert len(d["entries"]) == 2
    assert d["entries"][0]["version"] == 1
    assert d["entries"][1]["version"] == 2


def test_export_guion_creates_html(tmp_path):
    _skip_if_missing()
    from art.mcp_server import record_version, export_guion
    guion_path = str(tmp_path / "guion.json")
    html_path  = str(tmp_path / "report.html")
    record_version(_PCE_INP, guion_path, name="PC1", decision="Test")
    result = export_guion(guion_path, html_path)
    assert os.path.exists(html_path)
    with open(html_path) as f:
        html = f.read()
    assert "PC1" in html
    assert "<table" in html


# ---------------------------------------------------------------------------
# confirm_and_estimate with guion_path
# ---------------------------------------------------------------------------

def test_confirm_and_estimate_records_to_guion(tmp_path):
    _skip_if_missing()
    from art.mcp_server import confirm_and_estimate
    out_inp    = str(tmp_path / "ce.inp")
    guion_path = str(tmp_path / "guion.json")
    result = confirm_and_estimate(
        _PCE_INP, out_inp,
        lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=2,
        guion_path=guion_path, guion_name="PC1",
        guion_decision="Prueba confirm_and_estimate",
    )
    assert os.path.exists(guion_path)
    with open(guion_path) as f:
        d = json.load(f)
    assert d["entries"][0]["name"] == "PC1"
    assert "Registrado" in result[0].text or "guion" in result[0].text.lower()
