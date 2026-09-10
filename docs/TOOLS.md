# `art` — MCP tool reference

*Generated from the docstrings by `tools/gen_tools_md.py`. Do not edit by hand — edit the docstring.*

**46 tools.** In an MCP server the docstring is what the model reads, so this page and the instruction the model receives are the same text by construction.

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
| [`guided_intervention`](#guided-intervention) | Sequential INTERVENTION — ONE decision node per call. |
| [`guion_abandon`](#guion-abandon) | Mark a version as a DEAD END, with the reason — and cascade to what descends |
| [`guion_diff`](#guion-diff) | Compare two analyses NODE BY NODE, with the reasoning of each side. |
| [`guion_evidencia`](#guion-evidencia) | La EVIDENCIA de un nodo del guion: ecuación, diagnosis y figuras. |
| [`guion_map`](#guion-map) | Show the analysis as a MAP: what descends from what, what was adopted, and |
| [`guion_node`](#guion-node) | Record a DECISION NODE in the guion — a specification choice, not a model. |
| [`identification_analysis`](#identification-analysis) | ACF/PACF identification listing + ARMA order suggestions — standalone use. |
| [`incident_configurations`](#incident-configurations) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`intervention_analysis`](#intervention-analysis) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`intervention_ladder`](#intervention-ladder) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`intervention_plot`](#intervention-plot) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`load_data`](#load-data) | Load a time series from Excel or CSV and write a fue .inp file. |
| [`meg_frequency`](#meg-frequency) | MEG for ONE given seasonal frequency, evaluated on the CHAINED baseline. |
| [`meg_reformulate`](#meg-reformulate) | Reformulate the model for STOCHASTIC seasonality at frequency `freq`, after the |
| [`model_equation_display`](#model-equation-display) | Display the estimated model as two polynomial-operator equations. |
| [`model_histogram`](#model-histogram) | Show the residuals histogram with normal overlay for a fitted model. |
| [`overparameterization_analysis`](#overparameterization-analysis) | Check for over-parameterization by inspecting parameter correlation matrix. |
| [`preliminary_outlier_scan`](#preliminary-outlier-scan) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`preview_data`](#preview-data) | Preview the contents of an Excel or CSV file before loading. |
| [`record_version`](#record-version) | Load, fit and record a model version in guion.json. |
| [`residual_episodes`](#residual-episodes) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`residual_outlier_scan`](#residual-outlier-scan) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
| [`save_identification_report`](#save-identification-report) | Generate and save a full HTML identification report to disk. |
| [`seasonal_analysis`](#seasonal-analysis) | HAC F-test for seasonal patterns — support tool, standalone use only. |
| [`seasonal_param_analysis`](#seasonal-param-analysis) | Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars. |
| [`series_info`](#series-info) | Load a time series from an .inp file and return basic information. |
| [`sps_dashboard`](#sps-dashboard) | Generate a sequential prediction (SPS) dashboard for all series in a directory. |
| [`suggest_intervention_form`](#suggest-intervention-form) | Add an intervention to the .inp, re-estimate and show updated diagnosis. |
| [`test_interventions`](#test-interventions) | **Instrumento suelto del nodo de intervención.** La secuencia completa |
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
| `objetivo` | string | no | `univariante` |

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
    objetivo    : what the models are FOR -- "univariante" | "multivariante" |
                  "estructural". Applies to EVERY series in the batch, and that
                  is the point: a batch destined for a system (VECM, transfer
                  function, VARMA) must carry `objetivo="multivariante"`, which
                  vetoes the D=1 route so the series share one seasonal
                  treatment and their integration orders stay comparable.
                  Letting each series pick its own best-fitting route is what
                  produces a batch that cannot be assembled.

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
| `con_figuras` | boolean | no | `False` |
| `run_meg` | boolean | no | `False` |
| `lam` | number | no | `-1.0` |
| `d` | integer | no | `-1` |
| `D` | integer | no | `-1` |
| `p` | integer | no | `-1` |
| `q` | integer | no | `-1` |
| `n_harmonics` | integer | no | `-1` |
| `estimate_mu` | integer | no | `-1` |
| `domain` | string | no | `` |
| `decision` | string | no | `` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |
| `objetivo` | string | no | `univariante` |

Box-Jenkins-Treadway pipeline for a single series — autonomous or guided.

    Runs ONE engine (pipeline.run_full): decides the spec, estimates, adds
    interventions for detected outliers and re-estimates until the diagnosis is
    clean or max_rounds. The only difference between modes is WHO supplies each
    decision:

      - Autonomous (all spec params left at their sentinel): the heuristic
        DefaultPolicy decides λ, d, D, harmonics, p, q and the mean.
      - Guided (any of lam/d/D/p/q/n_harmonics/estimate_mu/decision provided): those
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
    estimate_mu   : free mean? 1 = yes, 0 = no, -1 = let the policy decide from
                    the drift of the differenced series (|t| > 2). For a price
                    index the mean IS the inflation rate, so -1 usually gives 1;
                    force 0 only when you mean "this series has no drift".
    domain        : what KIND of series this is — "price_index" or "generic".
                    "" (default) = infer from the name, which is WEAK evidence
                    and is why declaring it wins. A price index has no natural
                    zero (its base year is a convention), so it takes λ=0
                    whatever the Box-Cox statistic says; measured on eight CPI
                    indices the statistic split them 4/4 on a |gap| that never
                    exceeded 0.304. Declare it when the name does not say so —
                    "EMU" is a price index and does not look like one.
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
| `p` | — | no | `0` |
| `q` | integer | no | `1` |
| `ar_seeds` | — | no | `None` |
| `ar_f_freqs` | — | no | `None` |
| `n_harmonics` | integer | no | `5` |
| `P` | integer | no | `0` |
| `Q` | integer | no | `0` |
| `base_pre_path` | string | no | `` |
| `estimate_mu` | boolean | no | `False` |
| `seasonal` | — | no | `None` |
| `easter` | boolean | no | `False` |
| `include_histogram` | boolean | no | `False` |
| `domain` | string | no | `` |
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
    p               : regular AR order — an INT or a LIST OF ORDERS PER FACTOR.
                      `fue` estimates the regular AR as a PRODUCT of factors, and
                      that is how this school reads an operator: each factor has
                      its own damping and period.

                          6          one operator of order 6
                          [1,1,2,2]  four factors — the FACTORISED model

                      The factorised form is an EXACTLY IDENTIFIED
                      reparametrisation of the same model: same likelihood, same
                      degrees of freedom. Its point is not a better fit — it is
                      that each factor gets its `d ± SE` and `period ± SE`,
                      without which you cannot test whether a factor admits the
                      seasonal frequency.

                      **Never replace an AR(p) by a capped or sparse operator on
                      the strength of similar moduli.** That IMPOSES p−1
                      untested restrictions and forecloses Shin-Fuller. Estimate
                      the full operator, factorise it, then test.
    ar_seeds        : starting values per factor, e.g. [[0.78],[-0.77],[.9,-.6]].
                      `ar_factorization` computes them; pass them when splitting
                      an estimated operator into factors so the fit starts at the
                      optimum it already found. Ignored unless `p` is a list of
                      matching length.
    ar_f_freqs      : frequencies k of FIXED-FREQUENCY AR(2) factors, e.g. [4,2]
                      for s=12. Each is (1 − φ₁B − φ₂B²) with the frequency
                      NAILED to 2πk/s: only φ₂ is estimated and φ₁ is derived.
                      This is the CONTRASTABLE version of «this factor is
                      seasonal» — nested in the free factor, so a likelihood
                      ratio with 1 d.f. decides it. Without it the only way to
                      claim a factor is seasonal was to impose it.
    q               : regular MA order
    n_harmonics     : harmonic pairs cos/sin (D=0 fresh only; ignored when
                      base_pre_path is given — harmonics come from the .pre)
    easter          : add the EASTER (Semana Santa) calendar regressor. MONTHLY
                      series only — the engine builds it itself: 1.0 in the month
                      of Easter Sunday, split 0.5 March + 0.5 April when Good
                      Friday falls in March. It is a deterministic term like the
                      harmonics, NOT an intervention: it has no date and no form,
                      so it does not go through the intervention node. Add it when
                      the residuals show recurring April/March anomalies that move
                      with the calendar. Like n_harmonics, it is ignored when
                      base_pre_path is given — the deterministics come from the
                      .pre, and if the .pre already carries it, it is inherited.
    seasonal        : on/off switch for the whole deterministic seasonal package
                      (cos/sin pairs + Nyquist alter). None (default) => derive from
                      n_harmonics>0, correct for freq>=4. Pass False for a
                      NON-seasonal series (no seasonal terms at all — avoids the
                      spurious Nyquist of BUG-0005). Pass True for a SEMI-ANNUAL
                      seasonal series (freq=2), whose only seasonal term is the
                      Nyquist alter while n_harmonics (pairs) is 0.
    P               : seasonal AR order. Works with D=0 TOO, and that is not a
                      corner case: a stationary stochastic seasonality riding on
                      top of the deterministic harmonics is the B1 route's own
                      way of absorbing what the harmonics leave behind. Both
                      RATIO finals of this project are exactly that — P=1 with
                      D=0 — and `_make_model` has built it all along
                      (pipeline.py, "Stationary stochastic seasonality on top of
                      the deterministic harmonics").
                      BUG-0050: this line used to read "(D=1 only)". It was
                      false, and expensively so: an analyst who believes it
                      concludes that a residual seasonal AR forces D=1, i.e.
                      route B2 — the one route `objetivo="multivariante"`
                      forbids. The documentation sent you to the forbidden route
                      to solve a problem the allowed route solves.
    Q               : seasonal MA order — same as P, D=0 included. NOTE: the
                      fixed-frequency operators (`ar_f`/`ma_f`, where the MEG's
                      MA_f witness lives) are NOT controlled by Q — they are
                      inherited from base_pre_path as structure, together with
                      `ifadf` (BUG-0034).
    base_pre_path   : if given, load interventions+harmonics from this .pre and
                      add only the ARMA spec. Typical use: final ARMA step after
                      outlier cycle in B1 flow.
    estimate_mu     : include mean parameter μ in estimation (default False).
                      Set True when the DRIFT of the differenced series has
                      |t| > 2 -- not the mean of residuals of a model that
                      already fitted a mu, which reads ~0 by construction
                      (BUG-0013). When base_pre_path carries a fitted mean it is
                      inherited, so pass True to keep it.
    include_histogram : return histogram PNG as third item (default False).
                      Keep False during the outlier cycle to save tokens; set True
                      for the final model only.
    domain          : what KIND of series this is — "price_index" |
                      "multiplicative" | "ratio" | "generic". Se REGISTRA en el
                      guion (no se puede recuperar releyendo el `.inp`: es un
                      dato del analista) y se CONTRASTA con la λ que se pasa.
                      Declarar `price_index` con λ=1 es una contradicción y la
                      herramienta la dice — es exactamente el fallo que motivó
                      BUG-0080: art recomendó «identidad (λ=1)» sobre un índice
                      de precios y el carril guiado no ofrecía la corrección.
    guion_path      : (optional) path to guion.json — records this version
    guion_name      : version name (e.g. "PC3"); auto-assigned if empty
    guion_decision  : brief description of what this model tests or concludes
    objetivo        : what the model is FOR — "univariante" (forecasting the
                      series itself), "multivariante" (it enters a system: VECM,
                      transfer function) or "estructural" (read the components).

                      It is the one thing the data cannot supply, and it is asked
                      as a PURPOSE rather than as a method so that one answer
                      informs several nodes. It matters most at the seasonal
                      route: with seasonality detected the pipeline estimates
                      BOTH B1 (D=0 + harmonics) and B2 (D=1) and adjudicates them
                      with the MEG/DCD_f pair; `objetivo` breaks the tie when the
                      tests do not decide, and VETOES B2 under "multivariante" —
                      seasonal unit roots complicate cointegration and every
                      series of a system must carry the same seasonal treatment
                      or their integration orders are not comparable.
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
| `base_pre_path` | string | no | `` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |
| `guion_problems` | string | no | `` |
| `guion_next` | string | no | `` |
| `include_histogram` | boolean | no | `False` |

Fit the model specified in an .inp file and run diagnosis.

    Estimates the model by maximum likelihood (fue MVENC) and runs the
    full diagnosis: standardised residuals, ACF/PACF, Ljung-Box Q-test,
    Jarque-Bera normality test, and residual seasonality check.

    **base_pre_path — DECLARA DE QUÉ MODELO SALE ÉSTE.** This tool re-reads an
    `.inp` as it stands, so it has no other way of knowing the lineage: without
    it the guion records the LAST entry as the parent, which need not be the
    real one. That matters because `guion_abandon` propagates to descendants BY
    DESIGN — a false parent turns a correct abandonment into a destructive one.
    Pass it whenever the `.inp` was built from another model, which is the usual
    case for hand-built factorised or fixed-frequency AR models.

    Parameters
    ----------
    inp_path    : path to the .inp file with the model specification
    include_histogram : devolver además el histograma de residuos (por defecto
                  False, igual que en `confirm_and_estimate`). El histograma NO
                  es parte del módulo básico de diagnosis: se pide (BUG-0129).
    output_path : if given, also persist the fitted model as the ``.pre``
                  (= .inp with the estimated parameters, to seed the next step)
                  and ``.out`` (ASCII results report) alongside this basename —
                  the same trio confirm_and_estimate writes, so a model estimated
                  through this clean path is not left without artefacts.  Empty
                  (default) keeps the old screen-only behaviour.
    guion_*     : lo mismo que en `confirm_and_estimate`. Con `output_path` la
                  entrada de guion **se escribe igual que allí**, y `guion_path`
                  se deriva si no se da: el guion es obligatorio, no opcional.

                  BUG-0088. Esta herramienta persistía el trío `.pre`/`.out`
                  —el docstring lo prometía con esas palabras— y NO el guion.
                  Un modelo estimado por esta vía quedaba con artefactos y sin
                  su entrada, y el guion se desincronizaba **en silencio**. En
                  la sesión FOOD_UEM la escalera de Ucrania entera se construyó
                  así y hubo que reescribir el guion a mano.

                  De las tres salidas que el reporte proponía, ésta es la que
                  mantiene la promesa del docstring: lo inconsistente era
                  persistir los artefactos y no el registro, y quitar los
                  artefactos habría quitado también la razón de ser de la
                  herramienta.

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

    LEE EL FICHERO, no lo vuelve a fabricar (BUG-0091). Antes reestimaba y
    generaba el informe otra vez, con dos consecuencias: si se le pasaba un
    `.pre` devolvía un informe con las desviaciones típicas hasta un **247%**
    desviadas del `.out` que estaba en el mismo directorio, y aun con un `.inp`
    devolvía una reestimación en vez del registro.

    Y el registro importa: **la covarianza no es una propiedad del óptimo, es un
    subproducto del camino del optimizador**, así que un fichero que sólo guarda
    el óptimo —el `.pre`— no puede llevarla. El `.out` es el único sitio donde
    las desviaciones típicas quedan tal como se calcularon.

    Si no hay `.out`, estima **y lo dice**.

    Parameters
    ----------
    inp_path : ruta del `.inp`, `.pre` o `.out`. La terna comparte basename, así
               que se busca el `.out` hermano.

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
| `objetivo` | string | no | `univariante` |
| `domain` | string | no | `` |

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
    domain   : what KIND of series this is — "price_index" | "multiplicative" |
               "ratio" | "generic". Empty = inferred by `policy.decide_domain`.
               **Lo declarado gana**, que es lo que la política dice de sí misma
               y no podía cumplirse: el parámetro sólo existía en `build_model`,
               así que un analista recorriendo los nodos uno a uno no tenía
               forma de declararlo (BUG-0080). Muerde en el nodo Box-Cox
               (Call 1), que es donde el dominio decide: un índice va en log
               SIEMPRE —su base es una convención y un modelo en niveles no
               tiene escala interpretable—, y una magnitud multiplicativa o un
               cociente van en log salvo que el dato lo desmienta.
    objetivo : what the model is FOR — "univariante" | "multivariante" |
               "estructural". Only bites at the seasonal node (Call 3), where it
               says what the purpose implies for the B1/B2 route. It was
               reachable only from `build_model`, so an analyst walking the nodes
               one at a time could not state the purpose at all — and the route
               is precisely where the purpose matters.
    pre_path : path to fitted .pre (Call 4, B1): ARMA identified on
               its residuals instead of the raw transformed series.

---

## `guided_intervention`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `escalera` | boolean | no | `False` |
| `date` | string | no | `` |
| `form` | string | no | `` |
| `n_omega` | integer | no | `0` |
| `output_path` | string | no | `` |
| `threshold` | number | no | `3.0` |
| `umbral_activo` | number | no | `1.0` |
| `umbral_vecino` | number | no | `0.0` |
| `dominio` | string | no | `` |
| `evento_desde` | string | no | `` |
| `evento_naturaleza` | string | no | `` |
| `evento_fuente` | string | no | `` |
| `aportada_por` | string | no | `` |
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |
| `guion_problems` | string | no | `` |
| `guion_next` | string | no | `` |

Sequential INTERVENTION — ONE decision node per call.

    La entrada del nodo de intervención, paralela a `guided_identification`. El
    nodo tiene nueve instrumentos y era el único de la suite sin puerta: el
    analista tenía que elegir a ciegas entre ellos y ninguno remitía a otro.
    Esta herramienta los SECUENCIA y presenta un veredicto por llamada. **No
    decide**: el analista decide en cada paso, igual que en identificación.

    DECISION TREE — call in this sequence, one at a time:

    Call 1   date=""   (default)
      → ¿HAY QUE INTERVENIR? Calibra el correlograma OMITIENDO los anómalos y
        dice si la identificación cambia: qué órdenes AR (PACF) y MA (ACF)
        entran o salen. **Si no cambia nada, lo dice y avisa de que intervenir
        aquí es sobre-intervenir** — cada intervención encoge σ̂ y promueve al
        siguiente anómalo, así que la escalada no para sola.
        Devuelve además las fechas candidatas con su |z|.
      WAIT for user: qué fecha, o parar.

    Call 2   date="Q3/2008"   form=""
      → ¿QUÉ FORMA ADMITE EL DATO? En UNA respuesta:
          · el EPISODIO — cuántos períodos del nivel altera el suceso;
          · las CONFIGURACIONES que el dato admite, acotadas por el mecanismo,
            con su ganancia ω(1) y su lectura permanente/transitorio;
          · la ESCALERA de Ockham con lo que justifica subir de peldaño.
        Y un veredicto único, con el árbitro explícito: para la FORMA gobierna
        `incident_configurations` sobre `residual_episodes`, porque extiende el
        arranque por el mecanismo y el otro sólo agrupa extremos.
        Si el dato NO identifica la configuración, lo dice y pide lo
        extramuestral en vez de elegir por AIC.
      WAIT for user: qué forma y de CUÁNTOS ESCALONES.

    Call 3   date="Q3/2008"   form="step"   n_omega=5   output_path=...
             (n_omega = cuántos escalones; 5 escalones ⇔ ω(B) de orden 4)
      → CONSTRUYE la forma elegida, estima, y verifica:
          · Treadway — ¿queda un anómalo de vecino? ¿el residuo en la fecha
            está en la media?
          · ganancia — Wald sobre ω(1)=0: ¿permanente o transitorio?
        Deja el nodo en el guion. Éste es el paso que faltaba (BUG-0079).

    Parameters
    ----------
    inp_path      : .inp del modelo estimado **SIN** la intervención
    date          : "" → Call 1. "MM/YYYY", "QN/YYYY" o "YYYY" → Call 2 ó 3
    form          : "" → Call 2. "step"|"pulse"|"impulse"|"ramp" → Call 3
    n_omega       : **cuántos ω**, que es lo mismo que cuántos ESCALONES en el
                    nivel — la lengua en la que habla todo este nodo:
                    `incident_configurations` dice «N escalones», la escalera
                    dice «N escalones», y la Call 2 te devuelve el `n_omega` ya
                    calculado. 0 = lo decide la escalera.

                    La equivalencia, por si vienes del operador: **N escalones
                    ⇔ ω(B) de orden N−1**. Así que `n_omega=2` son DOS escalones
                    y un ω(B) = ω₀ − ω₁B.

                    ⚠ Esta línea documentaba el parámetro como si fuera el
                    grado del polinomio, y no lo es: cuenta coeficientes. Un
                    analista al que Treadway le ordenaba subir de peldaño pasaba
                    `n_omega=1` creyendo pedir la escalera de dos, recibía un
                    escalón simple, y la cabecera se lo confirmaba en las
                    unidades equivocadas. No se le ignoraba: se le había
                    documentado otra cosa (BUG-0093).
    output_path   : obligatorio en la Call 3 — dónde se escribe el modelo nuevo
    threshold     : |z| para marcar un residuo como extremo
    umbral_activo : |z| a partir del cual un vecino cuenta como parte del suceso
                    aunque no sea extremo (Call 2)
    umbral_vecino : |z| a partir del cual un vecino cuenta como anómalo
                    (Treadway, Call 2). 0 = el de la política (2.0)
    dominio       : clase de serie ("price_index", "generic"…). Vacío = la
                    infiere `policy.decide_domain`. Lo declarado gana.
    evento_*      : lo extramuestral, que sólo sabe el analista. `evento_fuente`
                    es obligatoria si se declara `evento_naturaleza`: no se
                    afirma que un suceso fue permanente sin decir por qué se
                    sabe.
    guion_*       : registro del nodo, como en el resto de la suite

---

## `guion_abandon`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_path` | string | yes | — |
| `version` | integer | yes | — |
| `why` | string | yes | — |
| `cascade` | boolean | no | `True` |

Mark a version as a DEAD END, with the reason — and cascade to what descends
    from it.

    `why` is required, and that is deliberate: a dead end recorded without its
    reason does not stop anyone walking into it again, which is the only thing
    marking it is for.

    The cascade is not tidiness either. A contaminated decision contaminates
    everything after it — that is precisely the property that forces going back
    instead of patching forward — so the descendants of an abandoned version are
    abandoned with it.

    Parameters
    ----------
    guion_path : path to guion.json
    version    : version to abandon
    why        : why this branch is a dead end (required)
    cascade    : also abandon its descendants (default True, and normally right)

---

## `guion_diff`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_a` | string | yes | — |
| `guion_b` | string | yes | — |
| `etiqueta_a` | string | no | `A` |
| `etiqueta_b` | string | no | `B` |

Compare two analyses NODE BY NODE, with the reasoning of each side.

    Comparing two final models says THAT they differ. Comparing two paths says
    WHERE and WHY, and that is the only comparison anything is learned from: a
    worse model whose chain of decisions is legible teaches more than a better
    one that came out of a box.

    Use it to contrast the guided lane (analyst + LLM deciding together) against
    the autonomous one (the LLM deciding alone) over the same series. The
    protocol is the same and the nodes are the same; the only thing that changes
    is who decided each one — so every divergence localises to a node and comes
    with both reasons attached.

    Pairing is by node NAME, not position: two paths may visit the same nodes in
    a different order, or one may come BACK to a node the other decided once —
    which is exactly what makes the method iterative — and aligning by position
    would turn that into noise.

    Parameters
    ----------
    guion_a, guion_b   : paths to the two guion.json files
    etiqueta_a/b       : names for the two columns ("guiado", "autónomo")

---

## `guion_evidencia`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_path` | string | yes | — |
| `version` | integer | no | `0` |
| `con_figura` | boolean | no | `True` |

La EVIDENCIA de un nodo del guion: ecuación, diagnosis y figuras.

    Para volver a un camino seguro hacen falta dos cosas: el MAPA —quién
    desciende de quién, qué se abandonó y por qué, que lo da `guion_map`— y la
    EVIDENCIA del nodo al que se vuelve. Esto es lo segundo.

    **No reestima nada.** Y ésa es toda la gracia: reestimar dirigido por el LLM
    cuesta llamadas, tokens y decisiones intermedias, y no hace falta porque el
    convenio de ficheros ya guarda lo necesario:

        el `.out`      la ecuación CON sus errores típicos, exactos. La
                       covarianza es un subproducto del camino del optimizador,
                       así que no se puede recuperar de ningún otro sitio
                       (BUG-0090, BUG-0091).
        el guion       la diagnosis registrada: Q con sus retardos y p-valores,
                       Jarque-Bera, σ̂ₐ, anómalos, y con qué versión del
                       instrumento se calculó.
        `figs/`        residuos + ACF/PACF, y el histograma.

    Si alguna pieza no está, lo DICE en vez de fabricarla en silencio; sólo la
    figura se regenera —desde el `.inp`, y avisando— porque depende de los
    valores y no de la covarianza.

    Parameters
    ----------
    guion_path  : ruta del guion.json
    version     : versión a mirar. 0 = la última con modelo.
    con_figura  : False si sólo interesa el texto (más barato).

---

## `guion_map`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_path` | string | yes | — |
| `version` | integer | no | `0` |
| `detalle` | boolean | no | `False` |

Show the analysis as a MAP: what descends from what, what was adopted, and
    which branches were dead ends — with the reason each was abandoned.

    This is the labyrinth view. The iterative method is a search with
    backtracking: it has dead ends, and a dead end is the method working, not
    failing. What a failed iteration produces of value is not the model that is
    discarded — it is the REASON, which is the only thing that stops the branch
    being tried again.

    With `version`, also shows the chain of decisions that led to it (its path
    from the root) and the nearest safe place to return to.

    Parameters
    ----------
    guion_path : path to guion.json
    version    : version to locate in the map (0 = just draw the whole map)
    detalle    : False (default) recorta los textos largos; True los da enteros.

    BUG-0064: el mapa volcaba `decidido`, `evidencia`, `razón`, `descartado` y
    `callejón` SIN LÍMITE, uno por línea. Con nodos bien razonados eso son ~945
    bytes por línea: el RATIO del RUN 3 salía en 52.921 bytes y se truncaba a
    fichero — justo la serie con más ramas, o sea donde más información había que
    ver. La intención estaba escrita en `_record_to_guion`: «el registro es
    interno y la salida no debe crecer por documentar. Quien quiera ver lo
    documentado llama a `export_guion`». El mapa es un MAPA.

---

## `guion_node`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `guion_path` | string | yes | — |
| `nodo` | string | yes | — |
| `decidido` | string | yes | — |
| `razon` | string | yes | — |
| `evidencia` | string | no | `` |
| `alternativas` | string | no | `` |
| `decidido_por` | string | no | `` |
| `parent` | integer | no | `-1` |

Record a DECISION NODE in the guion — a specification choice, not a model.

    Why this exists. A guion that records only MODELS starts the story late. By
    the time the first estimated model exists, λ has been decided, d has been
    decided, whether there is seasonality and of what kind has been decided, and
    the orders have been picked — and none of that leaves a trace. On PGAS of
    the Bolivia replication the ENTIRE divergence between the two lanes is λ,
    decided before any model existed: the guion could not show it.

    Nodes and models live in the SAME chain, because the order in which they
    happened is itself information: a node that comes AFTER a model is a
    reformulation, and that only shows if they are interleaved.

    `razon` is required. A decision recorded without its reason is a number, and
    a number cannot be argued with later — which is the whole point of writing
    it down. This is the same principle as `why` in guion_abandon.

    Parameters
    ----------
    guion_path   : path to guion.json (created if absent)
    nodo         : which node — "lambda", "d", "estacionalidad", "ordenes",
                   "media", "intervenciones", "reformulacion", "dominio"
    decidido     : the value chosen, as text ("0", "1", "B1 + 1 armónico",
                   "ARMA(0,2)×(1,0)₄", "escalón en 2009:1")
    razon        : WHY. Required.
    evidencia    : the statistics it was decided on ("gap=+0.161",
                   "ADF p=0.013, KPSS p=0.09", "F-HAC=50.2")
    alternativas : what was considered and discarded, and why
    decidido_por : "analista+LLM" (guided) | "LLM" (autonomous) | "heurística"
    parent       : version this node descends from (-1 = the last one recorded).

    WHEN TO SET `parent` EXPLICITLY. A node that records the REJECTION of a
    branch must not hang from the branch it rejects. If it does, abandoning that
    branch cascades onto the very reasoning that condemned it — and the cascade
    is right to do so for models, because a contaminated decision contaminates
    what follows, but a node that says "I tried this and it failed" is not
    downstream of the failure: it is the conclusion drawn from it, and it belongs
    to the surviving trunk. Point it at the version you are keeping (the safe
    ancestor), not at the one you are about to abandon.

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

## `incident_configurations`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `at` | integer | no | `0` |
| `threshold` | number | no | `2.5` |
| `umbral_activo` | number | no | `1.0` |
| `evento_desde` | string | no | `` |
| `evento_naturaleza` | string | no | `` |
| `evento_fuente` | string | no | `` |
| `aportada_por` | string | no | `` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar qué configuraciones del incidente admite el dato sin avanzar el flujo.
    Enumera las CONFIGURACIONES del incidente compatibles con el dato, y dice
    si el dato las identifica o no.

    EL PROBLEMA. Con d=1 un spike observado en ∇ puede ser el ARRANQUE de un
    suceso o la COLA de uno que empezó un período antes: un impulso de nivel en
    T da +ω en T y −ω en T+1. Si la serie deambula, el primer spike puede quedar
    tapado y sólo cruzar el umbral el segundo — y la intervención cae un período
    tarde, con Δ logL de 0,03 entre la fecha buena y la mala (BUG-0030).

    Y el arranque no es un detalle de fecha: DECIDE LA LÍNEA BASE. Arrancar
    antes absorbe parte del movimiento previo y encoge la ganancia estimada.

    LO QUE ESTA HERRAMIENTA NO HACE, y es su razón de ser: **no elige cuando el
    dato no identifica**. Medido sobre una serie real, tres configuraciones
    dentro de 2 puntos de AIC, ninguna dejando vecino anómalo, con ganancias de
    −0,27 a −0,58 y el veredicto permanente/transitorio invertido entre ellas.
    Publicar una y su error típico sería fabricar una precisión que no existe.

    LA TRAMPA que avisa: la configuración de arranque MÁS TARDÍO tiende a tener
    el intervalo MÁS ESTRECHO y a ser la única que excluye el cero. No es suerte
    — acortar la ventana quita parámetros y aprieta la identificación dentro del
    modelo mientras empeora la línea base. La lectura más segura es la más
    sospechosa.

    EL CONJUNTO ESTÁ ACOTADO POR EL MECANISMO, no por rejilla: se anda hacia
    atrás desde el primer extremo mientras los residuos contiguos sigan ACTIVOS
    (|z| ≥ `umbral_activo`), y cada arranque determina UNA longitud. No hay
    barrido, que es lo que sobre-elaboraría.

    INFORMACIÓN EXTRAMUESTRAL — LÉASE ANTES DE RELLENARLA.
    Es lo único que identifica de verdad, y **la herramienta no la sabe ni debe
    inventarla**: entra por estos parámetros y queda registrada con quién la
    aportó. Si eres un LLM y no te consta el suceso, **deja los campos vacíos**;
    no rellenes `evento_fuente` con un recuerdo. `naturaleza` sin `fuente` se
    rechaza: afirmar que un suceso fue permanente exige decir por qué se sabe.

    Parameters
    ----------
    inp_path          : .inp de un modelo estimado SIN la intervención
    at                : obs 1-based (espacio de RESIDUOS) dentro del episodio a
                        analizar. 0 = el de mayor |z|. **Se analiza UN episodio
                        por llamada**: las configuraciones son de un suceso, no
                        del conjunto de anómalos de la serie
    threshold         : |z| para marcar un residuo como extremo
    umbral_activo     : |z| a partir del cual un residuo contiguo cuenta como
                        parte del suceso aunque no sea extremo (1,0)
    evento_desde      : fecha declarada de inicio, "QN/AAAA" — fija el arranque
    evento_naturaleza : "permanente" | "transitorio" | "" — se contrasta contra
                        la ganancia: la explicación debe explicar la FORMA
    evento_fuente     : qué se está citando. Obligatorio si hay `naturaleza`
    aportada_por      : "analista" | "LLM"

---

## `intervention_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `threshold` | number | no | `3.5` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos antes de decidir nada sin avanzar el flujo.
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

## `intervention_ladder`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `at` | integer | no | `0` |
| `ventana` | integer | no | `0` |
| `threshold` | number | no | `3.0` |
| `umbral_vecino` | number | no | `0.0` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los peldaños de Ockham de un suceso sin avanzar el flujo.
    ESCALERA DE OCKHAM — estima las especificaciones rivales de un suceso EN
    ORDEN de sofisticación, y dice qué justifica subir de peldaño.

      peldaño 1   UNA intervención escalar. Dos lecturas del MISMO coste —un
                  parámetro cada una— y no anidadas entre sí:
                    1a  escalón en el nivel  → efecto PERMANENTE
                    1b  impulso en el nivel  → efecto TRANSITORIO
      peldaño 2   EPISODIO: L+1 escalones en el nivel, con el contraste de
                  ganancia ω(1)=0 que separa transitorio de permanente.

    LO QUE ESTA HERRAMIENTA PROHÍBE, y es su razón de ser: **el AIC no arbitra
    la subida de peldaño**. Compara dentro de uno, o confirma una subida ya
    justificada. Una escalera que se quedase con el mejor AIC subiría siempre,
    porque el modelo más sofisticado casi siempre ajusta mejor — tiene más
    parámetros. Eso es lo contrario de la navaja.

    LO QUE SÍ JUSTIFICA SUBIR, en este orden:
      1. **Treadway** — la forma de abajo deja un anómalo de vecino. Evidencia
         objetiva: la parte no modelizada del suceso cae entera ahí.
      2. **Inadecuación** — la forma de abajo no deja ruido blanco.
      3. **Dominio** — la lectura simple es implausible para esta clase de
         serie (una caída PERMANENTE en un índice de precios es poco usual).
      4. **Ausencia de explicación extramuestral** — y ésta la herramienta NO
         la sabe: la pregunta y espera respuesta del analista.

    LA EXPLICACIÓN TIENE QUE EXPLICAR LA FORMA, no sólo la fecha. Una bajada de
    impuestos explica un escalón permanente; una huelga, un impulso
    transitorio. Si el analista aporta una explicación de suceso permanente y el
    contraste de ganancia dice transitorio, no cubre lo que hay y se sube igual.

    Parameters
    ----------
    inp_path      : .inp de un modelo estimado **SIN** la intervención en
                    cuestión — sus residuos son justo lo que ella debe explicar
    at            : obs 1-based (espacio de RESIDUOS) donde arranca el suceso.
                    0 = tomar el episodio de mayor |z| que detecte el escaneo
    ventana       : ventana de agrupación en episodios; 0 usa la de la política
    threshold     : |z| para marcar un residuo como extremo
    umbral_vecino : |z| a partir del cual un vecino cuenta como anómalo.
                    0 = el de la política (2.0). Estaba clavado a 3.0 —el de los
                    anómalos sueltos— y daba por exitosa una intervención que
                    deja un vecino a 2.4σ (BUG-0087).

---

## `intervention_plot`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `omega` | array | yes | — |
| `delta` | — | no | `None` |
| `b` | integer | no | `0` |
| `inp_path` | string | no | `` |
| `at` | integer | no | `0` |
| `ventana` | integer | no | `8` |
| `K` | integer | no | `24` |
| `entrada` | string | no | `escalon` |
| `sobre` | string | no | `residuos` |
| `label` | string | no | `` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar una respuesta impulso concreta sobre los datos sin avanzar el flujo.
    GRÁFICO DE INTERVENCIÓN — la forma de una intervención, sola o superpuesta
    a lo observado.

    Dos modos, según se pase `inp_path` y `at`:

      SIN inp_path  → dibuja la HIPÓTESIS SOLA: respuesta al impulso y al
                      escalón, en el nivel y en primeras diferencias, con la
                      ganancia a largo plazo. Para razonar sobre una forma antes
                      de tener modelo.
      CON inp_path
      y `at`        → SUPERPONE esa hipótesis sobre lo observado en el ENTORNO
                      del suceso, y devuelve tres números que dicen si encaja.

    POR QUÉ EXISTE. La forma de una intervención no se identifica a ojo: `fue`
    permite modelizar un suceso con varios parámetros (FLT), y en cuanto `s`
    crece la figura deja de tener lectura obvia. Se usa ANTES de estimar — si la
    forma ya se ve incompatible, estimarla gasta un modelo para confirmar lo que
    el gráfico decía gratis.

    EL CONVENIO. Toda intervención se especifica **en el nivel de la serie**,
    sea cual sea la d con la que se trabaje:

      · escalón en el nivel  → efecto PERMANENTE  → un impulso en ∇
      · impulso en el nivel  → efecto TRANSITORIO → dos impulsos en ∇ que suman 0
      · N escalones en el nivel con ganancia NULA ≡ N−1 impulsos en el nivel,
        es decir un EPISODIO de duración N−1

    LA CONVENCIÓN DE SIGNO, que es donde se cae. fue guarda el numerador con el
    convenio de Box-Jenkins, el mismo para TODO operador —AR, MA, δ y ω—: los
    coeficientes de retardo entran **restando**.

        ω(B) = ω₀ − ω₁B − ω₂B² − ⋯ − ω_sB^s

    Así que la ganancia es (ω₀−ω₁−⋯−ω_s)/(1−δ₁−⋯−δ_r) y **NO la suma de los ω**.
    Pásalos tal como salen del `.out`, sin cambiarles el signo.

    **No hace falta que hagas la resta.** La respuesta trae el CAMINO DEL NIVEL
    que producen los ω que has pasado, que es lo que quieres decir cuando
    escribes una hipótesis. Si el camino no es el que tenías en la cabeza, el
    signo estaba mal — y lo ves antes de estimar nada. Ejemplo real de la
    réplica: ω = (0.5700, +0.7236) tiene coeficientes que uno «sumaría» a
    +1.29, y su ganancia es **−0.15**.

    LOS TRES NÚMEROS del modo superpuesto separan tres preguntas, y se leen sin
    mirar la figura — así sirven también al carril autónomo:

      escala       cuánto hay que multiplicar la forma para que encaje. Cerca de
                   1 con ω estimados: la amplitud era la que se creía. Muy
                   lejos: se está estirando una forma que no da.
      R²           qué fracción del entorno explica la forma YA escalada. Bajo
                   con escala buena ⇒ el problema no es la amplitud, es el
                   PERFIL.
      mayor resto  el pico que sobrevive a quitar la forma, en desviaciones
                   típicas. Si tras ajustar sigue habiendo un 4, la hipótesis no
                   cubre lo que hay.

    DÓNDE NO LLEGA: la superposición **no** distingue una forma correcta de otra
    que deja una cola permanente pequeña — el R² apenas se mueve, porque la
    diferencia está en la GANANCIA A LARGO PLAZO, propiedad del comportamiento
    futuro y no de la forma local. Eso lo dirime el contraste ω(1)=0 de
    `test_interventions`. El gráfico descarta lo incompatible barato; el
    contraste ve lo que el gráfico no puede.

    Parameters
    ----------
    omega    : ω₀…ω_s del numerador, en el orden del `.out`
    delta    : δ₁…δ_r del denominador; vacío o None si no hay
    b        : retardo muerto en períodos
    inp_path : (superposición) .inp de un modelo estimado SIN la intervención
               que se hipotetiza — sus residuos son justo lo que ella debe
               explicar
    at       : (superposición) posición 1-based donde arranca el suceso
    ventana  : (superposición) períodos a mostrar antes y después del soporte
    K        : (hipótesis sola) hasta qué retardo simular
    entrada  : "escalon" usa la respuesta al escalón —el camino del nivel, que
               es el lenguaje homogeneizado del nodo—; "impulso" usa la IRF
    sobre    : (superposición) "residuos" (por defecto) o "serie"
    label    : etiqueta para el título

    Alcance: d = 0 y d = 1. Con d=2 un impulso en la serie transformada es una
    RAMPA en el nivel y el diccionario de arriba tiene otra fila.

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
| `guion_path` | string | no | `` |
| `guion_name` | string | no | `` |
| `guion_decision` | string | no | `` |
| `guion_rationale` | string | no | `` |

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

    BUG-0053. `guion_path`/`guion_name`/`guion_decision`/`guion_rationale` work
    exactly as in `confirm_and_estimate`. Without them this tool wrote a model to
    disk that the guion never saw, and the lineage broke at the worst possible
    place: the reformulated model became an orphan, and whatever was chained on
    top of it was recorded as descending from the model BEFORE the
    reformulation. The one branch the MEG exercise exists to document was the one
    the map could not show.
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

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos de una serie aún sin modelo sin avanzar el flujo.
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

## `residual_episodes`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `ventana` | integer | no | `0` |
| `threshold` | number | no | `3.0` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar cómo se agrupan los extremos en sucesos sin avanzar el flujo.
    Agrupa los residuos extremos de un modelo estimado en EPISODIOS.

    LA PREGUNTA DE ESTE NODO no es «cuántos atípicos hay» sino **«esto es un
    suceso o son varios»**. Un choque puede durar más de un período, y tratado
    como atípicos sueltos se modeliza mal: sobre la réplica, encontrar la
    segunda intervención del episodio 2008-09 valía **16,24 puntos de AIC**, y
    sólo 1 de 8 corridas la encontró.

    QUÉ DEVUELVE. Los episodios con su tramo, duración, cohesión y la
    ESPECIFICACIÓN GENERAL que le corresponde a cada uno: un episodio de
    duración L son **L+1 escalones en el nivel** desde su inicio. Con ganancia
    ω(1)=0 equivalen a L impulsos en el nivel (efecto TRANSITORIO); con ganancia
    distinta de cero, a un cambio de nivel PERMANENTE. Cuál de las dos cosas lo
    dice el contraste —`test_interventions`—, no la forma del grupo.

    Esto sustituye a la dicotomía escalón/impulso decidida por adyacencia: deja
    de ser una REGLA y pasa a ser un CONTRASTE.

    Parameters
    ----------
    inp_path  : .inp de un modelo estimado
    ventana   : hueco máximo entre extremos consecutivos para que sean el mismo
                suceso. 0 = usar la de la política (2). 1 = estrictamente
                adyacentes; 3 admite dos períodos tranquilos dentro.
    threshold : |z| a partir del cual un residuo es extremo

    Juzga la agrupación sobre el gráfico antes de estimar nada. Para ver qué
    FORMA implica un episodio, el `intervention_plot` la dibuja.

---

## `residual_outlier_scan`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `threshold` | number | no | `3.5` |
| `omitir` | — | no | `None` |
| `motivo` | string | no | `` |

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar los anómalos de un modelo ya estimado sin avanzar el flujo.
    Scan the RESIDUALS of an estimated model for outliers, with each one's
    contribution to every ACF lag.

    This is the calibration that decides whether to intervene before choosing
    ARMA orders — and it must run on the residuals, because an outlier is only
    an outlier *relative to a model*. Before the dynamics are fitted, what looks
    anomalous may be exactly what the model predicts.

    NOT to be confused with `preliminary_outlier_scan`, which scans the SERIES
    (before any model exists) and takes the transformation as arguments because
    there is no model yet to carry it. Passing a fitted model to that one
    silently scans the raw, untransformed series — see bugs/BUG-0028.

    QUÉ SE CALIBRA — tres criterios, una sola figura (BUG-0133):

    * por UMBRAL (por defecto)   `threshold=3.0`
    * por OBSERVACIÓN            `omitir=["Q2/2020"]`
    * por INCIDENTE              `omitir=["Q4/2008", "Q1/2009", "Q2/2009"]`

    Con `omitir` el umbral no interviene: se quita exactamente lo que se pide,
    lo marque o no. Es lo que el nodo de intervención necesita antes de elegir
    la forma — «¿cómo queda el correlograma sin este suceso?» — y evita tener
    dos figuras para la misma pregunta.

    Parameters
    ----------
    inp_path  : .inp of an estimated model (per the file convention, estimate
                from the .inp, not the .pre)
    threshold : |z| threshold for flagging (default 3.5)
    omitir    : fechas ("Q2/2020") o índices 0-based a omitir en la calibración.
                Si se da, sustituye al umbral como criterio.
    motivo    : qué se está omitiendo, para la cabecera («el episodio 2008-09»)

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

    ⚠ PRECONDITION — run the MEG FIRST (BUG-0010)
    ---------------------------------------------
    "Which harmonics could be dropped" is only answerable AFTER the MEG has run
    on the all-deterministic baseline. Two reasons, and the second is the one
    that bites:

    * The MEG's null model IS the deterministic harmonic at f. Drop it and there
      is nothing left to contrast: the sweep reports that frequency as
      **sin contrastar** and the analyst never gets a verdict for it.
    * **A low t-ratio at f is evidence FOR stochastic seasonality at f**, not
      evidence that f is absent. A fixed-coefficient harmonic fitted to a
      frequency whose amplitude wanders averages toward zero. So pruning by
      significance removes preferentially the frequencies the MEG most needs to
      look at, under the very hypothesis (deterministic) it exists to test.

    Measured on IPC_ES, the two criteria came out close to orthogonal in both
    directions at once: f=5 (|t| = 0.29 and 1.27 — the first pair any filter
    deletes) carried the second-highest MEG evidence of stochasticity, while
    f=3 (|t| = 5.4 and 2.1 — untouchable by any filter) is the one that IS
    stochastic.

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
| `n_omega` | integer | no | `0` |
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
    n_omega           : nº de coeficientes ω del numerador. **0 = automático**
                        (1 con forma explícita; lo que decida la escalera con
                        `form="auto"`). Con `form="step"` y `n_omega=N` se
                        construye la FLT de N escalones consecutivos en el
                        nivel que `incident_configurations` identifica como
                        «fecha×N» — antes no había forma de construirla desde
                        aquí, aunque el motor la soportaba (BUG-0079).
    form              : "pulse", "step", "ramp" — o **"auto"**, que corre la
                        ESCALERA DE OCKHAM: estima los peldaños en orden (1a
                        escalón permanente, 1b impulso transitorio, 2 episodio
                        de L+1 escalones) y sube sólo cuando algo lo justifica
                        —Treadway, inadecuación, duración del episodio o
                        dominio—. **El AIC no arbitra la subida.** Deja el nodo
                        de decisión en el guion con las alternativas descartadas
                        y la razón de cada descarte.
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

**Instrumento suelto del nodo de intervención.** La secuencia completa
    —¿hay que intervenir? → ¿qué forma admite el dato? → construir y
    verificar— la lleva `guided_intervention`, que es la puerta del nodo.
    Ésta sirve para mirar si las intervenciones ya puestas se sostienen sin avanzar el flujo.
    Test H₀: ω=0 for every non-structural intervention in a fitted model.

    Runs a t-test on each free omega parameter of pulse, step, ramp, and
    similar interventions (cosine/sine harmonics and alter are structural
    and skipped by default). Identifies which interventions are non-significant
    and can be removed to simplify the model.

    Para cualquier intervención con más de un ω libre, además el Wald conjunto
    de GANANCIA NULA, H₀: ω(1) = ω₀−ω₁−⋯−ω_s = 0 — que es lo que separa un
    efecto transitorio de uno permanente (BUG-0071/0072).

    Y LA REGLA DE TREADWAY, que es diagnosis y no bloqueo: si intervienes en una
    fecha no puedes tener un anómalo de vecino, ni antes ni después; y que la
    intervención haya funcionado se ve en que los residuos EN LAS FECHAS
    intervenidas están en la media de los residuos. Un vecino anómalo tiene dos
    lecturas, las dos errores de representación: la FORMA se queda corta (hay
    episodio) o la FECHA está desplazada.

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

    ⚠ RUN THE MEG FIRST. This tool prunes the deterministic harmonics, which are
    the MEG's null hypothesis: prune before testing and that frequency can no
    longer be contrasted at all. And the t-ratio is not neutral evidence here —
    a low |t| at f is evidence FOR stochastic seasonality at f, not for its
    absence. See `seasonal_param_analysis` for the measured IPC_ES case and
    `meg_frequency` for the test itself. (BUG-0010.)

    Typical workflow, AFTER the MEG has run on the all-deterministic baseline:
    - Pass the k values with |t| ≤ 2 in both cos and sin as freq_list —
      **excluding any frequency the MEG called stochastic**, which needs
      `ifadf[f]=1` rather than pruning.
    - If LR < χ²(df, 5%): remove those harmonics and refit.
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
