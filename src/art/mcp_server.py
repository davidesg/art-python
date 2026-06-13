"""
ART MCP Server — expone las funciones de análisis ART como herramientas MCP.

Uso con Claude Code:
    claude mcp add art -- python -m art.mcp_server

Todas las herramientas trabajan sobre ficheros .inp (modelo + serie) o .pre
(modelo ya estimado). Sin estado en memoria — cada llamada es idempotente.

Protocolo agnóstico al LLM: cualquier cliente MCP puede usar este servidor.
"""

from __future__ import annotations

import os
import traceback

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ART — Box-Jenkins-Treadway Analysis")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_ts_model(path: str):
    """Load (ts, model) from an .inp file."""
    import fue
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return fue.inp.load(path)


def _load_fitted(path: str):
    """Load and fit a model from .pre or .inp file."""
    import fue
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    ts, m = fue.load(path)
    m.fit()
    return ts, m


def _result(desc) -> list:
    """Convert a Description to MCP content list (text + optional image)."""
    from mcp.types import TextContent, ImageContent
    items = [TextContent(type="text", text=desc.summary + "\n\n---\n" + desc.recommendation)]
    if desc.figure_b64:
        items.append(ImageContent(type="image", data=desc.figure_b64, mimeType="image/png"))
    return items


def _err(msg: str) -> list:
    from mcp.types import TextContent
    return [TextContent(type="text", text=f"❌ Error: {msg}")]


# ---------------------------------------------------------------------------
# Tool: series info
# ---------------------------------------------------------------------------

