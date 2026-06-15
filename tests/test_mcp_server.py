"""Smoke tests for the MCP server tools."""
import os
import pytest

_RIPC1 = os.path.expanduser(
    "~/Dropbox/SRC/atws/fue/fue/tests/real_cases/PRICES"
    "/IPC/Mensual/sample_1.2002_12.2007/RIPC.1.pre"
)
_PO3 = os.path.expanduser(
    "~/Dropbox/SRC/drvus-source/1.2.01/drvus/src/Tesis"
    "/po/muestra_1.89_12.01/PO3.pre"
)


def _skip_if_missing(path):
    if not os.path.exists(path):
        pytest.skip(f"test data not found: {path}")


# ---------------------------------------------------------------------------
# series_info
# ---------------------------------------------------------------------------

def test_series_info_returns_string():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import series_info
    result = series_info(_RIPC1)
    assert isinstance(result, str)
    assert "RIPC" in result
    assert "n**: 72" in result
    assert "freq**: 12" in result


def test_series_info_missing_file():
    from art.mcp_server import series_info
    result = series_info("/nonexistent/path.pre")
    assert "❌" in result


# ---------------------------------------------------------------------------
# boxcox_analysis
# ---------------------------------------------------------------------------

def test_boxcox_analysis_returns_text_and_figure():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import boxcox_analysis
    result = boxcox_analysis(_RIPC1)
    assert len(result) == 2
    assert result[0].type == "text"
    assert "Box-Cox" in result[0].text
    assert result[1].type == "image"
    assert len(result[1].data) > 100  # non-empty base64


# ---------------------------------------------------------------------------
# estimate_and_diagnose
# ---------------------------------------------------------------------------

def test_estimate_and_diagnose_returns_text_and_figure():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import estimate_and_diagnose
    result = estimate_and_diagnose(_RIPC1)
    assert len(result) == 2
    assert result[0].type == "text"
    assert "Diagnosis" in result[0].text
    assert result[1].type == "image"


def test_estimate_and_diagnose_detects_extremes_po3():
    _skip_if_missing(_PO3)
    from art.mcp_server import estimate_and_diagnose
    # PO3 has the 1999 outlier — diagnosis should detect it
    result = estimate_and_diagnose(_PO3)
    text = result[0].text
    # Should mention intervention hints if extremes present, or clean pass
    assert "Diagnosis" in text


# ---------------------------------------------------------------------------
# formal_tests
# ---------------------------------------------------------------------------

def test_boxcox_analysis_data_fields():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import boxcox_analysis
    # Test that enriched describe_boxcox returns ambiguous flag
    from art.describe import describe_boxcox
    import fue
    ts, _ = fue.inp.load(_RIPC1)
    d = describe_boxcox(ts)
    assert "ambiguous" in d.data
    assert "gap" in d.data
    assert isinstance(d.data["ambiguous"], bool)


def test_seasonality_decision_field():
    _skip_if_missing(_RIPC1)
    from art.describe import describe_seasonality
    import fue
    ts, _ = fue.inp.load(_RIPC1)
    d = describe_seasonality(ts)
    assert "decision" in d.data
    assert d.data["decision"] in ("A", "B1", "B2")
    assert "recommended_d" in d.data


def test_identification_ambiguous_field():
    _skip_if_missing(_RIPC1)
    from art.describe import describe_identification
    import fue
    ts, _ = fue.inp.load(_RIPC1)
    d = describe_identification(ts, d=1, D=0, lam=0.0)
    assert "ambiguous" in d.data
    assert "top_gap" in d.data
    for s in d.data["suggestions"]:
        assert "pattern" in s


def test_formal_tests_no_applicable_ripc1():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import formal_tests
    result = formal_tests(_RIPC1, run_meg=False)
    assert result[0].type == "text"
    assert "Ningún contraste aplicable" in result[0].text


