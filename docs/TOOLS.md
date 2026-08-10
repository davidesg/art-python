# `art` — MCP tool reference

*Generated from the docstrings by `tools/gen_tools_md.py`. Do not edit by hand — edit the docstring.*

**35 tools.** In an MCP server the docstring is what the model reads, so this page and the instruction the model receives are the same text by construction.

---

| tool | what it answers |
|---|---|
| [`ar_factorization`](#ar-factorization) | Factorize the estimated AR operator(s) of a fitted model and identify |
| [`batch_build`](#batch-build) | Autonomous pipeline for multiple series. Builds one model per series. |
| [`boxcox_analysis`](#boxcox-analysis) | Analyse Box-Cox transformation for a time series (standalone use). |
| [`build_model`](#build-model) | Box-Jenkins-Treadway pipeline for a single series — autonomous or guided. |
| [`compare_versions`](#compare-versions) | Compare two estimated models: spec diff, stats table, nested LR test. |
| [`confirm_and_estimate`](#confirm-and-estimate) | Build the .inp for the confirmed spec, estimate and show diagnosis immediately. |
| [`create_inp`](#create-inp) | Create a .inp file from raw time series data. |
| [`estimate_and_diagnose`](#estimate-and-diagnose) | Fit the model specified in an .inp file and run diagnosis. |
| [`export_guion`](#export-guion) | Render guion.json to a self-contained, navigable HTML report. |
| [`formal_tests`](#formal-tests) | Run formal hypothesis tests on a fitted model. |
| [`full_report`](#full-report) | Generate a complete HTML report for a fitted model and save it to disk. |
| [`generate_forecast`](#generate-forecast) | Generate L-step-ahead forecasts from a fitted model. |
| [`get_out_report`](#get-out-report) | Return the full fue .out ASCII report for an estimated model. |
| [`guided_identification`](#guided-identification) | Sequential identification — ONE decision node per call. |
| [`identification_analysis`](#identification-analysis) | ACF/PACF identification listing + ARMA order suggestions — standalone use. |
| [`intervention_analysis`](#intervention-analysis) | Detect extreme residuals and assess their impact on ACF/PACF and tests. |
| [`load_data`](#load-data) | Load a time series from Excel or CSV and write a fue .inp file. |
| [`meg_frequency`](#meg-frequency) | MEG for ONE given seasonal frequency, evaluated on the CHAINED baseline. |
| [`meg_reformulate`](#meg-reformulate) | Reformulate the model for STOCHASTIC seasonality at frequency `freq`, after the |
| [`model_equation_display`](#model-equation-display) | Display the estimated model as two polynomial-operator equations. |
| [`model_histogram`](#model-histogram) | Show the residuals histogram with normal overlay for a fitted model. |
| [`overparameterization_analysis`](#overparameterization-analysis) | Check for over-parameterization by inspecting parameter correlation matrix. |
| [`preliminary_outlier_scan`](#preliminary-outlier-scan) | Scan the differenced series for extreme observations BEFORE choosing ARMA orders. |
| [`preview_data`](#preview-data) | Preview the contents of an Excel or CSV file before loading. |
| [`record_version`](#record-version) | Load, fit and record a model version in guion.json. |
| [`save_identification_report`](#save-identification-report) | Generate and save a full HTML identification report to disk. |
| [`seasonal_analysis`](#seasonal-analysis) | HAC F-test for seasonal patterns — support tool, standalone use only. |
| [`seasonal_param_analysis`](#seasonal-param-analysis) | Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars. |
| [`series_info`](#series-info) | Load a time series from an .inp file and return basic information. |
| [`sps_dashboard`](#sps-dashboard) | Generate a sequential prediction (SPS) dashboard for all series in a directory. |
| [`suggest_intervention_form`](#suggest-intervention-form) | Add an intervention to the .inp, re-estimate and show updated diagnosis. |
| [`test_interventions`](#test-interventions) | Test H₀: ω=0 for every non-structural intervention in a fitted model. |
| [`test_seasonal_simplification`](#test-seasonal-simplification) | Joint LR test for eliminating seasonal harmonics: H₀: cos_k = sin_k = 0. |
| [`unit_root_analysis`](#unit-root-analysis) | ADF + KPSS unit root tests for d = 0, 1, ..., max_d — support tool. |
| [`update_and_forecast`](#update-and-forecast) | Append new observations to a fuf file and update the forecast. |

---

## `ar_factorization`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `sper` | integer | no | `0` |

Factorize the estimated AR operator(s) of a fitted model and identify
    candidate seasonal AR_f factors.

    Each regular AR factor P(B) = 1 - c1 B - ... - cp B^p is factored (via
    numpy.roots) and characterized in the original ``Root`` format: the roots
    table and the real factors (1 - a[1] B) and complex factors
    (1 - a[1] B - a[2] B^2), each complex factor given its damping factor d, its
    frequency freq (cycles/obs) and its period per (obs/cycle).  For a
    directly-estimated AR(2) factor (both coefficients free), d and per carry
    delta-method standard errors (``d ± SE``, ``per ± SE``) from the factor's 2x2
    coefficient covariance — matching ABTreadway-Dperar2.xls / caracterizar_operadores.py.

    INTERPRETATION IS LEFT TO THE ASSISTANT: a complex factor whose period matches
    a seasonal cycle (per = s/k for an integer harmonic k) and whose damping d is
    near 1 is a candidate seasonal AR_f operator -- a stochastic-seasonal factor
    hidden inside an un-factored AR(p) -- to feed the MEG (DCD_f) and the dual
    Shin-Fuller AR_f test (paper SF_MEG, confirmatory pair). Because fue can
    estimate the AR operator factored or un-factored, factoring a freely estimated
    AR(p) exposes such factors.

    Parameters
    ----------
    inp_path : path to .inp or .pre file (fitted model)
    sper     : seasonal period; 0 (default) uses the series frequency

---

## `batch_build`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_paths` | array | yes | — |
| `output_dir` | string | yes | — |
| `max_rounds` | integer | no | `5` |
| `run_meg` | boolean | no | `False` |

Autonomous pipeline for multiple series. Builds one model per series.

    Calls build_model for each inp_path, saves individual .inp files and
    HTML diagnosis reports in output_dir. Returns a summary table and
    individual diagnosis figures.

    Parameters
    ----------
    inp_paths   : list of source .inp paths
    output_dir  : directory where output .inp files and HTML reports are saved
    max_rounds  : maximum intervention rounds per series (default 5)
    run_meg     : run MEG test (slow; default False)

---

## `boxcox_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Analyse Box-Cox transformation for a time series (standalone use).

    NOTE: in guided analysis use guided_identification instead — it integrates
    Box-Cox, the identification listing, unit-root tests and seasonality test
    in the correct order (listing first, tests as support).

    Computes the mean-std scatter for lambda=0 (log) and lambda=1 (identity),
    recommends the transformation, and returns the comparison figure.

    Parameters
    ----------
    inp_path : path to the .inp file

---

## `build_model`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | yes | — |
| `max_rounds` | integer | no | `5` |
| `run_meg` | boolean | no | `False` |
| `lam` | number | no | `-1.0` |
| `d` | integer | no | `-1` |
| `D` | integer | no | `-1` |
| `p` | integer | no | `-1` |
| `q` | integer | no | `-1` |
| `n_harmonics` | integer | no | `-1` |
| `decision` | string | no | `` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |

Box-Jenkins-Treadway pipeline for a single series — autonomous or guided.

    Runs ONE engine (pipeline.run_full): decides the spec, estimates, adds
    interventions for detected outliers and re-estimates until the diagnosis is
    clean or max_rounds. The only difference between modes is WHO supplies each
    decision:

      - Autonomous (all spec params left at their sentinel): the heuristic
        DefaultPolicy decides λ, d, D, harmonics, p, q.
      - Guided (any of lam/d/D/p/q/n_harmonics/decision provided): those
        analyst/Claude-confirmed choices are honoured (ClaudePolicy) and the
        heuristic fills only what was left unspecified. Use after
        guided_identification to run the build with the confirmed spec while
        the outlier cycle proceeds automatically.

    Always returns parameters + residual diagnosis figure; DCD/MEG at the end.

    Parameters
    ----------
    inp_path      : source .inp file — only the series is used
    output_path   : path for the final estimated .inp
    max_rounds    : maximum intervention-addition rounds (default 5)
    run_meg       : run MEG stochastic seasonality test (slow; default False)
    lam           : confirmed Box-Cox λ (0/0.5/1); -1 = let the heuristic decide
    d, D          : confirmed differencing orders; -1 = heuristic
    p, q          : confirmed ARMA orders; -1 = heuristic
    n_harmonics   : confirmed cos/sin pairs (B1); -1 = heuristic
    decision      : confirmed "A"/"B1"/"B2"; "" = heuristic
    guion_path    : (optional) path to guion.json — records the final model
    guion_name    : version name (e.g. "PC1"); auto-assigned if empty
    guion_decision: brief description of the model or pipeline result
    guion_rationale: justification for the spec

---

## `compare_versions`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path_a` | string | yes | — |
| `inp_path_b` | string | yes | — |
| `lam_a` | number | no | `0.0` |
| `lam_b` | number | no | `0.0` |
| `guion_path` | string | no | `` |

Compare two estimated models: spec diff, stats table, nested LR test.

    Loads and fits both .inp files. Returns:
    - Spec comparison (what parameters changed)
    - Side-by-side stats: loglik, AIC, BIC, σ_a, Q-pass, JB-pass
    - Nested LR test if one model is a restricted version of the other
    - ACF/PACF comparison figure (residuals of both models)

    Parameters
    ----------
    inp_path_a  : .inp file for model A (baseline / more restricted)
    inp_path_b  : .inp file for model B (alternative / richer)
    lam_a       : Box-Cox lambda for model A (0.0 = log)
    lam_b       : Box-Cox lambda for model B (0.0 = log)
    guion_path  : (optional) guion.json — unused currently, reserved

---

## `confirm_and_estimate`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | yes | — |
| `lam` | number | no | `0.0` |
| `d` | integer | no | `1` |
| `D` | integer | no | `0` |
| `p` | integer | no | `0` |
| `q` | integer | no | `1` |
| `n_harmonics` | integer | no | `5` |
| `P` | integer | no | `0` |
| `Q` | integer | no | `0` |
| `base_pre_path` | string | no | `` |
| `estimate_mu` | boolean | no | `False` |
| `seasonal` | — | no | `None` |
| `include_histogram` | boolean | no | `False` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |
| `guion_problems` | string | no | `` |
| `guion_next` | string | no | `` |

Build the .inp for the confirmed spec, estimate and show diagnosis immediately.

    Two modes:
    - Fresh model (base_pre_path=""): constructs from scratch using series in
      inp_path and the analyst-confirmed (lam, d, D, p, q, P, Q) spec.
    - Incremental (base_pre_path=<.pre>): loads all existing interventions and
      harmonics from the .pre, then replaces/adds only the ARMA part (p, q,
      P, Q) and mu. Use this to add ARMA to a model after the outlier cycle.

    Always returns:
      - Parameter table with SE and t-stats
      - Diagnosis verdict (Q-test, JB, outliers)
      - Residual ACF/PACF + histogram

    Parameters
    ----------
    inp_path        : source .inp/.pre (series data and name; spec ignored
                      unless base_pre_path is given)
    output_path     : path to write the new .inp
    lam             : Box-Cox lambda (0.0=log, 1.0=identity)
    d               : regular differencing order
    D               : seasonal differencing order (0=B1 harmonics, 1=B2 multiplicative)
    p               : regular AR order
    q               : regular MA order
    n_harmonics     : harmonic pairs cos/sin (D=0 fresh only; ignored when
                      base_pre_path is given — harmonics come from the .pre)
    seasonal        : on/off switch for the whole deterministic seasonal package
                      (cos/sin pairs + Nyquist alter). None (default) => derive from
                      n_harmonics>0, correct for freq>=4. Pass False for a
                      NON-seasonal series (no seasonal terms at all — avoids the
                      spurious Nyquist of BUG-0005). Pass True for a SEMI-ANNUAL
                      seasonal series (freq=2), whose only seasonal term is the
                      Nyquist alter while n_harmonics (pairs) is 0.
    P               : seasonal AR order (D=1 only)
    Q               : seasonal MA order (D=1 only)
    base_pre_path   : if given, load interventions+harmonics from this .pre and
                      add only the ARMA spec. Typical use: final ARMA step after
                      outlier cycle in B1 flow.
    estimate_mu     : include mean parameter μ in estimation (default False).
                      Set True when μ̄/SE > 2 in the residuals of the clean model.
    include_histogram : return histogram PNG as third item (default False).
                      Keep False during the outlier cycle to save tokens; set True
                      for the final model only.
    guion_path      : (optional) path to guion.json — records this version
    guion_name      : version name (e.g. "PC3"); auto-assigned if empty
    guion_decision  : brief description of what this model tests or concludes
    guion_rationale : justification for the choices made
    guion_problems  : problems found in the diagnosis of this model
    guion_next      : description of the next version to try

---

## `create_inp`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `data` | array | yes | — |
| `output_path` | string | yes | — |
| `name` | string | no | `series` |
| `freq` | integer | no | `12` |
| `start_year` | integer | no | `2000` |
| `start_period` | integer | no | `1` |

Create a .inp file from raw time series data.

    This is the FIRST tool to call when the user provides data from a
    spreadsheet, CSV, or any source other than an existing .inp file.
    The .inp produced is a minimal data container (no model structure) ready
    for boxcox_analysis, guided_identification, and the full guided workflow.

    Parameters
    ----------
    data         : list of numeric observations in chronological order
    output_path  : path where the .inp file will be written (e.g. ~/data/IPC.inp)
    name         : series name (e.g. "IPC", "PCE", "GDP")
    freq         : observation frequency — 1=annual, 4=quarterly, 12=monthly
    start_year   : year of the first observation (e.g. 2003)
    start_period : period of the first observation, 1-based
                   (month 1-12 for monthly; quarter 1-4 for quarterly; 1 for annual)

    Returns
    -------
    Confirmation string with the path, series name, n, freq, and start date.

---

## `estimate_and_diagnose`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | no | `` |

Fit the model specified in an .inp file and run diagnosis.

    Estimates the model by maximum likelihood (fue MVENC) and runs the
    full diagnosis: standardised residuals, ACF/PACF, Ljung-Box Q-test,
    Jarque-Bera normality test, and residual seasonality check.

    Parameters
    ----------
    inp_path    : path to the .inp file with the model specification
    output_path : if given, also persist the fitted model as the ``.pre``
                  (= .inp with the estimated parameters, to seed the next step)
                  and ``.out`` (ASCII results report) alongside this basename —
                  the same trio confirm_and_estimate writes, so a model estimated
                  through this clean path is not left without artefacts.  Empty
                  (default) keeps the old screen-only behaviour.

---

## `export_guion`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_path` | string | yes | — |
| `output_html` | string | yes | — |

Render guion.json to a self-contained, navigable HTML report.

    Generates a single HTML file with:
    - Summary table of all versions (loglik, AIC, BIC, Q✓, JB✓, anomalías)
    - One collapsible section per version with equation, spec, stats, figure,
      decision notes, and link to next version

    Parameters
    ----------
    guion_path  : path to guion.json
    output_html : path to write the .html file

---

## `formal_tests`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `run_meg` | boolean | no | `True` |

Run formal hypothesis tests on a fitted model.

    ⚠ MARCA ESTA RUTA COMO (EXPERIMENTAL) — Y SI TE PREGUNTAN QUÉ SIGNIFICA,
      EXPLÍCALO BIEN, PORQUE NO ES LO QUE PARECE.

    QUÉ ESTÁ PUBLICADO Y ESTABLECIDO (casi todo):
      · los MODELOS son antiguos: Abraham y Box (1978).
      · la IDEA de resolver la estacionalidad frecuencia por frecuencia está en
        HEGY (Hylleberg, Engle, Granger y Yoo).
      · el contraste DCD (Davis, Chen y Dunsmuir) está PUBLICADO.
      · el Shin-Fuller está PUBLICADO.

    QUÉ ES NUEVO (poco, y menos de lo que "experimental" sugiere):
      · los VALORES CRÍTICOS derivados por Monte Carlo, que difieren por un
        margen MARGINAL de los interpolados que están publicados.
      · y, sobre todo, LA IMPLEMENTACIÓN DE ART -- que es donde están los tres
        defectos abiertos de abajo. Eso es lo realmente nuevo aquí.

    Así que "(experimental)" es una SALVAGUARDIA, no una advertencia de que el
    método sea dudoso. El método está establecido; lo que aún no está avalado
    es esta implementación y el último decimal de los críticos.

    NOMBRE: la clase se llama HSM --Hybrid Seasonal Models-- que es como la
    nombra el artículo de referencia (SF_MEG). `MEG`, Modelos de Estacionalidad
    Generalizada (Gallego, 1995), es su nombre en la literatura española y el
    identificador que conserva el código; en prosa, di HSM.

    LAS DOS LÍNEAS DE ESTACIONALIDAD son:
      · DETERMINISTA   armónicos con coeficientes de previsión fijos
      · ESTOCÁSTICA    SARIMA multiplicativo, la diferencia anual 1-B^s entera

    HSM no es una tercera línea: es la FORMA CANÓNICA de Abraham y Box (1978),
    en la que cada frecuencia es independientemente una u otra, y que anida las
    dos líneas como casos especiales. Ellos ya distinguen componentes
    deterministas de "forecast-adaptive" y notan que un modelo puede ser
    adaptativo en unos parámetros y no en otros. ESA RUTA ES LA EXPERIMENTAL.

    Los tres defectos ABIERTOS y reproducidos de la implementación, todos en
    esta familia:

      BUG-0009  dcd_overdiff_regular pisa el testigo de Nyquist --comparten la
                ranura de MA regular y miden raíces OPUESTAS (B=+1 frente a
                B=-1)-- y recomienda d+1 sobre una d correcta.
      BUG-0010  podar un armónico no significativo anula el barrido MEG
                ENTERO, la excepción se traga, y el informe cierra diciendo
                que el modelo es adecuado mientras se pierde una frecuencia
                genuinamente estocástica.
      BUG-0011  dcd_overdiff_regular recomienda d+1 en toda especificación de
                un índice de precios, incluida la línea base que su propio
                docstring prescribe. Causa establecida: los armónicos
                deterministas compiten con el testigo, y la precondición del
                docstring nombra al competidor equivocado.

    PUEDES OFRECERLA. Preguntar al analista si quiere evaluar la NATURALEZA de
    la estacionalidad --determinista o estocástica, frecuencia por frecuencia--
    es una pregunta legítima y hay analistas que la quieren siempre. Ofrécela
    marcada "(experimental)", no como el camino por defecto.

    Lo que sí: no tomes una decisión de especificación apoyándote SÓLO en ella.
    Contrástala con Shin-Fuller y con la acf/pacf, y si el veredicto contradice
    al resto del informe, hoy es más probable que el fallo esté en esta
    implementación que en los otros instrumentos.

    Tests run (where applicable to the model structure):
    - Shin-Fuller (1998): Phi_1u test; H0: rho=1-4/n (near-unit-root); crit 5%≈1.75
    - DCD: non-invertibility of regular MA factors (H0: theta=1)          [exper.]
    - DCD_f: non-invertibility of seasonal MA factors (H0: lambda2=-1)    [exper.]
    - RV: fixed frequency for AR(2) factors
    - MEG: HSM sweep — stochastic vs deterministic seasonality, frequency by
      frequency (requires D=0 + harmonics). `meg` is the API name; the class is
      HSM (Hybrid Seasonal Models).                                       [exper.]

    Parameters
    ----------
    inp_path : path to .inp or .pre file
    run_meg  : whether to run MEG (slow, default True; EXPERIMENTAL, see above)

---

## `full_report`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | yes | — |
| `run_meg` | boolean | no | `True` |
| `intervention_threshold` | number | no | `3.5` |

Generate a complete HTML report for a fitted model and save it to disk.

    The report is a self-contained HTML file with collapsible sections:
    1. Estimated model (parameters, SE, t-stats, AIC/BIC)
    2. Diagnosis (residuals, ACF/PACF, Q-test, Jarque-Bera)
    3. Formal tests (DCD, DCD_f, RV, MEG where applicable)
    4. Interventions (extreme residuals and ACF distortion warnings)

    Parameters
    ----------
    inp_path             : path to .inp or .pre file
    output_path          : path for the HTML output file
    run_meg              : run MEG test (default True, only if D=0 + harmonics)
    intervention_threshold : |z| threshold for outlier warnings (default 3.5)

---

## `generate_forecast`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `horizon` | integer | yes | — |
| `output_fuf_path` | string | yes | — |
| `output_html` | string | yes | — |

Generate L-step-ahead forecasts from a fitted model.

    Loads the model from inp_path (fitted .pre), computes forecasts, writes a
    fuf file to output_fuf_path for future updates, and writes the full
    Treadway/Jenkins HTML forecast report (tables + charts) to output_html.

    Parameters
    ----------
    inp_path        : fitted model file (.pre)
    horizon         : number of periods ahead to forecast (e.g. 24)
    output_fuf_path : path to write the fuf input file (for update_and_forecast)
    output_html     : path to write the fue HTML forecast report (required)

---

## `get_out_report`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Return the full fue .out ASCII report for an estimated model.

    Produces the same output as the C 'fue' binary: parameter estimates with
    standard errors, AR/MA polynomials, sigma, log-likelihood, AIC/BIC,
    correlation matrix, residual statistics, outlier table, and ACF of residuals.

    Useful for detailed review of the estimated model beyond what the diagnosis
    summary shows.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the model specification

---

## `guided_identification`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `lam` | number | no | `-1.0` |
| `d` | integer | no | `-1` |
| `D` | integer | no | `-1` |
| `pre_path` | string | no | `` |

Sequential identification — ONE decision node per call.

    DECISION TREE — call in this sequence, one at a time:

    Call 1  lam=-1  (default)
      → Box-Cox scatter. Decide λ. WAIT for user.

    Call 2  lam=X  d=-1  (default)
      → Series(λ) + ACF/PACF at level d=0.
        ¿Trend? → next call with d=1.
        ¿No trend? → next call with d=0, D confirmed.
        Support: unit_root_analysis available if needed.
      WAIT for user.

    Call 3  lam=X  d=<level>  D=-1
      → Series(λ) differenced d times + ACF/PACF + HAC seasonality.
        Seasonal? + B1 (deterministic seasonality: harmonics, D=0):
          Confirm d and D=0, then:
            a) confirm_and_estimate(m00: harmonics only, p=0, q=0)
            b) preliminary_outlier_scan on m00 residuals
            c) [cycle: add steps → re-estimate → scan] until clean
            d) Call 4 with pre_path=<mNN.pre> (ARMA on clean residuals)
        Seasonal? + B2 (stochastic seasonality: seasonal differencing, D=1):
          → Call 4 with lam, d, D=1 (ARMA+P+Q on ∇∇_s series)
        ¿No seasonality? → D=0, no harmonics, Call 4 directly.
      WAIT for user to confirm d and D.

    Call 4  lam=X  d=<confirmed>  D=<confirmed>  [pre_path=<.pre>]
      B1 path (D=0, pre_path given):
        → ACF/PACF of clean model RESIDUALS from pre_path.
          PACF cuts → AR(p).  ACF cuts → MA(q).
          Also: mean significant? (μ̄/SE > 2) → estimate_mu=True
      B2 path (D=1, no pre_path):
        → ACF/PACF of ∇^d ∇_s y(λ).
          Also check lags s,2s,3s for seasonal P and Q.
      B1 no-outliers (D=0, no pre_path):
        → ACF/PACF of ∇^d y(λ) directly.
      WAIT for user to confirm p, q (and P, Q if D=1).

    Parameters
    ----------
    inp_path : path to series .inp file (all calls)
    lam      : Box-Cox lambda  (-1 = not yet decided → Call 1)
    d        : differencing order (-1 = not yet decided → Call 2)
    D        : seasonal differencing (-1 = not yet decided → Call 3)
    pre_path : path to fitted .pre (Call 4, B1): ARMA identified on
               its residuals instead of the raw transformed series.

---

## `identification_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `d` | integer | no | `2` |
| `D` | integer | no | `0` |
| `lam` | number | no | `0.0` |

ACF/PACF identification listing + ARMA order suggestions — standalone use.

    NOTE: in guided analysis use guided_identification instead:
      - Call 1 (lam=-1): shows Box-Cox + listing (d=0,1,2) + unit-root + HAC
      - Call 2 (lam confirmed): shows ACF/PACF of ∇^d ∇_s^D y_t + suggestions
    identification_analysis is called internally by guided_identification.

    Compares the empirical ACF/PACF of the differenced series with theoretical
    ACF/PACF of candidate ARIMA models. Returns top-5 suggestions by similarity.

    Parameters
    ----------
    inp_path : path to the .inp file (series is used, model spec ignored)
    d        : regular differencing order (default 2)
    D        : seasonal differencing order (default 0)
    lam      : Box-Cox lambda (0.0=log, 1.0=identity, default 0.0)

---

## `intervention_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `threshold` | number | no | `3.5` |

Detect extreme residuals and assess their impact on ACF/PACF and tests.

    Identifies residuals with |z| > threshold and reports:
    - Date and standardised z-value of each extreme observation
    - Fraction of total variance explained (global ACF/PACF compression)
    - ACF lags most affected by the outlier's pair-contribution
    - Whether Jarque-Bera and Ljung-Box Q are unreliable

    Parameters
    ----------
    inp_path  : path to .inp or .pre file
    threshold : |z| threshold for flagging extremes (default 3.5)

---

## `load_data`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `source_path` | string | yes | — |
| `output_inp` | string | yes | — |
| `column` | string | yes | — |
| `series_name` | string | no | `` |
| `sheet` | string | no | `` |
| `freq` | integer | no | `0` |
| `start_year` | integer | no | `0` |
| `start_period` | integer | no | `1` |

Load a time series from Excel or CSV and write a fue .inp file.

    If the file has a date index (DatetimeIndex), freq and start are inferred
    automatically. If not, you must provide freq, start_year and start_period.

    Parameters
    ----------
    source_path  : path to .xlsx, .xls, .ods or .csv file
    output_inp   : path for the output .inp file (e.g. "cases/IPC_ES/IPC_ES.inp")
    column       : column name to extract (exact match or 0-based integer index)
    series_name  : name for the series in the .inp (default: column name)
    sheet        : sheet name for Excel (default: first sheet)
    freq         : 1=annual, 4=quarterly, 12=monthly  (0 = auto-detect from dates)
    start_year   : start year if no date index (0 = auto-detect)
    start_period : start period within year if no date index (1-based)

---

## `meg_frequency`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `freq` | integer | yes | — |
| `base_pre_path` | string | no | `` |

MEG for ONE given seasonal frequency, evaluated on the CHAINED baseline.

    Unlike `formal_tests` (which sweeps all frequencies), this runs the MEG /
    DCD_f contrast for exactly one frequency `freq`, ON TOP of the supplied
    baseline model — its AR/AR_s, μ, interventions and the OTHER harmonics are
    all kept. This is the correct chained MEG: from the baseline (e.g. harmonics
    + seasonal AR(1) + μ) it reformulates only f as stochastic (ifadf[freq]=1:
    the AR_f unit root 1−2cos(ω)B+B² for an interior f, or 1+B at the Nyquist;
    removes f's cos/sin harmonics; adds the free invertible MA_f testigo), then
    fits the free and the constrained (λ₂=−1) models and reports the DCD_f LR:

      LR = 2·[logL(free) − logL(λ₂=−1)]
      LR > crit  ⇒ witness invertible, seasonal unit root genuine ⇒ STOCHASTIC.
      LR ≤ crit  ⇒ witness at −1, cancels the AR_f unit root       ⇒ DETERMINISTIC.

    The witness coef is reported as the INVERTIBLE estimate (the engine flips
    |θ₂|>1 → 1/θ₂ inside the likelihood). If STOCHASTIC, adopt the form with
    `meg_reformulate(freq=…, base_pre_path=<this baseline>)`.

    Parameters
    ----------
    inp_path      : source .inp/.pre (series data; also the model if base_pre_path="")
    freq          : the single seasonal frequency to test (1..s/2)
    base_pre_path : the baseline .pre (AR_s+μ+harmonics); if empty, uses inp_path

---

## `meg_reformulate`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `freq` | integer | yes | — |
| `output_path` | string | yes | — |
| `base_pre_path` | string | no | `` |
| `with_witness` | boolean | no | `True` |

Reformulate the model for STOCHASTIC seasonality at frequency `freq`, after the
    MEG (DCD_f / Shin-Fuller AR_f) has concluded stochastic there.

    Builds the model the MEG recommends, FROM THE LAST .pre, without editing files by
    hand. It loads the last fitted model (base_pre_path if given, else inp_path),
    activates the seasonal AR_f unit root at `freq` (ifadf[freq]=1: the operator
    1-2cos(w)B+B^2 for an interior frequency, or 1+B at the Nyquist f=s/2), removes the
    now-annihilated deterministic harmonics at `freq`, re-estimates, writes the
    reformulated .pre/.out to output_path and shows the model equation + diagnosis.

    with_witness=True (DEFAULT) also adds the free invertible MA_f testigo
    (1-2λcos(w)B+λ²B²), so the reformulated model is EXACTLY what the MEG/DCD_f
    contrasts — the AR_f unit root AND the MA_f witness together. This is the correct
    stochastic model S. After fitting, run `formal_tests` to read the witness DCD_f:
    LR>crit ⇒ genuine stochastic; λ→boundary (−1) ⇒ quasi-cancellation (frontier).

    with_witness=False gives the AR-only form (no witness): this OVER-DIFFERENCES the
    seasonal (inflated σ, exploded Q-test) and is only a diagnostic subproduct, NOT S.
    Use it only to inspect the bare over-differenced residuals.

    Multiple stochastic frequencies: call iteratively (strongest first), passing the
    previous output's .pre as base_pre_path, re-running formal_tests after each — the
    per-frequency MEG on the all-deterministic model has cross-frequency contamination.

    Parameters
    ----------
    inp_path      : source .inp/.pre (series data; also the model if base_pre_path="")
    freq          : seasonal frequency to make stochastic (1..s/2)
    output_path   : path to write the reformulated model (.pre/.out alongside)
    base_pre_path : the last .pre (the deterministic model); if empty, uses inp_path
    with_witness  : add the free MA_f testigo (default True → the correct S model)

---

## `model_equation_display`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Display the estimated model as two polynomial-operator equations.

    Shows the two-equation B-J-T form with estimated parameters and SE aligned
    below each coefficient (equivalent to the \est{}{} LaTeX macro in the thesis).

    Equation 1 (level):  [transform] yₜ = Dₜ + Nₜ
      Dₜ shows all deterministic components: interventions, harmonics, mean.

    Equation 2 (noise):  ∇ᵈ∇ₛᴰ φ(B) Nₜ = θ(B) aₜ
      Polynomial operator form for the ARIMA stochastic model.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model

---

## `model_histogram`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Show the residuals histogram with normal overlay for a fitted model.

    Optional complement to the basic Treadway diagnostic module
    (estimate_and_diagnose / confirm_and_estimate).  The histogram is not
    part of the basic diagnostic module — request it explicitly when you
    want to inspect the distributional shape of the residuals.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model

---

## `overparameterization_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `threshold` | number | no | `0.7` |

Check for over-parameterization by inspecting parameter correlation matrix.

    Computes the correlation matrix of all estimated parameters from the
    covariance matrix returned by fue (MVENC).  Parameter pairs with
    |corr| > threshold are flagged as potentially redundant.

    The correlation matrix is shown as a colour heatmap with the ARMA/mu
    block highlighted.  High-correlation pairs are listed with labels and
    a note on whether the high correlation is structural (expected) or
    indicates true redundancy.

    Run this after estimate_and_diagnose if the diagnosis text mentions
    sobreparametrización, or as a routine check before finalising the model.

    Parameters
    ----------
    inp_path  : path to .inp or .pre file with the estimated model
    threshold : |corr| threshold for flagging (default 0.7)

---

## `preliminary_outlier_scan`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `d` | integer | yes | — |
| `D` | integer | yes | — |
| `lam` | number | no | `0.0` |
| `threshold` | number | no | `3.5` |

Scan the differenced series for extreme observations BEFORE choosing ARMA orders.

    "Lo más obvio primero": a large outlier in the differenced series distorts
    ACF/PACF coefficients (subestimated due to inflated variance). Treating the
    outlier BEFORE identification gives cleaner, more informative ACF/PACF.

    Returns the standardised ∇ᵈ∇ᴰ series with ±2σ bands and outliers marked,
    plus a recommendation on whether to add interventions before identifying (p, q).

    Parameters
    ----------
    inp_path  : path to the .inp file
    d         : confirmed regular differencing order
    D         : confirmed seasonal differencing order
    lam       : confirmed Box-Cox lambda (0.0=log, 1.0=identity)
    threshold : |z| threshold for flagging extremes (default 3.5)

---

## `preview_data`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `source_path` | string | yes | — |
| `sheet` | string | no | `` |

Preview the contents of an Excel or CSV file before loading.

    Lists available sheets (Excel), column names, number of rows, detected
    date range and frequency. Use this before load_data to choose the right
    column and confirm that dates are parsed correctly.

    Parameters
    ----------
    source_path : path to .xlsx, .xls, or .csv file
    sheet       : sheet name (Excel only; default = first sheet)

---

## `record_version`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `guion_path` | string | yes | — |
| `name` | string | no | `` |
| `decision` | string | no | `` |
| `rationale` | string | no | `` |
| `problems_found` | string | no | `` |
| `next_version` | string | no | `` |

Load, fit and record a model version in guion.json.

    Loads the model from inp_path, fits it, extracts stats (loglik, AIC, BIC,
    Q-test, JB-test, extreme residuals) and appends an entry to guion.json.
    Creates guion.json if it does not exist.

    Parameters
    ----------
    inp_path       : .inp file with the estimated model
    guion_path     : path to guion.json (created if absent)
    name           : version name, e.g. "PC3"; auto-assigned ("PC{n}") if empty
    decision       : brief note on what this model tests or concludes
    rationale      : justification for the parameter choices
    problems_found : problems detected in the diagnosis
    next_version   : description of the next version to try

---

## `save_identification_report`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | yes | — |
| `d` | integer | no | `2` |
| `D` | integer | no | `0` |
| `lam` | number | no | `0.0` |

Generate and save a full HTML identification report to disk.

    The report contains the ACF/PACF listing for the differenced series
    (for d=0,1,2 or with seasonal differencing) and the top-5 ARMA order
    suggestions ranked by pattern similarity.

    Parameters
    ----------
    inp_path    : path to the .inp file (series is used, model spec ignored)
    output_path : path for the HTML output file
    d           : regular differencing order (default 2)
    D           : seasonal differencing order (default 0)
    lam         : Box-Cox lambda (0.0=log, 1.0=identity, default 0.0)

---

## `seasonal_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

HAC F-test for seasonal patterns — support tool, standalone use only.

    NOTE: in guided analysis use guided_identification instead — seasonal_analysis
    is a support tool called internally after the identification listing.

    Tests all harmonic frequencies using a joint F-test with HAC Newey-West
    standard errors. Returns the seasonality plot and a recommendation for D.

    Parameters
    ----------
    inp_path : path to the .inp file

---

## `seasonal_param_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars.

    For each harmonic k=1..freq//2 present in the model, reports:
    - cos_k and sin_k coefficients with SE and t-ratio
    - Amplitude A_k = sqrt(cos_k² + sin_k²)
    - Which harmonics are significant (|t| > 2) and which could be dropped

    Bar chart figure: two panels (cos coefficients | sin coefficients),
    colour-coded by significance.

    Parameters
    ----------
    inp_path : path to a fitted .inp or .pre file

---

## `series_info`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |

Load a time series from an .inp file and return basic information.

    Parameters
    ----------
    inp_path : path to the .inp file

    Returns basic metadata: name, n, frequency, start date, Box-Cox lambda,
    differencing orders (d, D), ARMA structure.

---

## `sps_dashboard`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `sps_dir` | string | yes | — |
| `output_dir` | string | yes | — |

Generate a sequential prediction (SPS) dashboard for all series in a directory.

    Scans sps_dir for fuf .inp files, generates a fue HTML forecast report
    for each series in output_dir, and writes an index.html with a summary
    table linking to the per-series reports.

    Parameters
    ----------
    sps_dir    : directory containing fuf .inp files (one per series)
    output_dir : directory to write per-series HTML reports and index.html

---

## `suggest_intervention_form`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `output_path` | string | yes | — |
| `date` | string | no | `` |
| `form` | string | no | `auto` |
| `context_hint` | string | no | `` |
| `include_histogram` | boolean | no | `False` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |
| `guion_problems` | string | no | `` |
| `guion_next` | string | no | `` |

Add an intervention to the .inp, re-estimate and show updated diagnosis.

    Adds a pulse, step or ramp intervention at the given date, saves to
    output_path, re-estimates and returns the updated parameter table and
    diagnosis. Use this iteratively — one intervention at a time.

    Parameters
    ----------
    inp_path          : current .inp/.pre (with any previous interventions)
    output_path       : path to write the updated .inp
    date              : observation date "MM/YYYY" or "QN/YYYY" or "YYYY".
                        Leave empty ("") to auto-select the most extreme residual.
    form              : "pulse", "step", "ramp" or "auto" (heuristic)
    context_hint      : free-text note about the economic event (for logging)
    include_histogram : return histogram PNG (default False — saves tokens
                        during the outlier cycle; set True for final round)
    guion_path        : (optional) path to guion.json — records this version
    guion_name        : version name (e.g. "PC3"); auto-assigned if empty
    guion_decision    : brief description of what this model tests or concludes
    guion_rationale   : justification for the intervention choice
    guion_problems    : problems found in the diagnosis
    guion_next        : description of the next version to try

---

## `test_interventions`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `alpha` | number | no | `0.05` |

Test H₀: ω=0 for every non-structural intervention in a fitted model.

    Runs a t-test on each free omega parameter of pulse, step, ramp, and
    similar interventions (cosine/sine harmonics and alter are structural
    and skipped by default). Identifies which interventions are non-significant
    and can be removed to simplify the model.

    For interventions with a transfer function (delta ≠ 0), also computes
    a Wald joint test H₀: g = α·ω = 0.

    Parameters
    ----------
    inp_path : path to a fitted .inp or .pre file
    alpha    : significance level for classification (default 0.05)

---

## `test_seasonal_simplification`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `freq_list` | — | no | `None` |
| `alpha` | number | no | `0.05` |

Joint LR test for eliminating seasonal harmonics: H₀: cos_k = sin_k = 0.

    Fits a restricted model with the specified harmonics fixed to zero and
    computes LR = 2·(L_free − L_restricted) ~ χ²(df), where df = number of
    constrained parameters (2 per regular harmonic, 1 for Nyquist/alter).

    Typical workflow after seasonal_param_analysis:
    - Pass the k values with |t| ≤ 2 in both cos and sin as freq_list.
    - If LR < χ²(df, 5%): safely remove those harmonics and refit.
    - If LR ≥ χ²(df, 5%): the harmonics are jointly significant — keep them.

    Parameters
    ----------
    inp_path  : path to a fitted .inp or .pre file
    freq_list : harmonic indices to test (None = test all harmonics jointly)
    alpha     : significance level (default 0.05)

---

## `unit_root_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `lam` | number | no | `0.0` |
| `max_d` | integer | no | `2` |

ADF + KPSS unit root tests for d = 0, 1, ..., max_d — support tool.

    NOTE: in guided analysis use guided_identification instead — unit_root_analysis
    is a support tool called internally after the identification listing.

    Exploratory tool for the starting value of d. NOT a formal hypothesis test —
    for formal testing on an estimated model use formal_tests (Shin-Fuller 1998).

    Parameters
    ----------
    inp_path : path to the .inp file
    lam      : Box-Cox lambda (0.0 = log, 1.0 = none)
    max_d    : highest differencing order to test (default 2)

---

## `update_and_forecast`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `fuf_path` | string | yes | — |
| `new_values` | array | yes | — |
| `output_html` | string | yes | — |
| `output_fuf_path` | string | no | `` |
| `actual_dates` | array | no | `[]` |

Append new observations to a fuf file and update the forecast.

    Loads the fuf file, appends new_values to the series, re-runs the
    forecast (fixed parameters), compares actual observations against the
    previous forecast to report tracking errors, and writes the updated
    Treadway/Jenkins HTML report to output_html.

    Parameters
    ----------
    fuf_path         : existing fuf .inp file (from generate_forecast)
    new_values       : list of new observations in original scale
    output_html      : path to write the fue HTML forecast report (required)
    output_fuf_path  : where to save the updated fuf file (default: overwrites fuf_path)
    actual_dates     : (optional) date labels for new observations ("MM/YYYY")

---