@mcp.tool()
def series_info(inp_path: str) -> str:
    """
    Load a time series from an .inp file and return basic information.

    Parameters
    ----------
    inp_path : path to the .inp file

    Returns basic metadata: name, n, frequency, start date, Box-Cox lambda,
    differencing orders (d, D), ARMA structure.
    """
    try:
        ts, m = _load_ts_model(inp_path)
        p = sum(len(f) for f in (m.ar   or []))
        q = sum(len(f) for f in (m.ma   or []))
        P = sum(len(f) for f in (m.ar_s or []))
        Q = sum(len(f) for f in (m.ma_s or []))
        s = ts.freq
        itv_types = sorted({itv.type for itv in (m.interventions or [])})
        lines = [
            f"**Serie**: {ts.name or 'sin nombre'}",
            f"**n**: {ts.nobs}  |  **freq**: {s}  |  **inicio**: {ts.start}",
            f"**λ (Box-Cox)**: {m.boxlam}",
            f"**d={m.d}  D={m.D}**",
            f"**Spec ARIMA**: ({p},{m.d},{q})({P},{m.D},{Q})_{s}",
            f"**Intervenciones**: {', '.join(itv_types) if itv_types else 'ninguna'}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


# ---------------------------------------------------------------------------
# Tool: Box-Cox
# ---------------------------------------------------------------------------

@mcp.tool()
def boxcox_analysis(inp_path: str) -> list:
    """
    Analyse Box-Cox transformation for a time series.

    Computes the mean-std scatter for lambda=0 (log) and lambda=1 (identity),
    recommends the transformation, and returns the comparison figure.

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_boxcox
        ts, _ = _load_ts_model(inp_path)
        return _result(describe_boxcox(ts))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal detection
# ---------------------------------------------------------------------------

@mcp.tool()
def seasonal_analysis(inp_path: str) -> list:
    """
    Run the HAC F-test for seasonal patterns and recommend D.

    Tests all harmonic frequencies using a joint F-test with HAC
    Newey-West standard errors. Returns the seasonality plot and
    a recommendation for D (0 = deterministic harmonics, 1 = seasonal diff).

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_seasonality
        ts, _ = _load_ts_model(inp_path)
        return _result(describe_seasonality(ts))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Identification
# ---------------------------------------------------------------------------

@mcp.tool()
def identification_analysis(inp_path: str, d: int = 2, D: int = 0,
                             lam: float = 0.0) -> list:
    """
    Generate ACF/PACF identification listing and suggest ARMA orders.

    Compares the empirical ACF/PACF of the differenced series with
    theoretical ACF/PACF of candidate ARIMA models. Returns top-5
    suggestions ranked by pattern similarity.

    Parameters
    ----------
    inp_path : path to the .inp file (series is used, model spec ignored)
    d        : regular differencing order (default 2)
    D        : seasonal differencing order (default 0)
    lam      : Box-Cox lambda (0.0=log, 1.0=identity, default 0.0)
    """
    try:
        from art.describe import describe_identification
        ts, _ = _load_ts_model(inp_path)
        return _result(describe_identification(ts, d=d, D=D, lam=lam))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Preliminary outlier scan (before ARMA identification)
# ---------------------------------------------------------------------------

@mcp.tool()
def preliminary_outlier_scan(inp_path: str, d: int, D: int,
                              lam: float = 0.0,
                              threshold: float = 3.5) -> list:
    """
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
    """
    try:
        from art.describe import describe_prelim_scan
        ts, _ = _load_ts_model(inp_path)
        return _result(describe_prelim_scan(ts, d=d, D=D, lam=lam, threshold=threshold))
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Model equation display (Bloque O)
# ---------------------------------------------------------------------------

@mcp.tool()
def model_equation_display(inp_path: str) -> list:
    """
    Display the estimated model as two polynomial-operator equations.

    Shows the two-equation B-J-T form with estimated parameters and SE aligned
    below each coefficient (equivalent to the \\est{}{} LaTeX macro in the thesis).

    Equation 1 (level):  [transform] yₜ = Dₜ + Nₜ
      Dₜ shows all deterministic components: interventions, harmonics, mean.

    Equation 2 (noise):  ∇ᵈ∇ₛᴰ φ(B) Nₜ = θ(B) aₜ
      Polynomial operator form for the ARIMA stochastic model.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model
    """
    try:
        from art.describe import model_equation
        from mcp.types import TextContent
        ts, m = _load_ts_model(inp_path)
        m.fit()
        eq_text = model_equation(ts, m)
        return [TextContent(type="text", text=eq_text)]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Estimate and diagnose
# ---------------------------------------------------------------------------

@mcp.tool()
def estimate_and_diagnose(inp_path: str) -> list:
    """
    Fit the model specified in an .inp file and run diagnosis.

    Estimates the model by maximum likelihood (fue MVENC) and runs the
    full diagnosis: standardised residuals, ACF/PACF, Ljung-Box Q-test,
    Jarque-Bera normality test, and residual seasonality check.

    Parameters
    ----------
    inp_path : path to the .inp file with the model specification
    """
    try:
        from art.describe import describe_diagnosis
        ts, m = _load_ts_model(inp_path)
        m.fit()
        return _result(describe_diagnosis(m))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Formal tests
# ---------------------------------------------------------------------------

@mcp.tool()
def formal_tests(inp_path: str, run_meg: bool = True) -> list:
    """
    Run formal hypothesis tests on a fitted model.

    Tests run (where applicable to the model structure):
    - DCD: non-invertibility of regular MA factors (H0: theta=1)
    - DCD_f: non-invertibility of seasonal MA factors (H0: lambda2=-1)
    - RV: fixed frequency for AR(2) factors
    - MEG: stochastic vs deterministic seasonality (requires D=0 + harmonics)

    Parameters
    ----------
    inp_path : path to .inp or .pre file
    run_meg  : whether to run MEG (slow, default True)
    """
    try:
        from art.describe import describe_formal_tests
        _, m = _load_fitted(inp_path)
        return _result(describe_formal_tests(m, run_meg=run_meg))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Interventions
# ---------------------------------------------------------------------------

@mcp.tool()
def intervention_analysis(inp_path: str, threshold: float = 3.5) -> list:
    """
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
    """
    try:
        from art.describe import describe_interventions
        _, m = _load_fitted(inp_path)
        return _result(describe_interventions(m, threshold=threshold))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Full report
# ---------------------------------------------------------------------------
# Tool: intervention significance testing (Phase 4b)
# ---------------------------------------------------------------------------

@mcp.tool()
def test_interventions(inp_path: str, alpha: float = 0.05) -> list:
    """
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
    """
    try:
        from mcp.types import TextContent
        from art.interventions import simplify_interventions, simplify_summary

        _, m = _load_fitted(inp_path)
        results = simplify_interventions(m, alpha=alpha)

        if not results:
            return [TextContent(type="text",
                                text="*No hay intervenciones no-estructurales en el modelo.*")]

        param_md  = _param_table(m)
        summary   = simplify_summary(results, alpha=alpha)
        n_sig     = sum(1 for r in results if r.significant)
        n_nosig   = len(results) - n_sig

        text = (
            f"### Contraste de intervenciones — {m.series.name or 'modelo'}\n\n"
            + f"**{n_sig} significativas**, **{n_nosig} prescindibles**"
            + f" (α={alpha:.2f},  df={results[0].df})\n\n"
            + "#### Parámetros del modelo actual\n\n" + param_md
            + "\n\n---\n\n" + summary
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------

@mcp.tool()
def full_report(inp_path: str, output_path: str,
                run_meg: bool = True,
                intervention_threshold: float = 3.5) -> str:
    """
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
    """
    try:
        from art.full_report import save_full_report
        _, m = _load_fitted(inp_path)
        output_path = os.path.expanduser(output_path)
        r = save_full_report(
            m, output_path,
            run_meg=run_meg,
            intervention_threshold=intervention_threshold,
        )
        verdict = "APROBADO ✓" if r.diagnosis.clean else "REVISAR ✗"
        return (
            f"Informe generado: {output_path}\n"
            f"Diagnosis: {verdict}\n"
            f"DCD: {len(r.dcd_results)} resultado(s)\n"
            f"MEG: {len(r.meg_results)} frecuencia(s)\n"
            f"Outliers ({intervention_threshold}): {r.interventions.has_outliers}"
        )
    except Exception as e:
        return f"❌ {traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Tool: save identification report
# ---------------------------------------------------------------------------

@mcp.tool()
def save_identification_report(inp_path: str, output_path: str,
                                d: int = 2, D: int = 0,
                                lam: float = 0.0) -> str:
    """
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
    """
    try:
        import art
        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)
        art.save_identification_report(ts, output_path, lam=lam)
        specs = art.suggest_orders(ts, d=d, D=D, lam=lam, top_n=5)
        top = specs[0] if specs else None
        if top:
            return (
                f"Informe guardado: {output_path}\n"
                f"Top sugerencia: ARIMA({top.p},{d},{top.q})"
                f"({top.P},{D},{top.Q})_{top.s}  similitud={top.similarity:.3f}"
            )
        return f"Informe guardado: {output_path} (sin sugerencias)"
    except Exception as e:
        return f"❌ {traceback.format_exc()}"


# ---------------------------------------------------------------------------
# Helpers — guided workflow
# ---------------------------------------------------------------------------

def _obs_to_date(begyear, begtime, freq, at_0based):
    """Convert 0-based obs index to (period, year) for writing .inp files."""
    offset = begtime - 1 + at_0based
    return offset % freq + 1, begyear + offset // freq


def _write_inp(ts, model, output_path: str) -> None:
    """
    Write a fue .inp file from a (ts, model) pair.

    Replicates the format produced by gtk_fue file_io.c:write_inp_file().
    Handles cos/sin/alter/pulse/step/ramp deterministic variables and
    AR/MA operators (regular and seasonal).
    """
    import numpy as np
    freq = ts.freq
    start = ts.start
    start_list = list(start) if hasattr(start, '__iter__') else [int(start), 1]
    beg_year   = start_list[0]
    beg_period = start_list[1] if freq > 1 else 1
    n    = ts.nobs
    name = ts.name or "series"

    itvs = list(model.interventions or [])
    ndet = len(itvs)

    def _itv_line(itv):
        t = itv.type
        if t in ("pulse", "impulse", "compimp"):
            period, year = _obs_to_date(beg_year, beg_period, freq, itv.at)
            c_type = "compimp" if t == "compimp" else "impulse"
            return f"{c_type} {period} {year}" if freq > 1 else f"impulse {year}"
        elif t in ("step", "ramp"):
            period, year = _obs_to_date(beg_year, beg_period, freq, itv.at)
            return f"{t} {period} {year}" if freq > 1 else f"{t} {year}"
        elif t in ("cos", "sin"):
            h = int(itv.harmonic) if hasattr(itv, "harmonic") else 1
            return f"{t} {h}"
        elif t == "alter":
            return "alter"
        elif t in ("trend", "easter"):
            return t
        else:
            return t  # unknown: just emit the type name

    lines = [
        "************************************************",
        "* Input file for program FUE                   *",
        "* DOCTYPE ATSW-interface SYSTEM                *",
        "************************************************",
        "",
        "** Frequency of time series: either 1(A), 4(Q) or 12(M):",
        f" {freq}",
        "** Number of observations and starting date of time series:",
    ]
    if freq > 1:
        lines.append(f" {n}  {beg_period} {beg_year} {name}")
    else:
        lines.append(f" {n}  {beg_year} {beg_year} {name}")

    lines += [
        "** Number of deterministic variables (including seasonal components):",
        f"{ndet}",
    ]

    if ndet > 0:
        lines.append("**")
        for itv in itvs:
            lines.append(_itv_line(itv))
        lines.append("**")

        # Omega orders (MA order of each det var's transfer function)
        omega_orders = []
        for itv in itvs:
            om = itv.omega if hasattr(itv, "omega") and itv.omega else [0.0]
            omega_orders.append(len(om) - 1)
        lines.append(" ".join(str(o) for o in omega_orders))

        # Omega coefs per det var
        for itv in itvs:
            om   = itv.omega      if (hasattr(itv, "omega")      and itv.omega)      else [0.0]
            omf  = itv.omega_free if (hasattr(itv, "omega_free") and itv.omega_free) else [True] * len(om)
            lines.append("**")
            for v, f in zip(om, omf):
                lines.append(f"{v:.6f}  {1 if f else 0}")

        # Delta orders
        lines.append("**")
        delta_orders = []
        for itv in itvs:
            dl = itv.delta if hasattr(itv, "delta") and itv.delta else []
            delta_orders.append(len(dl))
        lines.append(" ".join(str(o) for o in delta_orders))

        # Delta coefs (only where delta_order > 0)
        for itv, dord in zip(itvs, delta_orders):
            if dord > 0:
                dl  = itv.delta
                dlf = itv.delta_free if (hasattr(itv, "delta_free") and itv.delta_free) else [True] * dord
                lines.append("**")
                for v, f in zip(dl, dlf):
                    lines.append(f"{v:.6f}  {1 if f else 0}")

    def _arma_block(factors, free_lists, orders, label):
        n_ops = len(factors)
        if n_ops == 0:
            return [f"** {label}", "0"]
        order_str = " ".join(str(o) for o in orders)
        block = [f"** {label}", f"{n_ops} {order_str}"]
        for coefs, frees in zip(factors, free_lists):
            block.append("**")
            for v, f in zip(coefs, frees):
                block.append(f"{v:.6f}  {1 if f else 0}")
        return block

    def _free_or_default(factors, free_lists):
        """Return free_lists if present, else list of all-True lists matching factors."""
        if free_lists is None:
            return [[True] * len(f) for f in factors]
        return free_lists

    ar   = model.ar   or []
    ar_f = _free_or_default(ar,   model.ar_free)
    ma   = model.ma   or []
    ma_f = _free_or_default(ma,   model.ma_free)
    ar_s = model.ar_s or []
    ar_sf= _free_or_default(ar_s, model.ar_s_free if hasattr(model, "ar_s_free") else None)
    ma_s = model.ma_s or []
    ma_sf= _free_or_default(ma_s, model.ma_s_free if hasattr(model, "ma_s_free") else None)

    def _orders(factors):
        return [len(f) for f in factors]

    lines += _arma_block(ar,   ar_f,  _orders(ar),  "Number and orders of regular AR operators:")
    lines += _arma_block(ar_s, ar_sf, _orders(ar_s), "Number and orders of annual AR operators:")
    lines += _arma_block(ma,   ma_f,  _orders(ma),  "Number and orders of regular MA operators:")
    lines += _arma_block(ma_s, ma_sf, _orders(ma_s), "Number and orders of anual MA operators:")

    # Fixed-frequency AR2/MA2
    ar2f = getattr(model, "ar_f", None) or []
    ma2f = getattr(model, "ma_f", None) or []

    def _ffixed_block(factors, label):
        if not factors:
            return [f"** {label}", "0"]
        freqs_str = " ".join(str(int(f.freq)) for f in factors)
        block = [f"** {label}", f"{len(factors)} {freqs_str}"]
        for f in factors:
            block.append("**")
            block.append(f"{f.coef:.6f}  {1 if f.free else 0}")
        return block

    lines += _ffixed_block(ar2f, "Number and frequencies of regular AR(2) operators with fixed frequency:")
    lines += _ffixed_block(ma2f, "Number and frequencies of regular MA(2) operators with fixed frequency:")

    # Mean
    mu      = float(getattr(model, "mu0", 0.0) or 0.0)
    mu_free = bool(getattr(model, "estimate_mu", False) or False)
    lines += ["** Mean parameter (mu):"]
    if mu_free:
        lines.append(f"{mu:.6f} 1")
    else:
        lines.append("0")

    # Box-Cox and differences
    lam = model.boxlam if model.boxlam is not None else 1.0
    d   = model.d   or 0
    D   = model.D   or 0
    lines += [
        "** Box-Cox lambda, m. Regular differences and complete annual differences:",
        f" {lam:.2f}  {d}  {D}",
        "** Individual factors of the annual difference (starting at freq 0.0):",
    ]
    if freq > 1:
        ifadf = getattr(model, "ifadf", None)
        if ifadf is None:
            ifadf = [0] * (freq // 2 + 1)
        lines.append(" ".join(str(v) for v in ifadf))
    else:
        lines.append(" 0")

    lines += [
        "** ACF/PACF bands (0 Automatic) and reescaling factor:",
        " 0 100.00",
        "** Time series (stochastic and non-standard deterministic variables):",
    ]
    for v in np.asarray(ts.data, dtype=float):
        lines.append(f"{v:.6f} ")

    with open(output_path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


def _build_inp(ts, lam: float, d: int, D: int,
               p: int, q: int,
               n_harmonics: int,
               output_path: str) -> None:
    """
    Build a fresh .inp for a ARIMA(p,d,q) spec + harmonics + alter.
    Constructs a minimal fue Model object and delegates to _write_inp.
    """
    import fue
    freq = ts.freq
    n_harm_pairs = min(n_harmonics, freq // 2)

    # Build deterministic interventions: cos/sin pairs + alter
    itvs = []
    for k in range(1, n_harm_pairs + 1):
        itvs.append(fue.Intervention("cos", at=0,
                    omega=[0.0], omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0,
                    omega=[0.0], omega_free=[True], harmonic=float(k)))
    itvs.append(fue.Intervention("alter", at=0,
                omega=[0.0], omega_free=[True]))

    # AR and MA
    ar   = [[0.0] * p]  if p > 0 else []
    ar_f = [[True] * p] if p > 0 else []
    ma   = [[-0.3] * q] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    ifadf = [0] * (freq // 2 + 1)

    m = fue.Model(
        ts,
        d=d, D=D, boxlam=lam,
        ar=ar, ar_free=ar_f,
        ma=ma, ma_free=ma_f,
        ar_s=[], ma_s=[],
        interventions=itvs,
        ifadf=ifadf,
        mu=0.0, estimate_mu=False,
    )
    _write_inp(ts, m, output_path)


def _param_table(model) -> str:
    """Return a markdown table of estimated parameters with SE and t-stat."""
    import numpy as np
    r = model._result
    if r is None:
        return "*Modelo no estimado.*"

    params = np.asarray(r.params)
    se_raw = r.std_errors if hasattr(r, "std_errors") else (r.se if hasattr(r, "se") else None)
    se     = np.asarray(se_raw) if se_raw is not None else np.full_like(params, float("nan"))
    with np.errstate(divide='ignore', invalid='ignore'):
        tstat = np.where(se != 0, params / se, float("nan"))

    # Parameter names from model structure
    names = _param_names(model)
    if len(names) < len(params):
        names += [f"param_{i}" for i in range(len(names), len(params))]

    rows = ["| Parámetro | Estimación | SE | t |",
            "|-----------|------------|-----|---|"]
    for nm, v, s, t in zip(names, params, se, tstat):
        rows.append(f"| {nm} | {v:+.4f} | {s:.4f} | {t:+.2f} |")

    loglik = getattr(r, "loglik", None)
    n      = model.series.nobs if model.series else "?"
    footer = []
    if loglik is not None:
        k = len(params)
        aic = -2 * loglik + 2 * k
        bic = -2 * loglik + k * (float(np.log(n)) if isinstance(n, int) else float("nan"))
        footer.append(f"loglik={loglik:.3f}  AIC={aic:.2f}  BIC={bic:.2f}  n={n}")

    return "\n".join(rows) + ("\n\n" + "  ".join(footer) if footer else "")


def _param_names(model) -> list[str]:
    """Build human-readable parameter names for a fue model.

    Follows the same ordering as fue's parameter vector:
    det-var omega coefs (free only), then ARMA coefs (free only).
    """
    names = []

    for itv in (model.interventions or []):
        t = itv.type
        om_free = itv.omega_free if (hasattr(itv, "omega_free") and itv.omega_free) else [True]
        om      = itv.omega      if (hasattr(itv, "omega")      and itv.omega)      else [0.0]
        for i, (v, f) in enumerate(zip(om, om_free)):
            if f:
                if t in ("cos", "sin"):
                    h = int(itv.harmonic) if hasattr(itv, "harmonic") else 1
                    label = f"{t}{h}" if i == 0 else f"{t}{h}[ω{i}]"
                elif t in ("pulse", "impulse", "step", "ramp", "compimp"):
                    obs1 = itv.at + 1
                    label = f"{t}[{obs1}]" if i == 0 else f"{t}[{obs1}][ω{i}]"
                else:
                    label = f"{t}" if i == 0 else f"{t}[ω{i}]"
                names.append(label)

        dl_free = itv.delta_free if (hasattr(itv, "delta_free") and itv.delta_free) else []
        dl      = itv.delta      if (hasattr(itv, "delta")      and itv.delta)      else []
        for i, (v, f) in enumerate(zip(dl, dl_free)):
            if f:
                names.append(f"{t}[δ{i+1}]")

    def _arma_names(factors, free_lists, prefix):
        out = []
        if not factors:
            return out
        frees = free_lists if free_lists is not None else [[True] * len(f) for f in factors]
        for factor, freel in zip(factors, frees):
            for lag_idx, (v, f) in enumerate(zip(factor, freel)):
                if f:
                    out.append(f"{prefix}({lag_idx+1})")
        return out

    names += _arma_names(model.ar,   model.ar_free,   "AR")
    names += _arma_names(model.ar_s, model.ar_s_free if hasattr(model, "ar_s_free") else None, "AR_S")
    names += _arma_names(model.ma,   model.ma_free,   "MA")
    names += _arma_names(model.ma_s, model.ma_s_free if hasattr(model, "ma_s_free") else None, "MA_S")

    if model.estimate_mu:
        names.append("mu")

    return names


# ---------------------------------------------------------------------------
# Tool: guided identification (B1)
# ---------------------------------------------------------------------------

@mcp.tool()
def guided_identification(inp_path: str, lam: float = -1.0,
                           d: int = -1, D: int = -1) -> list:
    """
    Run identification steps interactively, one stage at a time.

    Call without lam/d/D to start: returns Box-Cox and seasonality analysis
    with recommended values and the next decision to confirm.

    Once you know lam, d, D: call again with those values to get the ARMA
    order suggestions (p, q) and a summary of all three decisions together.

    Parameters
    ----------
    inp_path : path to .inp file with the time series
    lam      : confirmed Box-Cox lambda (-1 = not yet decided)
    d        : confirmed regular differencing order (-1 = not yet decided)
    D        : confirmed seasonal differencing order (-1 = not yet decided)
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import (describe_boxcox, describe_seasonality,
                                   describe_identification)
        ts, _ = _load_ts_model(inp_path)

        if lam < 0:
            # Stage 1a + 1b: Box-Cox and seasonality
            bc  = describe_boxcox(ts)
            sea = describe_seasonality(ts)

            rec_lam = bc.data["recommended_lambda"]
            rec_d   = sea.data["recommended_d"]
            rec_D   = sea.data["recommended_D"]
            decision = sea.data["decision"]

            text = (
                bc.summary + "\n\n---\n" + bc.recommendation
                + "\n\n" + "=" * 60 + "\n\n"
                + sea.summary + "\n\n---\n" + sea.recommendation
                + "\n\n" + "=" * 60 + "\n\n"
                + f"**Próximo paso:** confirma λ={rec_lam}, d={rec_d}, D={rec_D} "
                f"(decisión {decision}) y llama de nuevo con esos valores "
                f"para ver las sugerencias ARMA."
            )
            items = [TextContent(type="text", text=text)]
            if bc.figure_b64:
                items.append(ImageContent(type="image",
                                          data=bc.figure_b64, mimeType="image/png"))
            if sea.figure_b64:
                items.append(ImageContent(type="image",
                                          data=sea.figure_b64, mimeType="image/png"))
            return items

        else:
            # Stage 1c: ARMA order suggestions
            ident = describe_identification(ts, d=d, D=D, lam=lam)
            top   = ident.data["suggestions"][0] if ident.data["suggestions"] else {}
            rec_p = top.get("p", 0)
            rec_q = top.get("q", 1)

            text = (
                f"**Especificación confirmada:** λ={lam}, d={d}, D={D}\n\n"
                + ident.summary + "\n\n---\n" + ident.recommendation
                + "\n\n" + "=" * 60 + "\n\n"
                + f"**Próximo paso:** cuando decidas (p, q), llama a "
                f"`confirm_and_estimate` con lam={lam}, d={d}, D={D}, "
                f"p=<tu elección>, q=<tu elección>."
            )
            items = [TextContent(type="text", text=text)]
            if ident.figure_b64:
                items.append(ImageContent(type="image",
                                          data=ident.figure_b64, mimeType="image/png"))
            return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: confirm and estimate (B2)
# ---------------------------------------------------------------------------

@mcp.tool()
def confirm_and_estimate(inp_path: str, output_path: str,
                          lam: float = 0.0, d: int = 1, D: int = 0,
                          p: int = 0, q: int = 1,
                          n_harmonics: int = 5) -> list:
    """
    Build the .inp for the confirmed spec, estimate and show diagnosis immediately.

    Constructs the model file from scratch using the series in inp_path and
    the analyst-confirmed (lam, d, D, p, q) spec. Always returns:
      - Parameter table with SE and t-stats
      - Diagnosis verdict (Q-test, JB, outliers)
      - Residual plot (standardised residuals + ACF/PACF + QQ)

    Parameters
    ----------
    inp_path     : source .inp file (series data is used; model spec ignored)
    output_path  : path to write the new .inp (can be re-used for later tools)
    lam          : Box-Cox lambda (0.0=log, 1.0=identity)
    d            : regular differencing order
    D            : seasonal differencing order
    p            : AR order
    q            : MA order
    n_harmonics  : number of harmonic pairs cos/sin (0 = no harmonics)
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue

        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)

        _build_inp(ts, lam=lam, d=d, D=D, p=p, q=q,
                   n_harmonics=n_harmonics, output_path=output_path)

        _, m = _load_fitted(output_path)

        # Parameter table
        spec_line = (f"**ARIMA({p},{d},{q})  λ={lam}  D={D}  "
                     f"armónicos={n_harmonics}**  —  {ts.name or 'series'}")
        param_md  = _param_table(m)

        # Diagnosis
        diag = describe_diagnosis(m)

        text = (
            spec_line + "\n\n"
            + "### Parámetros estimados\n\n" + param_md
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + f"\n\n*Modelo guardado en: {output_path}*"
        )

        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: suggest intervention form (B3)
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_intervention_form(inp_path: str, output_path: str,
                               date: str,
                               form: str = "auto",
                               context_hint: str = "") -> list:
    """
    Add an intervention to the .inp, re-estimate and show updated diagnosis.

    Adds a pulse, step or ramp intervention at the given date, saves to
    output_path, re-estimates and returns the updated parameter table and
    diagnosis. Use this iteratively — one intervention at a time.

    Parameters
    ----------
    inp_path     : current .inp file (with any previous interventions)
    output_path  : path to write the updated .inp
    date         : observation date in "MM/YYYY" or "QN/YYYY" or "YYYY" format
    form         : "pulse", "step", "ramp" or "auto" (heuristic from residuals)
    context_hint : free-text note about the economic event (used for logging)
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue, re

        inp_path    = os.path.expanduser(inp_path)
        output_path = os.path.expanduser(output_path)

        if not os.path.exists(inp_path):
            raise FileNotFoundError(f"File not found: {inp_path}")

        def _parse_date(d: str):
            d = d.strip()
            m_mo = re.match(r"^(\d{1,2})/(\d{4})$", d)
            m_q  = re.match(r"^[Qq](\d)/(\d{4})$", d)
            m_yr = re.match(r"^(\d{4})$", d)
            if m_mo:
                return int(m_mo.group(1)), int(m_mo.group(2))
            if m_q:
                return int(m_q.group(1)), int(m_q.group(2))
            if m_yr:
                return 1, int(m_yr.group(1))
            raise ValueError(f"Unrecognised date format: {d!r}. Use MM/YYYY, QN/YYYY or YYYY.")

        period, year = _parse_date(date)

        # Load current model to inspect residuals and build the new spec
        ts, m_src = _load_fitted(inp_path)

        freq  = ts.freq
        start = list(ts.start)
        s0y, s0p = start[0], (start[1] if freq > 1 else 1)

        # Convert (period, year) → 0-based observation index
        at_0 = (year - s0y) * freq + (period - s0p)
        if at_0 < 0 or at_0 >= ts.nobs:
            raise ValueError(f"Date {date} gives obs={at_0+1}, outside series range [1, {ts.nobs}].")

        if form == "auto":
            # Inspect residuals around that observation
            from art.diagnosis import diagnose
            diag_tmp = diagnose(m_src, z_threshold=2.5)
            extreme_obs = {obs for obs, _ in diag_tmp.extreme}
            obs_1 = at_0 + 1
            has_consec = (obs_1 - 1 in extreme_obs) or (obs_1 + 1 in extreme_obs)
            form = "step" if has_consec else "pulse"

        # Create new Intervention with correct at= (0-based index)
        itv = fue.Intervention(
            type=form,
            at=at_0,
            omega=[0.0],
            omega_free=[True],
        )

        # Build updated model with the new intervention appended
        new_itvs = list(m_src.interventions or []) + [itv]
        m_new = fue.Model(
            ts,
            ar=m_src.ar, ar_free=m_src.ar_free,
            ma=m_src.ma, ma_free=m_src.ma_free,
            ar_s=m_src.ar_s, ar_s_free=m_src.ar_s_free,
            ma_s=m_src.ma_s, ma_s_free=m_src.ma_s_free,
            ar_f=m_src.ar_f, ma_f=m_src.ma_f,
            d=m_src.d, D=m_src.D, ifadf=m_src.ifadf,
            interventions=new_itvs,
            mu=m_src.mu0, estimate_mu=m_src.estimate_mu,
            boxlam=m_src.boxlam,
        )

        # Write the updated .inp and re-estimate
        _write_inp(ts, m_new, output_path)
        _, m_fit = _load_fitted(output_path)

        param_md = _param_table(m_fit)
        diag     = describe_diagnosis(m_fit)

        context_str = f"  Contexto: {context_hint}" if context_hint else ""
        text = (
            f"**Intervención añadida:** {form.upper()} en {date}{context_str}\n\n"
            + "### Parámetros estimados\n\n" + param_md
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + f"\n\n*Modelo actualizado en: {output_path}*"
        )

        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Helpers for autonomous pipeline (Block C)
# ---------------------------------------------------------------------------

def _make_model(ts, lam: float, d: int, D: int,
                p: int, q: int, n_harmonics: int,
                extra_itvs: list | None = None):
    """
    Build a fue.Model from ARIMA spec + harmonic det-vars + optional interventions.

    extra_itvs : list of (at_0based, form_str) tuples for pulse/step/ramp
    """
    import fue
    freq = ts.freq
    n_harm = min(n_harmonics, freq // 2)

    itvs = []
    for k in range(1, n_harm + 1):
        itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
    itvs.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))

    if extra_itvs:
        for at_0, form in extra_itvs:
            itvs.append(fue.Intervention(form, at=int(at_0), omega=[0.0], omega_free=[True]))

    ar   = [[0.0] * p]  if p > 0 else []
    ar_f = [[True] * p] if p > 0 else []
    ma   = [[-0.3] * q] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    return fue.Model(
        ts,
        d=d, D=D, boxlam=lam,
        ar=ar, ar_free=ar_f,
        ma=ma, ma_free=ma_f,
        ar_s=[], ma_s=[],
        interventions=itvs,
        ifadf=[0] * (freq // 2 + 1),
        mu=0.0, estimate_mu=False,
    )


def _format_dcd_meg(dcd_results, meg_results) -> str:
    """Short text summary of DCD and MEG results for use in build_model output."""
    lines = []
    if dcd_results:
        lines.append("**DCD (no invertibilidad MA):**")
        for r in dcd_results:
            inv = "Invertible ✓" if r.rejects_5pct else "No invertible ✗"
            lines.append(f"  Factor {r.factor_index+1}: LR={r.lr:.3f}  → {inv}")
    if meg_results:
        lines.append("**MEG (estacionalidad estocástica):**")
        for r in meg_results:
            tag = {"stochastic": "Estocástica ⚠", "deterministic": "Determinista ✓",
                   "ambiguous": "Ambiguo ?"}.get(r.status, r.status)
            lr_str = f"  LR={r.dcd_result.lr:.3f}" if r.dcd_result else ""
            lines.append(f"  freq={r.freq}: {tag}{lr_str}")
    return "\n".join(lines) if lines else "*Sin contrastes formales aplicables.*"


# ---------------------------------------------------------------------------
# Tool: autonomous model build (C1)
# ---------------------------------------------------------------------------

@mcp.tool()
def build_model(inp_path: str, output_path: str, max_rounds: int = 5,
                run_meg: bool = False) -> list:
    """
    Autonomous Box-Jenkins-Treadway pipeline for a single series.

    Automatically selects lambda, d, D, p, q; estimates the model; adds
    interventions for detected outliers and re-estimates until the diagnosis
    is clean or max_rounds is reached. Always returns parameters + residual
    diagnosis figure. Formal tests (DCD, MEG) are run at the end.

    Parameters
    ----------
    inp_path    : source .inp file — only the series is used
    output_path : path for the final estimated .inp
    max_rounds  : maximum intervention-addition rounds (default 5)
    run_meg     : run MEG stochastic seasonality test (slow; default False)
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_boxcox, describe_seasonality, describe_diagnosis
        from art.model_detection import suggest_orders
        from art.diagnosis import diagnose, plot_diagnosis
        from art.formal_tests import dcd as _dcd
        import io, base64
        import matplotlib.pyplot as plt

        inp_path    = os.path.expanduser(inp_path)
        output_path = os.path.expanduser(output_path)
        ts, _ = _load_ts_model(inp_path)
        name = ts.name or os.path.basename(inp_path)
        log = [f"### Pipeline autónomo — {name}"]

        # ── 1. Box-Cox ────────────────────────────────────────────────────
        bc  = describe_boxcox(ts)
        lam = 0.0 if bc.data.get("gap", 0.0) >= 0 else 1.0
        lam_str = "log (λ=0)" if lam == 0.0 else "identidad (λ=1)"
        log.append(f"**λ:** {lam_str}  (gap={bc.data.get('gap', 0):+.3f})")

        # ── 2. Seasonality / d / D ────────────────────────────────────────
        seas     = describe_seasonality(ts)
        d        = seas.data.get("recommended_d", 1)
        D        = seas.data.get("recommended_D", 0)
        decision = seas.data.get("decision", "B1")
        n_harmonics = ts.freq // 2 if decision != "A" else 0
        log.append(f"**Estacionalidad:** decisión={decision}  d={d}  D={D}  armónicos={n_harmonics}")

        # ── 3. ARMA orders ────────────────────────────────────────────────
        specs = suggest_orders(ts, d=d, D=D, lam=lam, top_n=5)
        top   = specs[0] if specs else None
        if top is not None:
            p, q = top.p, top.q
            sim_str = f"{top.similarity:.3f}"
        else:
            p, q = 0, 1
            sim_str = "N/A"
        log.append(f"**Órdenes:** ARIMA({p},{d},{q})  similitud={sim_str}")

        # ── Main loop ─────────────────────────────────────────────────────
        extra_itvs: list[tuple[int, str]] = []
        m_fit = None
        diag  = None
        round_num = 0
        round_figures: list[str] = []   # base64 PNG per round (Block D)

        def _round_fig_b64(diag_result, model, label: str) -> str:
            """Render a diagnosis figure and return as base64 PNG."""
            diag_result.label = label
            fig = plot_diagnosis(diag_result, model)
            buf = io.BytesIO()
            fig.savefig(buf, format='png', dpi=110, bbox_inches='tight')
            plt.close(fig)
            buf.seek(0)
            return base64.b64encode(buf.read()).decode()

        for round_num in range(1, max_rounds + 1):
            m = _make_model(ts, lam, d, D, p, q, n_harmonics, extra_itvs)
            _write_inp(ts, m, output_path)
            _, m_fit = _load_fitted(output_path)
            diag = diagnose(m_fit, z_threshold=3.0)

            # ── Per-round rich log (Block D) ──────────────────────────────
            q_fail = [str(l) for l, pv in zip(diag.q_lags, diag.q_pvalues) if pv < 0.05]
            q_str  = "✓" if diag.white_noise else f"✗ lags {', '.join(q_fail)}"
            jb_str = "✓" if diag.normal else f"✗ JB={diag.jb_stat:.1f}"
            n_ext  = len(diag.extreme)
            ext_str = (
                "  ".join(f"obs {obs} (z={z:+.2f})" for obs, z in diag.extreme[:4])
                if diag.extreme else "—"
            )
            log.append(
                f"\n**Ronda {round_num}:**  Q: {q_str}  JB: {jb_str}  "
                f"extremos: {n_ext}"
            )
            if diag.extreme:
                log.append(f"  {ext_str}" + (" …" if n_ext > 4 else ""))

            # ── Figure for this round ──────────────────────────────────────
            fig_label = f"Ronda {round_num} — {name}"
            round_figures.append(_round_fig_b64(diag, m_fit, fig_label))

            if diag.clean or not diag.extreme:
                break

            # ── Intervention selection ─────────────────────────────────────
            ext_obs = {obs for obs, _ in diag.extreme}
            already = {at for at, _ in extra_itvs}
            new_itvs = []
            for obs, z in sorted(diag.extreme, key=lambda x: -abs(x[1])):
                at_0 = obs - 1
                if at_0 in already:
                    continue
                has_consec = (obs - 1) in ext_obs or (obs + 1) in ext_obs
                form = "step" if has_consec else "pulse"
                new_itvs.append((at_0, form))

            if not new_itvs:
                log.append("  Sin nuevas intervenciones que añadir.")
                break
            extra_itvs.extend(new_itvs)
            itv_labels = ", ".join(f"{f.upper()} obs {at+1}" for at, f in new_itvs[:5])
            log.append(f"  → Añadidas: {itv_labels}")

        log.append(f"\n**Rondas totales:** {round_num}")
        log.append(f"**Diagnosis final:** {'APROBADA ✓' if diag and diag.clean else 'REVISAR ✗'}")

        # ── Formal tests ──────────────────────────────────────────────────
        dcd_results = []
        meg_results = []
        if m_fit is not None:
            try:
                dcd_results = _dcd(m_fit)
            except Exception:
                pass
            if run_meg and m_fit.D == 0:
                try:
                    from art.formal_tests import meg as _meg
                    meg_results = _meg(m_fit)
                except Exception:
                    pass

        # ── Parameter table and final description ─────────────────────────
        param_md  = _param_table(m_fit) if m_fit else "*Modelo no estimado.*"
        if m_fit is not None:
            diag_desc = describe_diagnosis(m_fit)
            diag_text = diag_desc.summary + "\n\n---\n" + diag_desc.recommendation
        else:
            diag_text = "*Sin diagnosis disponible.*"

        formal_md = _format_dcd_meg(dcd_results, meg_results)

        text = (
            "\n".join(log)
            + "\n\n### Parámetros estimados\n\n" + param_md
            + "\n\n---\n\n" + diag_text
            + "\n\n---\n\n### Contrastes formales\n\n" + formal_md
            + f"\n\n*Modelo guardado en: {output_path}*"
        )

        # ── Return: text + one figure per round (Block D) ─────────────────
        items: list = [TextContent(type="text", text=text)]
        for fig_b64 in round_figures:
            items.append(ImageContent(type="image", data=fig_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: batch build (C2)
# ---------------------------------------------------------------------------

@mcp.tool()
def batch_build(inp_paths: list[str], output_dir: str,
                max_rounds: int = 5, run_meg: bool = False) -> list:
    """
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
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_boxcox, describe_seasonality, describe_diagnosis
        from art.model_detection import suggest_orders
        from art.diagnosis import diagnose
        from art.formal_tests import dcd as _dcd

        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        summary_rows = []
        items: list = []

        for raw_path in inp_paths:
            inp = os.path.expanduser(raw_path)
            if not os.path.exists(inp):
                summary_rows.append({"name": os.path.basename(inp),
                                     "error": "fichero no encontrado"})
                continue

            try:
                ts, _ = _load_ts_model(inp)
                name  = ts.name or os.path.splitext(os.path.basename(inp))[0]

                # ── 1. λ ──────────────────────────────────────────────────
                bc  = describe_boxcox(ts)
                lam = 0.0 if bc.data.get("gap", 0.0) >= 0 else 1.0

                # ── 2. d / D ──────────────────────────────────────────────
                seas     = describe_seasonality(ts)
                d        = seas.data.get("recommended_d", 1)
                D        = seas.data.get("recommended_D", 0)
                decision = seas.data.get("decision", "B1")
                n_harm   = ts.freq // 2 if decision != "A" else 0

                # ── 3. ARMA orders ────────────────────────────────────────
                specs = suggest_orders(ts, d=d, D=D, lam=lam, top_n=3)
                top   = specs[0] if specs else None
                p, q  = (top.p, top.q) if top else (0, 1)

                # ── Main loop ─────────────────────────────────────────────
                extra_itvs: list[tuple[int, str]] = []
                m_fit = None
                diag  = None
                out_inp = os.path.join(output_dir, f"{name}_auto.inp")

                for round_num in range(1, max_rounds + 1):
                    m = _make_model(ts, lam, d, D, p, q, n_harm, extra_itvs)
                    _write_inp(ts, m, out_inp)
                    _, m_fit = _load_fitted(out_inp)
                    diag = diagnose(m_fit, z_threshold=3.0)

                    if diag.clean or not diag.extreme:
                        break

                    ext_obs = {obs for obs, _ in diag.extreme}
                    already  = {at for at, _ in extra_itvs}
                    new_itvs = []
                    for obs, z in sorted(diag.extreme, key=lambda x: -abs(x[1])):
                        at_0 = obs - 1
                        if at_0 in already:
                            continue
                        form = "step" if ((obs - 1) in ext_obs or (obs + 1) in ext_obs) else "pulse"
                        new_itvs.append((at_0, form))
                    if not new_itvs:
                        break
                    extra_itvs.extend(new_itvs)

                # ── Formal tests ──────────────────────────────────────────
                dcd_results = []
                if m_fit is not None:
                    try:
                        dcd_results = _dcd(m_fit)
                    except Exception:
                        pass
                    if run_meg and m_fit.D == 0:
                        try:
                            from art.formal_tests import meg as _meg
                            _meg(m_fit)
                        except Exception:
                            pass

                # ── HTML report ───────────────────────────────────────────
                html_path = os.path.join(output_dir, f"{name}_auto_report.html")
                if m_fit is not None:
                    from art.diagnosis import save_diagnosis_report
                    save_diagnosis_report(m_fit, html_path)

                # ── Diagnosis image for batch output ──────────────────────
                if m_fit is not None:
                    diag_desc = describe_diagnosis(m_fit)
                    if diag_desc.figure_b64:
                        items.append(ImageContent(type="image",
                                                  data=diag_desc.figure_b64,
                                                  mimeType="image/png"))

                # ── DCD non-invertibility check ───────────────────────────
                dcd_flag = ""
                for r in dcd_results:
                    if not r.rejects_5pct:
                        dcd_flag = " ⚠DCD"
                        break

                summary_rows.append({
                    "name": name,
                    "lam": lam, "d": d, "D": D, "p": p, "q": q,
                    "n_harm": n_harm,
                    "n_itv": len(extra_itvs),
                    "rounds": round_num,
                    "clean": "✓" if (diag and diag.clean) else "✗",
                    "dcd": dcd_flag,
                    "html": os.path.basename(html_path),
                })

            except Exception as exc:
                summary_rows.append({"name": os.path.basename(inp),
                                     "error": str(exc)[:120]})

        # ── Summary table ──────────────────────────────────────────────────
        header = "| Serie | λ | d | D | p | q | arm. | interv. | rondas | ok | DCD |"
        sep    = "|-------|---|---|---|---|---|------|---------|--------|----|----|"
        rows   = [header, sep]
        errors = []
        for r in summary_rows:
            if "error" in r:
                errors.append(f"- {r['name']}: {r['error']}")
            else:
                rows.append(
                    f"| {r['name']} | {r['lam']:.0f} | {r['d']} | {r['D']} "
                    f"| {r['p']} | {r['q']} | {r['n_harm']} | {r['n_itv']} "
                    f"| {r['rounds']} | {r['clean']} | {r['dcd'] or '✓'} |"
                )

        n_ok  = sum(1 for r in summary_rows if r.get("clean") == "✓")
        n_tot = len(summary_rows) - len(errors)
        summary_text = (
            f"## Batch build — {n_ok}/{n_tot} series limpias\n\n"
            + "\n".join(rows)
            + (("\n\n**Errores:**\n" + "\n".join(errors)) if errors else "")
            + f"\n\n*Informes HTML en: {output_dir}*"
        )
        items.insert(0, TextContent(type="text", text=summary_text))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
