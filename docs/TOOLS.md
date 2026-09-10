# `art` — MCP tool reference

*Generated from the docstrings by `tools/gen_tools_md.py`. Do not edit by hand — edit the docstring.*

**46 tools.** In an MCP server the docstring is what the model reads, so this page and the instruction the model receives are the same text by construction.

---

| tool | what it answers |
|---|---|
| [`ar_factorization`](#ar-factorization) | Factorize the estimated AR operator(s) of a fitted model and identify |
| [`batch_build`](#batch-build) | Autonomous pipeline for multiple series. Builds one model per series. |
| [`boxcox_analysis`](#boxcox-analysis) | Analyse Box-Cox transformation for a time series (standalone use). |
| [`build_model`](#build-model) | Pipeline completo sobre UNA serie. **Escribe** el `.inp` final, su `.pre`, |
| [`compare_versions`](#compare-versions) | Compare two estimated models: spec diff, stats table, nested LR test. |
| [`confirm_and_estimate`](#confirm-and-estimate) | Estima el ARMA confirmado y devuelve la diagnosis. **Escribe** `output_path` |
| [`create_inp`](#create-inp) | Create a .inp file from raw time series data. |
| [`estimate_and_diagnose`](#estimate-and-diagnose) | Estima el modelo de un `.inp` y devuelve la diagnosis. **Escribe** el `.pre` |
| [`export_guion`](#export-guion) | Render guion.json to a self-contained, navigable HTML report. |
| [`formal_tests`](#formal-tests) | Contrastes formales sobre un modelo estimado. **No escribe nada.** |
| [`full_report`](#full-report) | Generate a complete HTML report for a fitted model and save it to disk. |
| [`generate_forecast`](#generate-forecast) | Generate L-step-ahead forecasts from a fitted model. |
| [`get_out_report`](#get-out-report) | Return the full fue .out ASCII report for an estimated model. |
| [`guided_identification`](#guided-identification) | La PUERTA de la identificación: un nodo de decisión por llamada. |
| [`guided_intervention`](#guided-intervention) | La PUERTA del nodo de intervención: un nodo de decisión por llamada. |
| [`guion_abandon`](#guion-abandon) | Mark a version as a DEAD END, with the reason — and cascade to what descends |
| [`guion_diff`](#guion-diff) | Compare two analyses NODE BY NODE, with the reasoning of each side. |
| [`guion_evidencia`](#guion-evidencia) | La EVIDENCIA de un nodo del guion: ecuación, diagnosis y figuras. |
| [`guion_map`](#guion-map) | Show the analysis as a MAP: what descends from what, what was adopted, and |
| [`guion_node`](#guion-node) | Registra un NODO DE DECISIÓN en el guion — una elección de especificación, |
| [`identification_analysis`](#identification-analysis) | ACF/PACF identification listing + ARMA order suggestions — standalone use. |
| [`incident_configurations`](#incident-configurations) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`intervention_analysis`](#intervention-analysis) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`intervention_ladder`](#intervention-ladder) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`intervention_plot`](#intervention-plot) | Dibuja la FORMA de una intervención. **No escribe modelo**, sólo la figura. |
| [`load_data`](#load-data) | Load a time series from Excel or CSV and write a fue .inp file. |
| [`meg_frequency`](#meg-frequency) | MEG for ONE given seasonal frequency, evaluated on the CHAINED baseline. |
| [`meg_reformulate`](#meg-reformulate) | Reformula el modelo para estacionalidad ESTOCÁSTICA en la frecuencia |
| [`model_equation_display`](#model-equation-display) | Display the estimated model as two polynomial-operator equations. |
| [`model_histogram`](#model-histogram) | Show the residuals histogram with normal overlay for a fitted model. |
| [`overparameterization_analysis`](#overparameterization-analysis) | Check for over-parameterization by inspecting parameter correlation matrix. |
| [`preliminary_outlier_scan`](#preliminary-outlier-scan) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`preview_data`](#preview-data) | Preview the contents of an Excel or CSV file before loading. |
| [`record_version`](#record-version) | Load, fit and record a model version in guion.json. |
| [`residual_episodes`](#residual-episodes) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`residual_outlier_scan`](#residual-outlier-scan) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
| [`save_identification_report`](#save-identification-report) | Generate and save a full HTML identification report to disk. |
| [`seasonal_analysis`](#seasonal-analysis) | HAC F-test for seasonal patterns — support tool, standalone use only. |
| [`seasonal_param_analysis`](#seasonal-param-analysis) | Visualise estimated seasonal harmonic parameters (cos/sin) with ±2 SE bars. |
| [`series_info`](#series-info) | Load a time series from an .inp file and return basic information. |
| [`sps_dashboard`](#sps-dashboard) | Generate a sequential prediction (SPS) dashboard for all series in a directory. |
| [`suggest_intervention_form`](#suggest-intervention-form) | Añade una intervención, reestima y devuelve la diagnosis actualizada. |
| [`test_interventions`](#test-interventions) | Instrumento suelto del nodo; la puerta es `guided_intervention`. |
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

Pipeline completo sobre UNA serie. **Escribe** el `.inp` final, su `.pre`,
    su `.out` y el guion.

    Un solo motor (`pipeline.run_full`): decide la especificación, estima, añade
    intervenciones para los anómalos detectados y reestima hasta que la
    diagnosis salga limpia o se agote `max_rounds`. Lo único que cambia entre
    modos es QUIÉN pone cada decisión:

      autónomo  todos los parámetros de especificación en su centinela: decide
                la heurística (`DefaultPolicy`).
      guiado    cualquiera de lam/d/D/p/q/n_harmonics/estimate_mu dado: se
                respeta (`ClaudePolicy`) y la heurística rellena sólo lo que
                quedó sin especificar. Úsalo tras `guided_identification` para
                correr el ciclo de anómalos automáticamente con la
                especificación ya confirmada.

    PRECONDICIÓN: un `.inp` con datos — sólo se usa la serie.

    LO QUE NUNCA: no lo uses para «probar» una especificación que el analista no
    ha confirmado. En carril guiado la especificación viene de la puerta.

    Devuelve parámetros y la figura de residuos + ACF/PACF; DCD/MEG al final.
    El objetivo y la ruta estacional, en `art://doc/DISENO-nodo-arma`.

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

Estima el ARMA confirmado y devuelve la diagnosis. **Escribe** `output_path`
    (.inp), su `.pre` y su `.out`, y registra la versión si se da `guion_path`.

    DOS MODOS:
      fresco       `base_pre_path=""` — construye desde cero con la serie de
                   `inp_path` y la especificación confirmada (lam, d, D, p, q,
                   P, Q).
      incremental  `base_pre_path=<.pre>` — hereda intervenciones, armónicos y
                   deterministas de ese `.pre` y sustituye SÓLO la parte ARMA y
                   μ. Es el paso final de ARMA tras el ciclo de anómalos.

    PRECONDICIÓN: un `.inp` con datos, y la especificación ya decidida — la da
    `guided_identification`. Esta herramienta no identifica: confirma y estima.

    LO QUE NUNCA:
      · Nunca sustituyas un AR(p) por un operador **capado o disperso** porque
        sus módulos se parezcan: impone p−1 restricciones sin contrastar y cierra
        Shin-Fuller. Estima entero → factoriza (`p` como lista) → contrasta.
      · Nunca reestimes desde un `.pre` para leer errores típicos: los válidos
        están en el `.out` (`get_out_report`).
      · `P`/`Q` **funcionan con D=0** — no es un caso raro, es la ruta B1.

    Devuelve tabla de parámetros con SE y t, veredicto de diagnosis (Q, JB,
    anómalos) y la figura de residuos + ACF/PACF.

    Detalle y doctrina —el AR como producto de factores, `ar_seeds`,
    `ar_f_freqs`, `objetivo`, `domain`, con qué t se decide μ— en
    `art://doc/DISENO-nodo-arma`. Los parámetros llevan su descripción en el
    esquema.

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

Estima el modelo de un `.inp` y devuelve la diagnosis. **Escribe** el `.pre`
    si se da `output_path`, y registra la versión si se da `guion_path`.

    Máxima verosimilitud (fue MVENC) y diagnosis completa: residuos
    tipificados, ACF/PACF, Q de Ljung-Box, Jarque-Bera y estacionalidad
    residual.

    PRECONDICIÓN: un `.inp` con la especificación ya escrita. Para construirlo
    desde una especificación confirmada, `confirm_and_estimate`.

    LO QUE NUNCA: no dejes `base_pre_path` vacío cuando este `.inp` salga de
    otro modelo. Esta herramienta relee el `.inp` tal cual y no tiene otra forma
    de saber de quién desciende: sin él, el guion anota como padre la ÚLTIMA
    entrada, que puede no serlo. Y `guion_abandon` propaga a los descendientes
    **por diseño**, así que un padre falso convierte un abandono correcto en uno
    destructivo. Es el caso normal en modelos factorizados o de frecuencia
    fijada construidos a mano.

    El histograma no viene por defecto: no es parte del módulo básico de
    diagnosis, se pide con `include_histogram` (BUG-0129).

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

Contrastes formales sobre un modelo estimado. **No escribe nada.**

    PRECONDICIÓN: un `.inp`/`.pre` de un modelo ya estimado.

    QUÉ CONTRASTA:
      Shin-Fuller  raíz casi unitaria en el AR regular (Φ₁ᵤ; crítico 5% ≈ 1,75)
      DCD / DCD_f  no invertibilidad de factores MA regulares / estacionales
      RV           frecuencia fijada para factores AR(2)
      MEG          barrido HSM: estacionalidad estocástica frente a determinista,
                   frecuencia por frecuencia. Exige D=0 + armónicos.

    LO QUE NUNCA:
      · **El MEG va ANTES de podar armónicos.** Podar uno no significativo anula
        el barrido entero y la excepción se traga: el informe cierra diciendo
        que el modelo es adecuado mientras se pierde una frecuencia
        genuinamente estocástica (BUG-0010).
      · No decidas una especificación apoyándote SÓLO en el MEG. Contrástalo con
        Shin-Fuller y con la acf/pacf; si contradice al resto del informe, hoy
        es más probable que falle esta implementación.

    MARCA LA RUTA MEG COMO «(experimental)» y ofrécela, no la des por defecto.
    Y si preguntan qué significa, explícalo: el MÉTODO está publicado —Abraham y
    Box (1978), HEGY, DCD, Shin-Fuller—; lo experimental es la implementación de
    `art` y el último decimal de los críticos. En prosa el modelo se llama HSM;
    `MEG` es el identificador del código.

    Los tres defectos abiertos de esta familia (BUG-0009, 0010, 0011), el porqué
    del nombre y la forma canónica de Abraham-Box, en
    `art://doc/DISENO-contrastes-formales`.

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

La PUERTA de la identificación: un nodo de decisión por llamada.

    **No decide**: presenta la evidencia y espera — WAIT for user. Cada llamada
    termina en ⏸ y ahí acaba tu turno. Los parámetros a −1 son «pregunta».

    LAS CUATRO LLAMADAS:
      1  `lam=-1`                    Box-Cox. Decide λ.
      2  `lam=X, d=-1`               serie(λ) + ACF/PACF en nivel. ¿Tendencia?
      3  `lam=X, d=<n>, D=-1`        diferenciada + ACF/PACF + estacionalidad
                                     HAC. Confirma d y D.
      4  `lam, d, D` confirmados     órdenes ARMA candidatos.

    LA BIFURCACIÓN ESTACIONAL, en la llamada 3:
      B1  determinista (armónicos, D=0) → estima m00 con armónicos solos, cicla
          anómalos hasta limpiar, y entra en la llamada 4 con `pre_path=<.pre>`
      B2  estocástica (D=1) → llamada 4 directa sobre ∇∇ₛ
    `objetivo="multivariante"` VETA B2: las series de un sistema tienen que
    llevar el mismo tratamiento estacional o sus órdenes de integración no son
    comparables.

    LO QUE NUNCA: no confirmes d y D en la misma llamada que λ. Cada nodo se
    decide con su evidencia delante.

    El detalle de cada nodo, en `art://protocolo/identificacion`.

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

La PUERTA del nodo de intervención: un nodo de decisión por llamada.

    Paralela a `guided_identification`. **No decide**: secuencia los nueve
    instrumentos del nodo y presenta un veredicto por llamada:
    **el analista decide en cada paso**.
    Cada llamada termina en ⏸ (WAIT for user) y ahí acaba tu turno.

    PRECONDICIÓN: un modelo estimado (`confirm_and_estimate`).

    LAS TRES LLAMADAS:
      1  `date=""`          ¿HAY QUE INTERVENIR? Calibra el correlograma
                            omitiendo los anómalos y dice si la identificación
                            cambia —qué órdenes AR (PACF) y MA (ACF) entran o
                            salen—. Devuelve las fechas candidatas con su |z|.
      2  `date="Q3/2008"`   ¿QUÉ FORMA ADMITE EL DATO? El episodio, las
                            configuraciones con su ganancia ω(1) y el veredicto.
                            `escalera=True` añade la escalera como argumento.
      3  `+ form="..."`     CONSTRUYE, estima y verifica: Treadway (¿vecino
                            anómalo?) y ω(1)=0 (permanente o transitorio).

    `n_omega` = **cuántos escalones** en el nivel, que es la lengua de este
    nodo: N escalones ⇔ ω(B) de orden N−1. Se construye con N escalón(es), de
    orden N−1 en el numerador. Un escalón con ganancia nula ES un impulso de un
    orden menos.

    LO QUE NUNCA: si la llamada 1 dice que la identificación NO cambia,
    intervenir ahí es sobre-intervenir. Cada intervención encoge σ̂ y promueve al
    siguiente anómalo: **la escalada no para sola**.

    La escalera de Ockham, la regla de Treadway y el diccionario de formas, en
    `art://doc/DISENO-nodo-intervencion` y `art://protocolo/intervencion`.

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

Registra un NODO DE DECISIÓN en el guion — una elección de especificación,
    no un modelo. **Escribe** el guion.

    POR QUÉ EXISTE: un guion que sólo anota MODELOS empieza la historia tarde.
    Cuando existe el primer modelo estimado ya se decidieron λ, d, si hay
    estacionalidad y de qué clase, y los órdenes — y nada de eso deja rastro.
    Sobre PGAS de la réplica, **toda** la divergencia entre los dos carriles es
    λ, decidida antes de que existiera modelo alguno: el guion no podía
    enseñarlo.

    Nodos y modelos van en la MISMA cadena, porque el orden en que ocurrieron es
    información: un nodo posterior a un modelo es una reformulación, y eso sólo
    se ve si están entrelazados.

    LO QUE NUNCA: `razon` no es opcional. Una decisión registrada sin su razón
    es un número, y con un número no se puede discutir después — que es para lo
    que se escribe. Mismo principio que el `why` de `guion_abandon`.

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

Instrumento suelto del nodo; la puerta es `guided_intervention`.

    Enumera las CONFIGURACIONES del incidente compatibles con el dato, y dice
    **si el dato las identifica o no**.

    EL PROBLEMA: con d=1, un pico observado en ∇ puede ser el ARRANQUE de un
    suceso o la COLA de uno que empezó un período antes —un impulso de nivel en
    T da +ω en T y −ω en T+1—. Si la serie deambula, el primer pico puede quedar
    tapado y la intervención cae un período tarde, con Δ logL de 0,03 entre la
    fecha buena y la mala (BUG-0030). Y el arranque **decide la línea base**:
    arrancar antes absorbe parte del movimiento previo y encoge la ganancia.

    LO QUE NO HACE, y es su razón de ser: **no elige cuando el dato no
    identifica**. Medido sobre una serie real: tres configuraciones dentro de 2
    puntos de AIC, ninguna dejando vecino anómalo, con ganancias de −0,27 a
    −0,58 y el veredicto permanente/transitorio **invertido** entre ellas.
    Publicar una con su error típico sería fabricar una precisión que no existe.

    LA TRAMPA: la configuración de arranque MÁS TARDÍO tiende a tener el
    intervalo MÁS ESTRECHO y a parecer la única significativa. Es un artefacto
    de la línea base, no evidencia.

    El mecanismo, en `art://doc/DISENO-configuracion-del-incidente`.

---

## `intervention_analysis`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `threshold` | number | no | `3.5` |

Instrumento suelto del nodo; la puerta es `guided_intervention`.
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

Instrumento suelto del nodo; la puerta es `guided_intervention`.

    ESCALERA DE OCKHAM — estima las especificaciones rivales de un suceso **en
    orden de sofisticación** y dice qué justifica subir de peldaño.

      1a  escalón en el nivel   → efecto PERMANENTE   ┐ mismo coste, un
      1b  impulso en el nivel   → efecto TRANSITORIO  ┘ parámetro, NO anidadas
      2   EPISODIO: L+1 escalones, con el contraste ω(1)=0 que separa
          transitorio de permanente

    LO QUE PROHÍBE, y es su razón de ser: **el AIC no arbitra la subida de
    peldaño.** Compara dentro de uno, o confirma una subida ya justificada por
    otra cosa. Una escalera que se quedara con el mejor AIC subiría siempre —el
    modelo más sofisticado casi siempre ajusta mejor porque tiene más
    parámetros—, que es lo contrario de la navaja.

    LO QUE SÍ JUSTIFICA SUBIR, en este orden: (1) Treadway —la forma de abajo
    deja un vecino anómalo—; (2) inadecuación —no deja ruido blanco—;
    (3) dominio —la lectura simple es implausible para esta clase de serie—;
    (4) ausencia de explicación extramuestral. Los dos primeros los ve la
    herramienta; el cuarto **sólo lo sabe el analista**, y por eso lo pregunta.

    Es ARGUMENTAL: se usa cuando el analista discute la forma sugerida. La
    sugerencia la lleva la superposición de `guided_intervention`.

    La doctrina, en `art://doc/DISENO-nodo-intervencion`.

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

Dibuja la FORMA de una intervención. **No escribe modelo**, sólo la figura.

    Instrumento suelto del nodo: la secuencia la lleva `guided_intervention`.

    DOS MODOS: sin `inp_path`, la HIPÓTESIS SOLA —impulso y escalón, en nivel y
    en diferencias, con la ganancia—; con `inp_path` y `at`, la SUPERPONE sobre
    lo observado y da tres números que dicen si encaja.

    EL CONVENIO — toda intervención se especifica **en el nivel de la serie**,
    sea cual sea la d con la que se trabaje:
      · escalón en el nivel  → efecto PERMANENTE   → un impulso en ∇
      · impulso en el nivel  → efecto TRANSITORIO  → un (1−B) en ∇

    LA CONVENCIÓN DE SIGNO, que es donde se cae. `fue` guarda el numerador con
    el convenio de Box-Jenkins, el mismo para TODO operador —AR, MA, δ y ω—: los
    coeficientes de retardo entran **restando**.

        ω(B) = ω₀ − ω₁B − ω₂B² − ⋯ − ω_sB^s

    Así que la ganancia es (ω₀−ω₁−⋯−ω_s)/(1−δ₁−⋯−δ_r) y **no la suma de los ω**.
    Pásalos tal como salen del `.out`, sin cambiarles el signo.
    **No hace falta que hagas la resta**: la respuesta trae el CAMINO DEL NIVEL
    que producen los ω que has pasado, y si no es el que tenías en la cabeza, el
    signo estaba mal — y lo ves antes de estimar nada.

    LO QUE NUNCA: no identifiques la forma a ojo. Úsala ANTES de estimar. Y no
    le pidas lo que no puede: NO distingue una forma correcta de otra que deja
    una cola permanente pequeña — eso lo dirime ω(1)=0 en `test_interventions`.

    La FLT, el diccionario de formas y la lectura de los tres números, en
    `art://doc/DISENO-nodo-intervencion`.

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

Reformula el modelo para estacionalidad ESTOCÁSTICA en la frecuencia
    `freq`. **Escribe** el `.pre`/`.out` en `output_path`.

    PRECONDICIÓN: que el MEG (DCD_f / Shin-Fuller AR_f) haya concluido
    estocástica en esa frecuencia. Parte del último `.pre` —`base_pre_path` si
    se da, si no `inp_path`— y no exige editar ficheros a mano.

    QUÉ HACE: activa la raíz unitaria AR_f en `freq` (`ifadf[freq]=1`: el
    operador 1−2cos(ω)B+B² en una frecuencia interior, o 1+B en el Nyquist
    f=s/2), retira los armónicos deterministas que quedan anulados ahí,
    reestima, y muestra la ecuación y la diagnosis.

    `with_witness=True` (por defecto) añade además el testigo MA_f libre
    invertible (1−2λcos(ω)B+λ²B²), de modo que el modelo reformulado es
    EXACTAMENTE lo que contrastan el MEG y el DCD_f —la raíz AR_f y el testigo
    juntos—. Ése es el modelo estocástico correcto. Después, `formal_tests` lee
    el testigo: LR>crítico ⇒ estocástica genuina; λ→−1 (frontera) ⇒
    cuasi-cancelación.

    LO QUE NUNCA: no reformules sin el MEG delante, y no podes armónicos antes
    de correrlo (BUG-0010).

    Ruta experimental: `art://doc/DISENO-contrastes-formales`.

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

Instrumento suelto del nodo; la puerta es `guided_intervention`.
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

Instrumento suelto del nodo; la puerta es `guided_intervention`.
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

Instrumento suelto del nodo; la puerta es `guided_intervention`.
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

Añade una intervención, reestima y devuelve la diagnosis actualizada.
    **Escribe** `output_path`.

    Instrumento suelto del nodo; la puerta es `guided_intervention`. Úsala
    iterativamente: **una intervención cada vez**.

    PRECONDICIÓN: un `.inp`/`.pre` estimado, con las intervenciones previas si
    las hay.

    LA FORMA:
      `form="step"|"pulse"|"ramp"`  la que decida el analista
      `form="auto"`                 la elige la escalera de Ockham
      `n_omega=0`                   automático (1 con forma explícita)
      `form="step"`, `n_omega=N`    la FLT de N escalones consecutivos en el
                                    nivel que `incident_configurations`
                                    identifica como «fecha×N»
      `date=""`                     toma el residuo más extremo

    LO QUE NUNCA: no encadenes intervenciones sin volver a mirar la diagnosis
    entre una y otra. Cada una encoge σ̂ y promueve al siguiente anómalo: la
    escalada no para sola.

    El diccionario de formas y el convenio de nivel, en
    `art://doc/DISENO-nodo-intervencion`.

---

## `test_interventions`

**Arguments**

| name | type | required | default |
|---|---|---|---|
| `inp_path` | string | yes | — |
| `alpha` | number | no | `0.05` |

Instrumento suelto del nodo; la puerta es `guided_intervention`.
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
