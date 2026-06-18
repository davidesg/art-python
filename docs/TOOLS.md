# ART — Referencia de herramientas MCP

32 herramientas expuestas por el servidor MCP (`art-mcp`). Agrupadas por etapa
del flujo Box-Jenkins-Treadway. Cada docstring es el contrato que lee el LLM.

## Datos / ingesta

### `create_inp(data, output_path, name, freq, start_year, start_period)`
Create a .inp file from raw time series data.

### `preview_data(source_path, sheet)`
Preview the contents of an Excel or CSV file before loading.

### `load_data(source_path, output_inp, column, series_name, sheet, freq, start_year, start_period)`
Load a time series from Excel or CSV and write a fue .inp file.

### `series_info(inp_path)`
Load a time series from an .inp file and return basic information.

## Etapa 1 — Identificación

### `guided_identification(inp_path, lam, d, D, pre_path)`
Sequential identification — ONE decision node per call.

### `boxcox_analysis(inp_path)`
Analyse Box-Cox transformation for a time series (standalone use).

### `seasonal_analysis(inp_path)`
HAC F-test for seasonal patterns — support tool, standalone use only.

### `unit_root_analysis(inp_path, lam, max_d)`
ADF + KPSS unit root tests for d = 0, 1, ..., max_d — support tool.

### `identification_analysis(inp_path, d, D, lam)`
ACF/PACF identification listing + ARMA order suggestions — standalone use.

### `save_identification_report(inp_path, output_path, d, D, lam)`
Generate and save a full HTML identification report to disk.

## Etapa 2 — Estimación

### `confirm_and_estimate(inp_path, output_path, lam, d, D, p, q, n_harmonics, P, Q, base_pre_path, estimate_mu, include_histogram, guion_path, guion_name, guion_decision, guion_rationale, guion_problems, guion_next)`
Build the .inp for the confirmed spec, estimate and show diagnosis immediately.

### `estimate_and_diagnose(inp_path)`
Fit the model specified in an .inp file and run diagnosis.

### `model_equation_display(inp_path)`
Display the estimated model as two polynomial-operator equations.

### `model_histogram(inp_path)`
Show the residuals histogram with normal overlay for a fitted model.

## Etapa 3 — Diagnosis / intervención

### `preliminary_outlier_scan(inp_path, d, D, lam, threshold)`
Scan the differenced series for extreme observations BEFORE choosing ARMA orders.

### `intervention_analysis(inp_path, threshold)`
Detect extreme residuals and assess their impact on ACF/PACF and tests.

### `test_interventions(inp_path, alpha)`
Test H₀: ω=0 for every non-structural intervention in a fitted model.

### `suggest_intervention_form(inp_path, output_path, date, form, context_hint, include_histogram, guion_path, guion_name, guion_decision, guion_rationale, guion_problems, guion_next)`
Add an intervention to the .inp, re-estimate and show updated diagnosis.

### `overparameterization_analysis(inp_path, threshold)`
Check for over-parameterization by inspecting parameter correlation matrix.

## Etapa 4 — Contrastes formales

### `formal_tests(inp_path, run_meg)`
Run formal hypothesis tests on a fitted model.

### `seasonal_param_analysis(inp_path)`
Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars.

### `test_seasonal_simplification(inp_path, freq_list, alpha)`
Joint LR test for eliminating seasonal harmonics: H₀: cos_k = sin_k = 0.

## Construcción completa

### `build_model(inp_path, output_path, max_rounds, run_meg, lam, d, D, p, q, n_harmonics, decision, guion_path, guion_name, guion_decision, guion_rationale)`
Box-Jenkins-Treadway pipeline for a single series — autonomous or guided.

### `batch_build(inp_paths, output_dir, max_rounds, run_meg)`
Autonomous pipeline for multiple series. Builds one model per series.

## Versionado / guion

### `record_version(inp_path, guion_path, name, decision, rationale, problems_found, next_version)`
Load, fit and record a model version in guion.json.

### `export_guion(guion_path, output_html)`
Render guion.json to a self-contained, navigable HTML report.

### `compare_versions(inp_path_a, inp_path_b, lam_a, lam_b, guion_path)`
Compare two estimated models: spec diff, stats table, nested LR test.

## Previsión (FUF)

### `generate_forecast(inp_path, horizon, output_fuf_path, output_html)`
Generate L-step-ahead forecasts from a fitted model.

### `update_and_forecast(fuf_path, new_values, output_html, output_fuf_path, actual_dates)`
Append new observations to a fuf file and update the forecast.

## Informes / salida

### `full_report(inp_path, output_path, run_meg, intervention_threshold)`
Generate a complete HTML report for a fitted model and save it to disk.

### `sps_dashboard(sps_dir, output_dir)`
Generate a sequential prediction (SPS) dashboard for all series in a directory.

### `get_out_report(inp_path)`
Return the full fue .out ASCII report for an estimated model.