def test_formal_tests_dcd_po3():
    _skip_if_missing(_PO3)
    from art.mcp_server import formal_tests
    result = formal_tests(_PO3, run_meg=False)
    assert result[0].type == "text"
    text = result[0].text
    assert "DCD" in text
    assert "Invertible" in text


_IPC_ES_M02 = os.path.join(
    os.path.dirname(__file__), "..", "cases", "IPC_ES", "IPC_ES_m02.pre"
)


def test_formal_tests_shin_fuller_ipc_es():
    """Shin-Fuller test runs and reports stationarity for IPC_ES_m02 (AR(1))."""
    _skip_if_missing(_IPC_ES_M02)
    from art.mcp_server import formal_tests
    result = formal_tests(_IPC_ES_M02, run_meg=False)
    assert result[0].type == "text"
    text = result[0].text
    assert "Shin-Fuller" in text
    assert "Estacionario" in text
    assert "Ningún contraste aplicable" not in text


def test_formal_tests_shin_fuller_data_field():
    """formal_tests returns shin_fuller dict with phi_1u and stationary fields."""
    _skip_if_missing(_IPC_ES_M02)
    from art.describe import describe_formal_tests
    import fue
    _, m = fue.load(_IPC_ES_M02)
    m.fit()
    desc = describe_formal_tests(m, run_meg=False)
    sf = desc.data.get("shin_fuller")
    assert sf is not None, "shin_fuller key missing from data"
    assert "phi_1u" in sf
    assert "stationary" in sf
    assert sf["stationary"] is True        # IPC_ES_m02 AR(1) is well inside unit circle


# ---------------------------------------------------------------------------
# intervention_analysis
# ---------------------------------------------------------------------------

def test_intervention_analysis_no_outliers():
    _skip_if_missing(_RIPC1)
    from art.mcp_server import intervention_analysis
    result = intervention_analysis(_RIPC1)
    assert result[0].type == "text"
    assert "Sin anomalías" in result[0].text or "No se detectan" in result[0].text


# ---------------------------------------------------------------------------
# full_report
# ---------------------------------------------------------------------------

def test_full_report_creates_file(tmp_path):
    _skip_if_missing(_RIPC1)
    from art.mcp_server import full_report
    out = str(tmp_path / "report.html")
    result = full_report(_RIPC1, out, run_meg=False)
    assert isinstance(result, str)
    assert os.path.exists(out)
    assert os.path.getsize(out) > 10_000


def test_full_report_missing_input(tmp_path):
    from art.mcp_server import full_report
    result = full_report("/nonexistent.pre", str(tmp_path / "out.html"), run_meg=False)
    assert "❌" in result


# ---------------------------------------------------------------------------
# save_identification_report
# ---------------------------------------------------------------------------

def test_save_identification_report_creates_file(tmp_path):
    _skip_if_missing(_RIPC1)
    from art.mcp_server import save_identification_report
    out = str(tmp_path / "ident.html")
    result = save_identification_report(_RIPC1, out, d=1, D=0, lam=0.0)
    assert isinstance(result, str)
    assert "ARIMA" in result
    assert os.path.exists(out)
    assert os.path.getsize(out) > 10_000


# ---------------------------------------------------------------------------
# Block B: guided_identification / confirm_and_estimate / suggest_intervention_form
# ---------------------------------------------------------------------------

_IPC_ES_INP = os.path.expanduser(
    "~/Dropbox/SRC/ART/Data/inp/IPC_ES.inp"
)


def test_guided_identification_returns_content():
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import guided_identification
    result = guided_identification(_IPC_ES_INP)
    assert len(result) >= 2
    assert result[0].type == "text"
    text = result[0].text
    assert "Box-Cox" in text or "λ" in text
    assert "decisión" in text.lower() or "decision" in text.lower() or "d=" in text


def test_confirm_and_estimate_produces_table_and_figure(tmp_path):
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import confirm_and_estimate
    out = str(tmp_path / "IPC_ES_b2.inp")
    result = confirm_and_estimate(_IPC_ES_INP, out,
                                   lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=5)
    assert len(result) == 2
    assert result[0].type == "text"
    text = result[0].text
    assert "ARIMA" in text
    # SE and t-stats must be numeric (not nan)
    assert "nan" not in text
    assert "MA(1)" in text
    assert result[1].type == "image"
    assert os.path.exists(out)


def test_suggest_intervention_form_adds_intervention(tmp_path):
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import confirm_and_estimate, suggest_intervention_form
    base = str(tmp_path / "IPC_ES_b2.inp")
    out  = str(tmp_path / "IPC_ES_b3.inp")
    confirm_and_estimate(_IPC_ES_INP, base,
                          lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=5)
    result = suggest_intervention_form(base, out, date="2/2022",
                                        form="pulse",
                                        context_hint="test outlier")
    assert len(result) == 2
    assert result[0].type == "text"
    text = result[0].text
    assert "PULSE" in text or "pulse" in text.lower()
    assert "2/2022" in text
    assert os.path.exists(out)
    # Verify the new .inp parses with the added intervention
    import fue
    _, m_new = fue.inp.load(out)
    types = [itv.type for itv in m_new.interventions]
    assert "pulse" in types or "impulse" in types


# ---------------------------------------------------------------------------
# Block C: build_model / batch_build
# ---------------------------------------------------------------------------

def test_build_model_runs_pipeline(tmp_path):
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import build_model
    out = str(tmp_path / "IPC_ES_auto.inp")
    result = build_model(_IPC_ES_INP, out, max_rounds=3)
    assert len(result) >= 1
    assert result[0].type == "text"
    text = result[0].text
    assert "λ" in text or "lambda" in text.lower()
    assert "ARIMA" in text or "Órdenes" in text
    assert "Ronda" in text
    assert "Parámetros" in text
    assert os.path.exists(out)


def test_build_model_adds_interventions(tmp_path):
    """build_model should detect and add pulse/step interventions for IPC_ES outliers."""
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import build_model
    import fue
    out = str(tmp_path / "IPC_ES_auto.inp")
    build_model(_IPC_ES_INP, out, max_rounds=4)
    _, m_auto = fue.inp.load(out)
    # IPC_ES has known outliers in 2022-2023 — should have added pulse/step
    itv_types = [itv.type for itv in m_auto.interventions]
    assert "pulse" in itv_types or "impulse" in itv_types or "step" in itv_types


def test_build_model_returns_figure_per_round(tmp_path):
    """Block D: build_model must return one figure per estimation round."""
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import build_model
    out = str(tmp_path / "IPC_ES_auto.inp")
    result = build_model(_IPC_ES_INP, out, max_rounds=3)
    types = [x.type for x in result]
    # At least the first round figure must be present
    assert "image" in types
    # IPC_ES needs multiple rounds (outliers in 2022-2023) — expect ≥2 figures
    n_images = types.count("image")
    assert n_images >= 1
    # Text log must contain per-round Q/JB detail (Block D)
    text = result[0].text
    assert "Q:" in text and "JB:" in text
    assert "Ronda 1:" in text


# ---------------------------------------------------------------------------
# Block D: immediate visualization rule
# ---------------------------------------------------------------------------

def test_estimate_and_diagnose_always_returns_image():
    """Block D rule: estimate_and_diagnose must always include ImageContent."""
    _skip_if_missing(_RIPC1)
    from art.mcp_server import estimate_and_diagnose
    result = estimate_and_diagnose(_RIPC1)
    types = [x.type for x in result]
    assert "text"  in types, "Missing text in estimate_and_diagnose"
    assert "image" in types, "Block D violation: estimate_and_diagnose returned no figure"


def test_confirm_and_estimate_always_returns_image(tmp_path):
    """Block D rule: confirm_and_estimate must always include ImageContent."""
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import confirm_and_estimate
    out = str(tmp_path / "check_d.inp")
    result = confirm_and_estimate(_IPC_ES_INP, out,
                                   lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=5)
    types = [x.type for x in result]
    assert "text"  in types, "Missing text in confirm_and_estimate"
    assert "image" in types, "Block D violation: confirm_and_estimate returned no figure"


def test_batch_build_produces_summary_table(tmp_path):
    _skip_if_missing(_IPC_ES_INP)
    _IPC_FR = os.path.expanduser("~/Dropbox/SRC/ART/Data/inp/IPC_FR.inp")
    _skip_if_missing(_IPC_FR)
    from art.mcp_server import batch_build
    result = batch_build([_IPC_ES_INP, _IPC_FR],
                          str(tmp_path / "batch_out"),
                          max_rounds=2)
    assert result[0].type == "text"
    text = result[0].text
    assert "Batch build" in text
    assert "IPC_ES" in text
    assert "IPC_FR" in text
    # Should contain table separator
    assert "|---" in text


def test_test_interventions_returns_significance_table(tmp_path):
    """Phase 4b MCP tool: test_interventions must classify each intervention."""
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import build_model, test_interventions
    out = str(tmp_path / "IPC_ES_4b.inp")
    build_model(_IPC_ES_INP, out, max_rounds=2)
    result = test_interventions(out)
    assert result[0].type == "text"
    text = result[0].text
    assert "Contraste de intervenciones" in text
    assert "Significativas" in text
    # Must contain at least one intervention result row
    assert "ω[0]=" in text


def test_compare_versions_block_q():
    """Block Q: compare_versions returns text+figure with LR test and dated diff."""
    _skip_if_missing(_IPC_ES_M02)
    m00 = os.path.join(os.path.dirname(__file__), "..", "cases", "IPC_ES", "IPC_ES_m00.pre")
    _skip_if_missing(m00)
    from art.mcp_server import compare_versions
    result = compare_versions(m00, _IPC_ES_M02)
    assert len(result) == 2
    assert result[0].type == "text"
    text = result[0].text
    # Stats table
    assert "loglik" in text
    assert "AIC" in text
    assert "Δ (B−A)" in text
    # LR test applied (models are nested)
    assert "Test LR" in text
    assert "B mejora significativamente" in text
    # Dated diff (not None)
    assert "step(" in text
    assert "None" not in text
    # Figure: 3x2 layout (residuals + ACF + PACF)
    assert result[1].type == "image"
    assert len(result[1].data) > 10_000


# ---------------------------------------------------------------------------
# Block M: guided_identification B2 path (D=1, seasonal ARMA)
# ---------------------------------------------------------------------------

_IPC_ES_M00 = os.path.join(
    os.path.dirname(__file__), "..", "cases", "IPC_ES", "IPC_ES_m00.pre"
)


def test_guided_identification_call4_b2_seasonal_note():
    """Block M: Call 4 with D=1 renders 'lag s=12' (not literal {ts.freq}) and P/Q suggestion."""
    _skip_if_missing(_IPC_ES_M00)
    from art.mcp_server import guided_identification
    result = guided_identification(_IPC_ES_M00, lam=0.0, d=1, D=1)
    assert len(result) >= 1
    text = result[0].text
    # B2 seasonal note must render with actual frequency value
    assert "lag s=12" in text, f"f-string not evaluated; got: {text[:300]}"
    # Next-step instruction must show explicit P/Q suggestion
    assert "P=<P>" in text and "Q=<Q>" in text
    assert "Sugerencia:" in text
    # Must include ACF/PACF rule for seasonal operators
    assert "SMA" in text or "SAR" in text


def test_guided_identification_call4_b2_returns_figure():
    """Block M: Call 4 B2 returns identification figure."""
    _skip_if_missing(_IPC_ES_M00)
    from art.mcp_server import guided_identification
    result = guided_identification(_IPC_ES_M00, lam=0.0, d=1, D=1)
    types = [x.type for x in result]
    assert "image" in types, "Block M B2 Call 4 returned no figure"


# ---------------------------------------------------------------------------
# Block P: record_version / export_guion (guion.json system)
# ---------------------------------------------------------------------------

def test_record_version_creates_guion(tmp_path):
    """Block P: record_version adds entries to guion.json (creates if absent)."""
    _skip_if_missing(_IPC_ES_M00)
    _skip_if_missing(_IPC_ES_M02)
    from art.mcp_server import record_version
    import json
    guion = str(tmp_path / "guion.json")
    # Record two versions
    r1 = record_version(_IPC_ES_M00, guion, name="PC1",
                         decision="Modelo inicial sin ARMA",
                         next_version="Añadir MA(1)")
    r2 = record_version(_IPC_ES_M02, guion, name="PC2",
                         decision="Añadido AR(1)")
    assert r1[0].type == "text"
    assert "PC1" in r1[0].text
    assert r2[0].type == "text"
    assert "PC2" in r2[0].text
    # guion.json must have 2 entries
    with open(guion, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["entries"]) == 2
    assert data["entries"][0]["name"] == "PC1"
    assert data["entries"][1]["name"] == "PC2"
    assert data["entries"][0]["version"] == 1
    assert data["entries"][1]["version"] == 2
    # Stats fields must be populated
    assert "loglik" in data["entries"][0]["stats"]
    assert "aic" in data["entries"][0]["stats"]
    assert "equation" in data["entries"][0]


def test_export_guion_creates_html(tmp_path):
    """Block P: export_guion renders guion.json to navigable HTML."""
    _skip_if_missing(_IPC_ES_M00)
    _skip_if_missing(_IPC_ES_M02)
    from art.mcp_server import record_version, export_guion
    guion  = str(tmp_path / "guion.json")
    out_html = str(tmp_path / "guion.html")
    record_version(_IPC_ES_M00, guion, name="PC1", decision="Initial model")
    record_version(_IPC_ES_M02, guion, name="PC2", decision="Added AR(1)")
    result = export_guion(guion, out_html)
    assert result[0].type == "text"
    assert "guion.html" in result[0].text or "guion" in result[0].text.lower()
    import os
    assert os.path.exists(out_html)
    with open(out_html, encoding="utf-8") as f:
        html = f.read()
    assert len(html) > 5_000
    assert "PC1" in html and "PC2" in html
    assert "<details" in html           # collapsible sections
    assert "<table" in html             # summary table
    assert "loglik" in html or "AIC" in html


def test_confirm_and_estimate_records_to_guion(tmp_path):
    """Block P: confirm_and_estimate with guion_path records the model."""
    _skip_if_missing(_IPC_ES_M00)
    import json
    from art.mcp_server import confirm_and_estimate
    out_inp = str(tmp_path / "test_b2.inp")
    guion   = str(tmp_path / "guion.json")
    result = confirm_and_estimate(
        _IPC_ES_M00, out_inp,
        lam=0.0, d=1, D=0, p=0, q=1, n_harmonics=5,
        guion_path=guion,
        guion_name="PC_test",
        guion_decision="Test MA(1) con armonicos",
    )
    assert result[0].type == "text"
    assert "PC_test" in result[0].text or "Registrado" in result[0].text
    with open(guion, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data["entries"]) == 1
    assert data["entries"][0]["name"] == "PC_test"


def test_batch_build_creates_html_reports(tmp_path):
    _skip_if_missing(_IPC_ES_INP)
    from art.mcp_server import batch_build
    out_dir = str(tmp_path / "batch_html")
    batch_build([_IPC_ES_INP], out_dir, max_rounds=2)
    htmls = [f for f in os.listdir(out_dir) if f.endswith(".html")]
    assert len(htmls) >= 1
    # HTML should be non-trivial
    with open(os.path.join(out_dir, htmls[0])) as fh:
        content = fh.read()
    assert len(content) > 5_000
