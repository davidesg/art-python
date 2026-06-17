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

_INSTRUCTIONS = """
Eres el asistente de análisis de series temporales ART (Box-Jenkins-Treadway).

══════════════════════════════════════════════════════
PREGUNTA INICIAL OBLIGATORIA
══════════════════════════════════════════════════════
Al iniciar cualquier análisis, SIEMPRE pregunta primero al usuario:

  "¿Cómo deseas proceder?
   1) Análisis GUIADO (paso a paso, con gráficos y confirmación en cada etapa)
   2) Análisis AUTÓNOMO (pipeline automático completo)"

Si el usuario elige autónomo → usa build_model o batch_build.
Si elige guiado → sigue el protocolo siguiente.

══════════════════════════════════════════════════════
DATOS DE ENTRADA — DOS CASOS
══════════════════════════════════════════════════════
CASO 1 — El usuario proporciona datos (Excel, CSV, lista de números):
  → Llama create_inp con los datos, nombre, frecuencia y fecha de inicio.
  → Este tool crea el .inp de datos. A partir de ahí continúa el análisis normal.
  → NO intentes escribir o interpretar el formato .inp manualmente.

CASO 2 — El usuario ya tiene un fichero .inp:
  → Úsalo directamente como inp_path en los tools de análisis.

CONSTRUCCIÓN DEL MODELO:
  confirm_and_estimate construye el fichero .inp del modelo desde cero a partir
  de los parámetros confirmados (λ, d, D, p, q, n_harmonics). Nunca busques ni
  edites ficheros .inp de modelo manualmente.

══════════════════════════════════════════════════════
PROTOCOLO GUIADO — 4 ETAPAS
══════════════════════════════════════════════════════

─────────────────────────────────────────────────────
ETAPA 1 — IDENTIFICACIÓN (árbol de decisiones secuencial)
─────────────────────────────────────────────────────

⚠ USA SOLO guided_identification para toda la identificación.
  NO llames boxcox_analysis, identification_analysis, seasonal_analysis
  ni unit_root_analysis individualmente — son herramientas internas.

LLAMADA 1 — guided_identification(inp_path)   [lam=-1 por defecto]
  Devuelve: gráfico Box-Cox (media vs desviación típica)
  Lee con el usuario:
  • Nube con pendiente positiva → λ=0 (log)
  • Nube horizontal → λ=1 (original)
  • REGLA: series índice (IPC, IPI, IPP…) → SIEMPRE λ=0
  → ESPERA confirmación de λ.

LLAMADA 2 — guided_identification(inp_path, lam=X)   [d=-1 por defecto]
  Devuelve: serie transformada(λ) + ACF/PACF en nivel d=0
  Lee con el usuario:
  • ¿Tendencia visible o ACF muy lenta? → d=1 necesario
  • ¿Serie estacionaria? → posible d=0
  → Si quieres apoyo estadístico: llama unit_root_analysis por separado.
  → ESPERA decisión sobre d.

LLAMADA 3 — guided_identification(inp_path, lam=X, d=<nivel>)   [D=-1 por defecto]
  Devuelve: ∇^d y(λ) + ACF/PACF + test HAC como soporte (si d>0)
  Lee con el usuario:
  • ¿Picos en ACF/PACF a lags s, 2s, 3s? → hay estacionalidad
    – Regulares y estables → hipótesis B1 (D=0, armónicos deterministas)
    – Dominantes e irregulares → hipótesis B2 (D=1, diferencia estacional)
  • ¿Sin picos estacionales? → D=0 sin armónicos
  • ¿Todavía con tendencia? → repite con d+1
  • Hipótesis B1 es revisable al final mediante MEG (formal_tests)
  → ESPERA confirmación de d y D.

LLAMADA 4 — guided_identification(inp_path, lam=X, d=<confirmado>, D=<confirmado>)
  Devuelve: ACF/PACF de ∇^d ∇_s^D y(λ) + sugerencias ARMA
  Lee con el usuario:
  • Corte brusco PACF, decaimiento ACF → AR(p)
  • Corte brusco ACF, decaimiento PACF → MA(q)
  • Ambas decaen → ARMA(p,q)
  • Sin estructura → p=0, q=0
  → ESPERA confirmación de p, q.

DESPUÉS DE LLAMADA 4 — Modelo de referencia (si D=0):
  → confirm_and_estimate con p=0, q=0, n_harmonics=<freq//2-1>,
    output_path=/tmp/<serie>_ref.inp
  → model_equation_display con ese output_path
  → Evalúa ACF/PACF del modelo de referencia:
    1. Lags s, 2s, 3s limpios → representación armónica adecuada
    2. Lags 1,2,3 con estructura → ajusta p, q

─────────────────────────────────────────────────────
ETAPA 2 — ESTIMACIÓN DEL MODELO ARMA ELEGIDO
─────────────────────────────────────────────────────
  → Llama confirm_and_estimate con (λ, d, D, p, q, n_harmonics=freq//2-1) confirmados
    output_path: usa /tmp/<serie>_v1.inp o la ruta que el usuario indique
    Este tool construye el INP, estima y devuelve la ecuación + diagnosis en una sola respuesta.
    NO llames model_equation_display por separado — la ecuación ya viene incluida.
  → MUESTRA el gráfico diagnóstico Treadway
  → Discute: ¿parámetros significativos (|t|>2)? ¿Q-test pasa? ¿JB pasa?

─────────────────────────────────────────────────────
ETAPA 3 — DIAGNOSIS E INTERVENCIONES
─────────────────────────────────────────────────────
  → Si hay residuos extremos (|z|>3.5): llama intervention_analysis
  → Discute impacto en ACF/PACF y tipo probable (pulse/step/ramp)
  → ESPERA confirmación del usuario antes de añadir cada intervención
  → Añade una a una con suggest_intervention_form → MUESTRA diagnosis actualizada
  → Cuando el modelo parezca limpio: llama test_interventions para verificar
    que todas las intervenciones son significativas

─────────────────────────────────────────────────────
ETAPA 4 — CONTRASTES FORMALES
─────────────────────────────────────────────────────
  → Llama formal_tests (Shin-Fuller, DCD, RV, MEG)
  → MEG: si detecta estocasticidad en alguna frecuencia → reformular con D=1
    (revisión de la hipótesis de trabajo B1)
  → DCD: si no rechaza invertibilidad → reformular el factor MA

══════════════════════════════════════════════════════
REGLAS GENERALES
══════════════════════════════════════════════════════
- En modo guiado, NUNCA llames boxcox_analysis, identification_analysis,
  seasonal_analysis ni unit_root_analysis individualmente para la identificación.
  USA guided_identification — integra los 4 análisis en el orden correcto.
- El gráfico listing ACF/PACF (segunda figura de guided_identification) es la
  herramienta principal. Discútelo ANTES de los tests.
- Los tests HAC, ADF, KPSS son herramientas de soporte, no árbitros.
  La decisión es siempre del analista a partir de los gráficos.
- NUNCA encadenes pasos sin mostrar el gráfico y esperar confirmación del usuario.
- confirm_and_estimate construye el INP del modelo — nunca busques ficheros .inp.
- Las decisiones finales (λ, d, D, p, q) son del USUARIO, no del modelo.
"""

mcp = FastMCP("ART — Box-Jenkins-Treadway Analysis", instructions=_INSTRUCTIONS)


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


def _write_bare_inp(ts, path: str) -> None:
    """Write a minimal fue .inp with only series data and no model spec."""
    freq    = ts.freq
    begyear = int(ts.start[0])
    begtime = int(ts.start[1]) if freq > 1 else begyear  # annual: year repeated twice
    n_ifadf = freq // 2 + 1 if freq > 1 else 1
    lines = [
        "************************************************",
        "* Input file for program FUE                   *",
        "* DOCTYPE ATSW-interface SYSTEM                *",
        "************************************************",
        "",
        "** Frequency of time series: either 1(A), 4(Q) or 12(M):",
        f" {freq}",
        "** Number of observations and starting date of time series:",
        f" {ts.nobs} {begtime:2d} {begyear} {ts.name}",
        "** Number of deterministic variables (including seasonal components):",
        " 0",
        "**Number and orders of regular AR operators:",
        " 0",
        "** Number and orders of annual AR operators:",
        " 0",
        "** Number and orders of regular MA operators:",
        " 0",
        "** Number and orders of anual MA operators:",
        " 0",
        "** Number and frequencies of regular AR(2) operators with fixed frequency:",
        " 0",
        "** Number and frequencies of regular MA(2) operators with fixed frequency:",
        " 0",
        "** Mean parameter (mu):",
        "0",
        "** Box-Cox lambda, regular differences and complete annual differences:",
        "1.00 0 0",
        "** Individual factors of the annual difference (from freq 0.0): ",
        " " + " ".join(["0"] * n_ifadf),
        "** ACF/PACF bands (0 Automatic) and reescaling factor: ",
        " 0 100.00",
        "** Time series (stochastic and non-standard deterministic variables): ",
    ]
    for v in ts.data:
        lines.append(f"{v:.10f} ")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(lines) + "\n")


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


def _show_fig(b64: str | None, label: str = "art") -> None:
    """Save figure to /tmp and open with xdg-open (non-blocking)."""
    if not b64:
        return
    import base64, subprocess, tempfile, threading
    data = base64.b64decode(b64)
    # Use a stable path per label so repeated calls replace the same window.
    path = f"/tmp/art_{label.replace(' ', '_').replace('/', '_')}.png"
    with open(path, "wb") as fh:
        fh.write(data)
    threading.Thread(
        target=lambda: subprocess.Popen(["xdg-open", path],
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL),
        daemon=True,
    ).start()


# ---------------------------------------------------------------------------
# Helper: single-level series + ACF/PACF figure
# ---------------------------------------------------------------------------

def _plot_series_at_d(ts, lam: float, d: int) -> str | None:
    """
    Plot Box-Cox(lam) + d-fold differenced series via pyfug plot_combined.
    Returns base64 PNG or None on error.
    """
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        from art.identification import boxcox_transform, apply_differences, transform_label
        from art.describe import _fig_b64, _pyfug_ts

        try:
            from pyfug.graphics import plot_combined as _pyfug_combined
        except ImportError:
            return None

        data  = np.asarray(ts.data, dtype=float)
        freq  = ts.freq if ts.freq > 0 else 1
        start = getattr(ts, "start", (1, 1))

        z = boxcox_transform(data, lam)
        w = apply_differences(z, freq, d, 0)   # D=0: calls 2 and 3 never use seasonal diff

        off       = (int(start[1]) - 1) + d
        new_start = (int(start[0]) + off // freq, off % freq + 1)
        title     = transform_label(lam, d, 0, freq)

        pf  = _pyfug_ts(w, freq, new_start, name=title)
        fig = _pyfug_combined(pf, title=title)
        b64 = _fig_b64(fig)
        plt.close(fig)
        return b64
    except Exception:
        return None

@mcp.tool()
def create_inp(
    data: list[float],
    output_path: str,
    name: str = "series",
    freq: int = 12,
    start_year: int = 2000,
    start_period: int = 1,
) -> str:
    """
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
    """
    try:
        import numpy as np
        import fue

        output_path = os.path.expanduser(output_path)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        ts = fue.TimeSeries(
            data=np.array(data, dtype=float),
            freq=freq,
            start=(start_year, start_period),
            name=name,
        )

        # Minimal model — no structure, no transformation
        m = fue.Model(
            ts,
            d=0, D=0, boxlam=1.0,
            ar=[], ar_free=None,
            ma=[], ma_free=None,
            ar_s=[], ar_s_free=None,
            ma_s=[], ma_s_free=None,
            interventions=[],
            ifadf=[0] * (max(freq // 2, 1) + 1),
            mu=0.0, estimate_mu=False,
        )
        _write_inp(ts, m, output_path)

        period_str = f"P{start_period}/{start_year}" if freq > 1 else str(start_year)
        return (
            f"✓ INP creado: {output_path}\n"
            f"  Serie: {name}  |  n={len(data)}  |  freq={freq}  |  inicio={period_str}\n"
            f"Siguiente paso: boxcox_analysis o guided_identification con este fichero."
        )
    except Exception:
        return f"❌ {traceback.format_exc()}"


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
    Analyse Box-Cox transformation for a time series (standalone use).

    NOTE: in guided analysis use guided_identification instead — it integrates
    Box-Cox, the identification listing, unit-root tests and seasonality test
    in the correct order (listing first, tests as support).

    Computes the mean-std scatter for lambda=0 (log) and lambda=1 (identity),
    recommends the transformation, and returns the comparison figure.

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_boxcox
        ts, _ = _load_ts_model(inp_path)
        desc = describe_boxcox(ts)
        _show_fig(desc.figure_b64, "boxcox")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal detection
# ---------------------------------------------------------------------------

@mcp.tool()
def seasonal_analysis(inp_path: str) -> list:
    """
    HAC F-test for seasonal patterns — support tool, standalone use only.

    NOTE: in guided analysis use guided_identification instead — seasonal_analysis
    is a support tool called internally after the identification listing.

    Tests all harmonic frequencies using a joint F-test with HAC Newey-West
    standard errors. Returns the seasonality plot and a recommendation for D.

    Parameters
    ----------
    inp_path : path to the .inp file
    """
    try:
        from art.describe import describe_seasonality
        ts, _ = _load_ts_model(inp_path)
        desc = describe_seasonality(ts)
        _show_fig(desc.figure_b64, "seasonality")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Unit root tests (Bloque L)
# ---------------------------------------------------------------------------

@mcp.tool()
def unit_root_analysis(inp_path: str, lam: float = 0.0,
                       max_d: int = 2) -> list:
    """
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
    """
    try:
        from art.describe import describe_unit_root
        ts, _ = _load_ts_model(inp_path)
        desc = describe_unit_root(ts, lam=lam, max_d=max_d)
        _show_fig(desc.figure_b64, "unit_root")
        return _result(desc)
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Identification
# ---------------------------------------------------------------------------

@mcp.tool()
def identification_analysis(inp_path: str, d: int = 2, D: int = 0,
                             lam: float = 0.0) -> list:
    """
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
    """
    try:
        from art.describe import describe_identification
        ts, _ = _load_ts_model(inp_path)
        desc = describe_identification(ts, d=d, D=D, lam=lam)
        _show_fig(desc.figure_b64, "identification")
        return _result(desc)
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
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_prelim_scan
        ts, _ = _load_ts_model(inp_path)
        desc = describe_prelim_scan(ts, d=d, D=D, lam=lam, threshold=threshold)

        next_opts = (
            "\n\n---\n\n**¿Qué hacemos?**\n\n"
            "**A) Añadir intervención** → `suggest_intervention_form(date=\"MM/YYYY\", form=\"auto\")`\n"
            "  Repite hasta que los residuos estén limpios, luego pasa a identificación ARMA.\n\n"
            "**B) Continuar con ARMA sin intervenciones**\n"
            "  → `guided_identification(..., pre_path=\"<modelo_actual>.pre\")`\n"
            "  ⚠ Si hay outliers significativos, las ACF/PACF estarán distorsionadas.\n\n"
            "**¿Dudas?** Para ver cuánto distorsiona cada outlier la ACF, llama a:\n"
            "  `preliminary_outlier_scan(inp_path=\"<modelo_actual>.pre\", d=0, D=0, lam=1.0)`\n"
            "  (muestra contribución de cada outlier a cada lag de la ACF)"
        )

        text = desc.summary + "\n\n---\n" + desc.recommendation + next_opts
        items = [TextContent(type="text", text=text)]
        if desc.figure_b64:
            items.append(ImageContent(type="image",
                                      data=desc.figure_b64, mimeType="image/png"))
        return items
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
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        ts, m = _load_ts_model(inp_path)
        m.fit()
        try:
            from art.describe import model_equation as _model_eq
            eq_text = _model_eq(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"
        desc = describe_diagnosis(m)
        _show_fig(desc.figure_b64, "diagnosis")
        text = eq_text + "\n\n---\n\n" + desc.summary + "\n\n---\n" + desc.recommendation
        items = [TextContent(type="text", text=text)]
        if desc.figure_b64:
            items.append(ImageContent(type="image",
                                      data=desc.figure_b64, mimeType="image/png"))
        hist_b64 = desc.data.get("hist_b64")
        if hist_b64:
            items.append(ImageContent(type="image",
                                      data=hist_b64, mimeType="image/png"))
        return items
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Residuals histogram (optional complement to estimate_and_diagnose)
# ---------------------------------------------------------------------------

@mcp.tool()
def model_histogram(inp_path: str) -> list:
    """
    Show the residuals histogram with normal overlay for a fitted model.

    Optional complement to the basic Treadway diagnostic module
    (estimate_and_diagnose / confirm_and_estimate).  The histogram is not
    part of the basic diagnostic module — request it explicitly when you
    want to inspect the distributional shape of the residuals.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the estimated model
    """
    try:
        from mcp.types import ImageContent
        from art.describe import describe_diagnosis
        ts, m = _load_fitted(inp_path)
        desc = describe_diagnosis(m)
        b64 = desc.data.get("hist_b64") or desc.figure_b64
        if b64 is None:
            return _err("No se pudo generar el histograma de residuos.")
        return [ImageContent(type="image", data=b64, mimeType="image/png")]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Over-parameterization analysis (Bloque I)
# ---------------------------------------------------------------------------

@mcp.tool()
def overparameterization_analysis(inp_path: str, threshold: float = 0.7) -> list:
    """
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
    """
    try:
        import io, base64
        import numpy as np
        import matplotlib.pyplot as plt
        from mcp.types import TextContent, ImageContent
        from art.diagnosis import _compute_param_corr, _build_param_labels
        from art.describe import _fig_b64

        _, m = _load_fitted(inp_path)
        corr, pairs, labels = _compute_param_corr(m, threshold=threshold)

        if corr is None:
            return [TextContent(type="text",
                                text="No se pudo calcular la matriz de correlación "
                                     "(modelo no estimado o sin matriz de covarianza).")]

        n = corr.shape[0]

        # ── heatmap figure ────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(max(6, n * 0.42 + 1.5),
                                        max(5, n * 0.38 + 1.2)))
        im = ax.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
        plt.colorbar(im, ax=ax, fraction=0.03, pad=0.02)

        # Tick labels — show all if ≤20 params, else abbreviated
        tick_labels = labels if n <= 20 else [
            lbl if i in (0, n - 1) or i % max(1, n // 10) == 0 else ""
            for i, lbl in enumerate(labels)
        ]
        ax.set_xticks(range(n))
        ax.set_yticks(range(n))
        ax.set_xticklabels(tick_labels, rotation=90, fontsize=7)
        ax.set_yticklabels(tick_labels, fontsize=7)

        # Highlight cells with |corr| > threshold
        for i in range(n):
            for j in range(n):
                if i != j and abs(corr[i, j]) > threshold:
                    ax.add_patch(plt.Rectangle(
                        (j - 0.5, i - 0.5), 1, 1,
                        fill=False, edgecolor="gold", lw=1.5
                    ))

        # Draw box around ARMA+mu block (last ARMA params)
        n_arma = (
            sum(len(f) for f in (m.ar or []))
            + sum(len(f) for f in (m.ar_s or []))
            + sum(len(f) for f in (m.ma or []))
            + sum(len(f) for f in (m.ma_s or []))
            + (1 if getattr(m, "estimate_mu", False) else 0)
        )

        if n_arma > 0:
            i0 = n - n_arma
            rect = plt.Rectangle((i0 - 0.5, i0 - 0.5), n_arma, n_arma,
                                  fill=False, edgecolor="black", lw=2.0, linestyle="--")
            ax.add_patch(rect)

        ax.set_title(f"Correlación de parámetros — {m.series.name if m.series else ''}\n"
                     f"(n_param={n}, umbral={threshold})", fontsize=10)
        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)

        # ── text summary ──────────────────────────────────────────────────
        # Classify each pair:  "flt" = always structural, "arma" = check RV test,
        # "" = unknown/genuine overpar candidate
        def _classify(lbl_i: str, lbl_j: str) -> str:
            a, b_lbl = lbl_i.lower(), lbl_j.lower()
            # FLT transfer function: ω + δ always structural
            if ("ω(" in lbl_i or "δ(" in lbl_i) and ("ω(" in lbl_j or "δ(" in lbl_j):
                return "flt"
            if "ω(" in lbl_i and lbl_j.startswith("δ"):
                return "flt"
            if lbl_i.startswith("δ") and "ω(" in lbl_j:
                return "flt"
            # AR + MA mixed: may be structural if AR(2) with complex roots
            is_ar_i = lbl_i.startswith("AR")
            is_ma_i = lbl_i.startswith("MA")
            is_ar_j = lbl_j.startswith("AR")
            is_ma_j = lbl_j.startswith("MA")
            if (is_ar_i and is_ma_j) or (is_ma_i and is_ar_j):
                return "arma"
            return ""

        def _note_text(kind: str, lbl_i: str, lbl_j: str) -> str:
            if kind == "flt":
                return "FLT (ω,δ): estructural, sin acción"
            if kind == "arma":
                return "AR+MA: si AR(2) con φ₂<0 puede ser estructural → verificar test RV"
            return "Sobreparametrización probable → reducir modelo"

        lines = ["## Sobreparametrización — análisis de correlaciones de parámetros", ""]
        lines.append(f"Parámetros: **{n}**  |  Umbral: **|r| > {threshold}**")
        lines.append("")

        if not pairs:
            lines.append("✅ **Sin sobreparametrización detectada.** "
                         "Ningún par de parámetros supera el umbral de correlación.")
        else:
            lines.append(f"⚠ **{len(pairs)} par(es) con |r| > {threshold}:**")
            lines.append("")
            lines.append("| # | Param i | Param j | r | Diagnóstico |")
            lines.append("|---|---------|---------|---|------------|")
            for k, (i, j, r_val, lbl_i, lbl_j) in enumerate(pairs, 1):
                kind = _classify(lbl_i, lbl_j)
                note = _note_text(kind, lbl_i, lbl_j)
                lines.append(f"| {k} | {lbl_i} | {lbl_j} | {r_val:+.3f} | {note} |")
            lines.append("")

            flt_pairs   = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == "flt"]
            arma_pairs  = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == "arma"]
            true_pairs  = [(li, lj, rv) for _, _, rv, li, lj in pairs if _classify(li, lj) == ""]

            if flt_pairs:
                lines.append(f"**{len(flt_pairs)} par(es) FLT** — estructurales, no requieren acción.")
            if arma_pairs:
                lines.append(f"**{len(arma_pairs)} par(es) AR+MA** — verificar si AR(2) tiene raíces "
                              "complejas (φ₂ < 0). Si no, es sobreparametrización real.")
                lines.append("  → Aplicar `formal_tests` (test RV) para confirmarlo.")
            if true_pairs:
                lines.append("")
                lines.append("**Sobreparametrización confirmada — acción recomendada:**")
                for lbl_i, lbl_j, r_val in true_pairs:
                    lines.append(f"- Eliminar uno de: `{lbl_i}` / `{lbl_j}` "
                                 f"(|r|={abs(r_val):.3f}). "
                                 "Comparar AIC/BIC con `compare_versions`.")
            elif not true_pairs and not arma_pairs:
                lines.append("")
                lines.append("Todos los pares son estructurales. No se requiere acción.")

        lines += [
            "",
            "---",
            "**Matriz de correlación** — heatmap adjunto.",
            "Recuadro negro punteado = bloque ARMA+μ. Celdas con borde dorado = pares flagged.",
        ]

        text = "\n".join(lines)
        items = [TextContent(type="text", text=text)]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Formal tests
# ---------------------------------------------------------------------------

@mcp.tool()
def formal_tests(inp_path: str, run_meg: bool = True) -> list:
    """
    Run formal hypothesis tests on a fitted model.

    Tests run (where applicable to the model structure):
    - Shin-Fuller (1998): Phi_1u test; H0: rho=1-4/n (near-unit-root); crit 5%≈1.75
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
# Tool: Seasonal parameters (Bloque G)
# ---------------------------------------------------------------------------

@mcp.tool()
def seasonal_param_analysis(inp_path: str) -> list:
    """
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
    """
    try:
        from art.describe import describe_seasonal_params
        _, m = _load_fitted(inp_path)
        return _result(describe_seasonal_params(m))
    except Exception as e:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: Seasonal simplification (Bloque H)
# ---------------------------------------------------------------------------

@mcp.tool()
def test_seasonal_simplification(inp_path: str,
                                  freq_list: list[int] | None = None,
                                  alpha: float = 0.05) -> list:
    """
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
    """
    try:
        from art.describe import describe_seasonal_simplification
        _, m = _load_fitted(inp_path)
        return _result(describe_seasonal_simplification(m, freq_list=freq_list,
                                                        alpha=alpha))
    except Exception:
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

        ts, m = _load_fitted(inp_path)
        results = simplify_interventions(m, alpha=alpha)

        if not results:
            return [TextContent(type="text",
                                text="*No hay intervenciones no-estructurales en el modelo.*")]

        try:
            from art.describe import model_equation as _model_eq
            eq_text = _model_eq(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        summary   = simplify_summary(results, alpha=alpha)
        n_sig     = sum(1 for r in results if r.significant)
        n_nosig   = len(results) - n_sig

        text = (
            f"### Contraste de intervenciones — {m.series.name or 'modelo'}\n\n"
            + f"**{n_sig} significativas**, **{n_nosig} prescindibles**"
            + f" (α={alpha:.2f},  df={results[0].df})\n\n"
            + eq_text
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


def _build_arma_on_model(m_base, p: int, q: int,
                         P: int = 0, Q: int = 0,
                         estimate_mu: bool = False):
    """
    Return a new unfitted fue.Model that keeps all interventions and harmonics
    from m_base but replaces the ARMA specification with (p, q, P, Q).

    Used by confirm_and_estimate(base_pre_path=...) to add ARMA to a model
    that already has its outlier interventions estimated.
    """
    import fue

    if p > 0:
        ar   = [[0.0] * p]
        ar_f = [[True] * p]
    elif q == 0 and P == 0 and Q == 0:
        # Keep the p=0,q=0 workaround only when there is truly no ARMA at all
        ar   = m_base.ar or [[0.0]]
        ar_f = m_base.ar_free or [[False]]
    else:
        ar   = []
        ar_f = []

    ma   = [[-0.3] * q] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    ar_s_val  = [[0.0]  * P] if P > 0 else []
    ar_sf_val = [[True] * P] if P > 0 else []
    ma_s_val  = [[-0.3] * Q] if Q > 0 else []
    ma_sf_val = [[True] * Q] if Q > 0 else []

    return fue.Model(
        m_base.series,
        d=m_base.d, D=m_base.D, boxlam=m_base.boxlam,
        ar=ar,       ar_free=ar_f       if ar   else None,
        ma=ma,       ma_free=ma_f       if ma   else None,
        ar_s=ar_s_val,  ar_s_free=ar_sf_val if ar_s_val  else None,
        ma_s=ma_s_val,  ma_s_free=ma_sf_val if ma_s_val  else None,
        interventions=list(m_base.interventions or []),
        ifadf=list(m_base.ifadf or []),
        mu=0.0, estimate_mu=estimate_mu,
        refactor=m_base.refactor,
    )


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


def _auto_scan_section(ts, m, lam: float, d: int, D: int,
                        p: int, q: int, P: int, Q: int,
                        inp_path: str, pre_path: str
                        ) -> "tuple[str, str | None]":
    """Auto-scan model residuals for outlier impact; return (text_section, b64).

    Calls describe_prelim_scan on residuals (d=0, D=0, lam=1.0) and appends
    an A/B choice: A) add intervention, B) proceed (ARMA or formal tests).
    Returns ("", None) on any error.
    """
    try:
        import fue as _fue
        from art.describe import describe_prelim_scan as _prelim_scan, _resid_start
        if m.residuals is None:
            return "", None
        # m.residuals.start is unreliable (fue sets it to 1900); recompute it
        _rstart = _resid_start(m)
        _res_ts = _fue.TimeSeries(
            m.residuals.data, freq=ts.freq,
            start=_rstart, name=f"Resid {ts.name or ''}",
        )
        # 2.5 (more sensitive than the user-facing 3.5) so that marginal outliers
        # are flagged during the modeling cycle rather than after formal diagnosis.
        scan = _prelim_scan(_res_ts, d=0, D=0, lam=1.0, threshold=2.5)
        # Count only FREE (estimated) ARMA parameters to distinguish m00 from final
        def _n_free(vals, free):
            if not vals:
                return 0
            if free is None:
                return len(vals)
            return sum(1 for f in (free[0] if isinstance(free[0], (list, tuple)) else free) if f)
        has_arma = any([
            _n_free(m.ar,   m.ar_free)   > 0,
            _n_free(m.ma,   m.ma_free)   > 0,
            _n_free(m.ar_s, m.ar_s_free) > 0,
            _n_free(m.ma_s, m.ma_s_free) > 0,
        ])
        if has_arma:
            ab_choice = (
                "\n\n**¿Qué hacemos?**\n\n"
                "**A) Añadir intervención** (si aún hay anomalías significativas):\n"
                f"→ `suggest_intervention_form(inp_path=\"{pre_path}\", "
                "output_path=<próxima_versión.inp>, date=\"MM/YYYY\", form=\"auto\")`\n\n"
                "**B) Contrastes formales** (si los residuos están limpios):\n"
                "→ `formal_tests` / `simplify_interventions`"
            )
        else:
            ab_choice = (
                "\n\n**¿Qué hacemos?**\n\n"
                "**A) Añadir intervención** — intervenciones ANTES de ARMA:\n"
                f"→ `suggest_intervention_form(inp_path=\"{pre_path}\", "
                "output_path=<próxima_versión.inp>, date=\"MM/YYYY\", form=\"auto\")`\n"
                "   Repite hasta que los residuos estén limpios.\n\n"
                "**B) Identificar ARMA** — si los residuos ya están limpios:\n"
                f"→ `guided_identification(inp_path=\"{inp_path}\", "
                f"lam={lam}, d={d}, D={D}, pre_path=\"{pre_path}\")`"
            )
        section = "\n\n---\n\n" + scan.summary + "\n\n" + scan.recommendation + ab_choice
        return section, scan.figure_b64
    except Exception:
        return "", None


def _param_names(model) -> list[str]:
    """Build human-readable parameter names for a fue model.

    Follows the same ordering as fue's parameter vector:
    det-var omega coefs (free only), then ARMA coefs (free only).
    """
    from math import gcd

    ts    = model.series
    freq  = ts.freq if ts and ts.freq > 0 else 1
    start = ts.start if ts else (0, 1)
    by, bp = int(start[0]), (int(start[1]) if freq > 1 else 1)

    def _at_to_date(at_0based: int) -> str:
        off = (bp - 1) + at_0based
        p, y = off % freq + 1, by + off // freq
        if freq == 1:
            return str(y)
        if freq == 4:
            return f"Q{p}/{y}"
        return f"{p}/{y}"

    def _harm_frac(h: int) -> str:
        half = freq // 2
        g    = gcd(h, half)
        num, den = h // g, half // g
        if den == 1:
            return "π" if num == 1 else f"{num}π"
        return f"π/{den}" if num == 1 else f"{num}π/{den}"

    names = []

    for itv in (model.interventions or []):
        t = itv.type
        om_free = itv.omega_free if (hasattr(itv, "omega_free") and itv.omega_free) else [True]
        om      = itv.omega      if (hasattr(itv, "omega")      and itv.omega)      else [0.0]
        for i, (v, f) in enumerate(zip(om, om_free)):
            if f:
                if t in ("cos", "sin"):
                    h    = int(itv.harmonic) if hasattr(itv, "harmonic") else 1
                    frac = _harm_frac(h)
                    base = f"{t}({frac})"
                    label = base if i == 0 else f"{base}[ω{i}]"
                elif t == "alter":
                    label = "alter" if i == 0 else f"alter[ω{i}]"
                elif t in ("pulse", "impulse", "step", "ramp", "compimp"):
                    date = _at_to_date(itv.at)
                    base = f"{t}[{date}]"
                    label = base if i == 0 else f"{base}[ω{i}]"
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
                           d: int = -1, D: int = -1,
                           pre_path: str = "") -> list:
    """
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
        ¿Seasonal? + B1 (Treadway, deterministic harmonics, D=0):
          Confirm d and D=0, then:
            a) confirm_and_estimate(m00: harmonics only, p=0, q=0)
            b) preliminary_outlier_scan on m00 residuals
            c) [cycle: add steps → re-estimate → scan] until clean
            d) Call 4 with pre_path=<mNN.pre> (ARMA on clean residuals)
        ¿Seasonal? + B2 (Box-Jenkins multiplicative, D=1):
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
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_boxcox, describe_seasonality, describe_identification
        ts, _ = _load_ts_model(inp_path)

        # ── Call 1: Box-Cox scatter ────────────────────────────────────────
        if lam < 0:
            bc      = describe_boxcox(ts)
            rec_lam = bc.data["recommended_lambda"]

            # Index series rule: series without a natural zero base → always log
            _INDEX_PREFIXES = ("ipc", "ipi", "ipp", "cpi", "ppi", "cci",
                               "indice", "índice", "index", "idx", "price")
            name_lower = (ts.name or "").lower()
            is_index   = any(name_lower.startswith(p) for p in _INDEX_PREFIXES)
            if is_index and rec_lam != 0.0:
                rec_lam   = 0.0
                index_note = (
                    f"\n\n> ⚠ **REGLA ÍNDICE APLICADA:** «{ts.name or 'serie'}» es una "
                    "serie índice sin base natural — se impone **λ=0 (log)** "
                    "independientemente de las estadísticas Box-Cox."
                )
            else:
                index_note = ""

            _show_fig(bc.figure_b64, "boxcox")
            text = (
                "## Paso 1 — Transformación Box-Cox\n\n"
                + bc.summary + "\n\n---\n" + bc.recommendation
                + index_note
                + f"\n\n**Próximo paso:** confirma λ y llama con `lam={rec_lam}` "
                "(o el valor que decidas) para ver la serie transformada."
            )
            items = [TextContent(type="text", text=text)]
            if bc.figure_b64:
                items.append(ImageContent(type="image",
                                          data=bc.figure_b64, mimeType="image/png"))
            return items

        # ── Call 2: Series at d=0 + ADF/KPSS unit root table ─────────────
        if d < 0:
            from art.describe import describe_unit_root
            b64     = _plot_series_at_d(ts, lam=lam, d=0)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            _show_fig(b64, "series_d0")

            urt       = describe_unit_root(ts, lam=lam, max_d=2)
            rec_d     = urt.data.get("recommended_d", 1)

            text = (
                f"## Paso 2 — Serie transformada ({lam_str}), nivel d=0\n\n"
                "Observa la serie y su ACF/PACF:\n"
                "- **Tendencia visible** o ACF que decae muy lentamente → diferencia necesaria → d=1\n"
                "- **Sin tendencia aparente** → posiblemente d=0 es suficiente\n\n"
                "---\n\n"
                + urt.summary + "\n\n"
                + f"**Recomendación ADF+KPSS:** d = {rec_d}. {urt.recommendation}\n\n"
                "---\n\n"
                "**Confirma d y llama al paso 3:**\n"
                f"- ¿Hay tendencia? → `guided_identification(inp_path, lam={lam}, d=1)`\n"
                f"- ¿Sin tendencia? → `guided_identification(inp_path, lam={lam}, d=0, D=0)`"
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
            return items

        # ── Call 3: Series at level d, D not yet decided ──────────────────
        if D < 0:
            b64     = _plot_series_at_d(ts, lam=lam, d=d)
            lam_str = "log" if lam == 0.0 else f"λ={lam}"
            sym     = {0: "", 1: "∇", 2: "∇²"}.get(d, f"∇^{d}")
            _show_fig(b64, f"series_d{d}")

            sea_text = ""
            sea_fig  = None
            if d > 0:
                sea     = describe_seasonality(ts)
                _show_fig(sea.figure_b64, "seasonality")
                sea_fig  = sea.figure_b64
                sea_text = (
                    "\n\n**Test HAC de estacionalidad (soporte):**\n"
                    + sea.summary + "\n\n---\n" + sea.recommendation
                )

            n_harm = max(ts.freq // 2 - 1, 0)
            sname  = ts.name or "SERIE"

            # B1 path: estimate harmonics-only first, then outlier cycle, then ARMA
            b1_steps = (
                "\n\n### Ruta B1 (Treadway, D=0 + armónicos estacionales)\n\n"
                "Secuencia obligatoria — **intervenciones ANTES de ARMA**:\n\n"
                f"**1.** Estima m00 (armónicos estacionales, sin ARMA):\n"
                f"```\nconfirm_and_estimate(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    output_path=\"cases/{sname}/{sname}_m00.inp\",\n"
                f"    lam={lam}, d={d}, D=0, p=0, q=0, n_harmonics={n_harm}\n)\n```\n"
                f"*({n_harm} pares cos/sin + alter Nyquist = {n_harm + 1} componentes estacionales)*\n\n"
                f"**2.** Escanea residuos de m00 (outliers > 2.5σ):\n"
                f"```\npreliminary_outlier_scan(\n"
                f"    inp_path=\"cases/{sname}/{sname}_m00.pre\",\n"
                f"    d=0, D=0, lam=1.0, threshold=2.5\n)\n```\n\n"
                "**3.** [Ciclo hasta residuos limpios]:\n"
                "    `suggest_intervention_form` → `confirm_and_estimate` → "
                "`preliminary_outlier_scan`\n"
                "    Cada estimación guarda el `.pre` automáticamente.\n\n"
                "**4.** Cuando los residuos estén limpios, identifica ARMA sobre ellos:\n"
                f"```\nguided_identification(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    lam={lam}, d={d}, D=0,\n"
                f"    pre_path=\"cases/{sname}/{sname}_mNN.pre\"\n)\n```"
            )

            # B2 path: go directly to ARMA identification on ∇∇_s series
            b2_steps = (
                "\n\n### Ruta B2 (Box-Jenkins, D=1)\n\n"
                f"```\nguided_identification(\n"
                f"    inp_path=\"{inp_path}\",\n"
                f"    lam={lam}, d={d}, D=1\n)\n```\n"
                "Identifica p, q (regular) y P, Q (estacional) sobre ∇∇_s y(λ), "
                "luego llama a `confirm_and_estimate`."
            )

            b1_note = (
                "\n\n> **Hipótesis B1:** D=0 + armónicos es revisable. "
                "El contraste MEG (`formal_tests`) evalúa al final si alguna "
                "frecuencia requiere tratamiento estocástico."
            )

            text = (
                f"## Paso 3 — {sym}y({lam_str}), d={d}\n\n"
                "Observa la serie diferenciada y su ACF/PACF:\n\n"
                "**¿Estacionalidad?** (picos en ACF/PACF a lags s, 2s, 3s…)\n"
                "  - Picos regulares/estables → **B1** (D=0, armónicos deterministas)\n"
                "  - Picos muy dominantes o irregulares → **B2** (D=1, dif. estacional)\n"
                "  - Sin picos estacionales → D=0, sin armónicos, → Call 4 directo\n\n"
                "**¿Tendencia residual?** → considera d=" + str(d + 1)
                + sea_text + b1_note
                + b1_steps + b2_steps
            )
            items = [TextContent(type="text", text=text)]
            if b64:
                items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
            if sea_fig:
                items.append(ImageContent(type="image", data=sea_fig, mimeType="image/png"))
            return items

        # ── Call 4: ARMA identification ───────────────────────────────────
        # B1 with clean residuals: pre_path points to fitted model after outlier cycle
        # B2 or no-outlier B1: identify directly on transformed series
        if pre_path:
            import fue as _fue
            from art.describe import _resid_start as _rs
            _, m_pre = _load_fitted(pre_path)
            res_start = _rs(m_pre)
            res_ts = _fue.TimeSeries(
                m_pre.residuals.data, freq=ts.freq,
                start=res_start, name=f"Resid {ts.name or ''}"
            )
            ident      = describe_identification(res_ts, d=0, D=0, lam=1.0)
            data_label = f"residuos de `{os.path.basename(pre_path)}`"
        else:
            ident      = describe_identification(ts, d=d, D=D, lam=lam)
            data_label = f"∇^{d}∇_s^{D} y(λ={lam})"

        _show_fig(ident.figure_b64, "identification")
        top   = ident.data["suggestions"][0] if ident.data["suggestions"] else {}
        rec_p = top.get("p", 0)
        rec_q = top.get("q", 0)
        rec_P = top.get("P", 0)
        rec_Q = top.get("Q", 0)
        n_harm = max(ts.freq // 2 - 1, 0)

        # ── Mean significance check ───────────────────────────────────────────
        import numpy as _np
        from art.identification import boxcox_transform as _bct, apply_differences as _adiff
        _series_for_mu = (
            _np.array(m_pre.residuals.data) if pre_path else
            _np.array(_adiff(_bct(ts.data, lam), ts.freq, d, D))
        )
        _mu_bar = float(_np.mean(_series_for_mu))
        _se_mu  = float(_np.std(_series_for_mu, ddof=1) / _np.sqrt(len(_series_for_mu)))
        _t_mu   = _mu_bar / _se_mu if _se_mu > 0 else 0.0
        _rec_mu = abs(_t_mu) > 2.0
        mu_decision = (
            f"\n\n**¿Incluir media (μ)?** μ̄={_mu_bar:.4f}, SE={_se_mu:.4f}, "
            f"t={_t_mu:+.2f} → "
            + ("**Sí, `estimate_mu=True`** (|t|>2)" if _rec_mu
               else "**No, `estimate_mu=False`** (|t|≤2, media no significativa)")
        )

        if D == 1:
            # B2: regular + seasonal ARMA — check lags s, 2s for P, Q
            seasonal_note = (
                f"\n\n**Para P y Q (operadores estacionales, lag s={ts.freq}):**\n"
                f"- ACF en lag {ts.freq} significativo, PACF(lag {ts.freq}) decae → **Q=1** (SMA)\n"
                f"- PACF en lag {ts.freq} significativo, ACF(lag {ts.freq}) decae → **P=1** (SAR)\n"
                f"- Caso más común para mensuales con D=1: Q=1 → ARIMA×(0,1,1)_{ts.freq}\n"
                + mu_decision
            )
            next_call = (
                f"Llama a `confirm_and_estimate` con\n"
                f"`lam={lam}, d={d}, D=1, p=<p>, q=<q>, P=<P>, Q=<Q>"
                f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                f"*(Sugerencia: p={rec_p}, q={rec_q}, P={rec_P}, Q={rec_Q})*"
            )
        else:
            if pre_path:
                next_call = (
                    f"Llama a `confirm_and_estimate` añadiendo el ARMA al modelo "
                    f"de `{os.path.basename(pre_path)}`:\n"
                    f"`inp_path=\"{pre_path}\", output_path=..._mFinal.inp, "
                    f"lam={lam}, d={d}, D=0, p=<p>, q=<q>, n_harmonics={n_harm}"
                    f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                    f"*(Sugerencia: p={rec_p}, q={rec_q})*"
                )
            else:
                next_call = (
                    f"Llama a `confirm_and_estimate` con\n"
                    f"`lam={lam}, d={d}, D=0, p=<p>, q=<q>, n_harmonics={n_harm}"
                    f", estimate_mu={'True' if _rec_mu else 'False'}`\n"
                    f"*(Sugerencia: p={rec_p}, q={rec_q})*"
                )
            seasonal_note = mu_decision

        text = (
            f"## Paso 4 — Identificación ARMA  (sobre {data_label})\n\n"
            "**Regla ACF/PACF:**\n"
            "- PACF corta en lag p, ACF decae → **AR(p)**\n"
            "- ACF corta en lag q, PACF decae → **MA(q)**\n"
            "- Ambas decaen → **ARMA(p,q)**\n"
            "- Sin estructura → p=0, q=0\n"
            + seasonal_note + "\n\n"
            + ident.summary + "\n\n---\n" + ident.recommendation
            + "\n\n**Próximo paso:** " + next_call
        )
        items = [TextContent(type="text", text=text)]
        if ident.figure_b64:
            items.append(ImageContent(type="image",
                                      data=ident.figure_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Guion helper — called by confirm_and_estimate and record_version
# ---------------------------------------------------------------------------

def _record_to_guion(
    model,
    inp_path: str,
    lam: float,
    guion_path: str,
    name: str = "",
    decision: str = "",
    rationale: str = "",
    problems_found: str = "",
    next_version: str = "",
    figure_b64: str | None = None,
) -> str:
    """
    Add a fitted model entry to guion.json (creates file if absent).
    Returns a one-line confirmation string for the caller.
    """
    from datetime import datetime
    from art.guion import (
        Guion, GuionEntry, load_guion, save_guion,
        _extract_spec, _extract_stats, _build_equation,
    )
    from art.diagnosis import diagnose

    guion_path = os.path.expanduser(guion_path)

    if os.path.exists(guion_path):
        guion = load_guion(guion_path)
    else:
        ts = model.series
        guion = Guion(
            series=ts.name or os.path.basename(inp_path),
            analyst="",
            created=datetime.now().strftime("%Y-%m-%d"),
        )

    version = (max(e.version for e in guion.entries) + 1) if guion.entries else 1
    if not name:
        name = f"PC{version}"

    diag_result = diagnose(model)
    spec  = _extract_spec(model, lam)
    stats = _extract_stats(model, diag_result)
    eq    = _build_equation(spec, model.series.freq)

    entry = GuionEntry(
        version=version,
        name=name,
        inp_path=inp_path,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        spec=spec,
        stats=stats,
        equation=eq,
        decision=decision,
        rationale=rationale,
        problems_found=problems_found,
        next_version=next_version,
        figure_b64=figure_b64,
    )
    guion.entries.append(entry)
    save_guion(guion, guion_path)
    return f"*Registrado en guion como {name} (v{version}) → {guion_path}*"


# ---------------------------------------------------------------------------
# Tool: confirm and estimate (B2)
# ---------------------------------------------------------------------------

@mcp.tool()
def confirm_and_estimate(inp_path: str, output_path: str,
                          lam: float = 0.0, d: int = 1, D: int = 0,
                          p: int = 0, q: int = 1,
                          n_harmonics: int = 5,
                          P: int = 0, Q: int = 0,
                          base_pre_path: str = "",
                          estimate_mu: bool = False,
                          include_histogram: bool = False,
                          guion_path: str = "",
                          guion_name: str = "",
                          guion_decision: str = "",
                          guion_rationale: str = "",
                          guion_problems: str = "",
                          guion_next: str = "") -> list:
    """
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
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import describe_diagnosis
        import fue

        ts, _ = _load_ts_model(inp_path)
        output_path = os.path.expanduser(output_path)

        if base_pre_path:
            # Incremental: preserve interventions + harmonics from .pre; replace ARMA
            base_pre_path = os.path.expanduser(base_pre_path)
            _, m_base = _load_ts_model(base_pre_path)
            ts_b = m_base.series
            if ts.nobs != ts_b.nobs or ts.freq != ts_b.freq:
                raise ValueError(
                    f"Series mismatch between inp_path and base_pre_path: "
                    f"nobs {ts.nobs} vs {ts_b.nobs}, freq {ts.freq} vs {ts_b.freq}"
                )
            m = _build_arma_on_model(m_base, p=p, q=q, P=P, Q=Q,
                                     estimate_mu=estimate_mu)
            _write_inp(ts, m, output_path)
        else:
            m_fresh = _make_model(ts, lam=lam, d=d, D=D, p=p, q=q,
                                  n_harmonics=n_harmonics, P=P, Q=Q,
                                  estimate_mu=estimate_mu)
            _write_inp(ts, m_fresh, output_path)

        _, m = _load_fitted(output_path)

        # Parameter table
        if base_pre_path:
            n_itvs = len(m.interventions) if m.interventions else 0
            spec_str = (f"ARIMA({p},{d},{q}) + {n_itvs} interv. "
                        f"[desde {os.path.basename(base_pre_path)}]")
        elif D == 1 and (P > 0 or Q > 0):
            spec_str = f"SARIMA({p},{d},{q})({P},{D},{Q})_{ts.freq}"
        elif D == 1:
            spec_str = f"ARIMA({p},{d},{q}) D=1"
        else:
            spec_str = f"ARIMA({p},{d},{q}) armónicos={n_harmonics}"
        spec_line = f"**{spec_str}  λ={lam}**  —  {ts.name or 'series'}"

        # Model equation replaces the parameter table
        try:
            from art.describe import model_equation as _model_eq
            eq_text = _model_eq(ts, m)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        # Diagnosis
        diag = describe_diagnosis(m)

        # Auto-save fitted model as .pre (same name as .inp but .pre extension)
        pre_path = os.path.splitext(output_path)[0] + ".pre"
        try:
            m.write_pre(pre_path)
            pre_note = f"\n\n*Modelo guardado en: {output_path}  |  parámetros en: {pre_path}*"
        except Exception:
            pre_note = f"\n\n*Modelo guardado en: {output_path}*"

        # Optional guion recording
        guion_note = ""
        if guion_path:
            guion_note = _record_to_guion(
                model=m, inp_path=output_path, lam=lam,
                guion_path=guion_path,
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale, problems_found=guion_problems,
                next_version=guion_next,
                figure_b64=diag.figure_b64,
            )

        scan_section, scan_b64 = _auto_scan_section(
            ts, m, lam=lam, d=d, D=D, p=p, q=q, P=P, Q=Q,
            inp_path=inp_path, pre_path=pre_path,
        )

        text = (
            spec_line + "\n\n"
            + eq_text
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + scan_section
            + pre_note
            + (f"\n\n{guion_note}" if guion_note else "")
        )

        _show_fig(diag.figure_b64, "diagnosis")
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        if scan_b64:
            items.append(ImageContent(type="image",
                                      data=scan_b64, mimeType="image/png"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(ImageContent(type="image",
                                          data=hist_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: record_version — add fitted model to guion.json  (Bloque P)
# ---------------------------------------------------------------------------

@mcp.tool()
def record_version(inp_path: str,
                   guion_path: str,
                   name: str = "",
                   decision: str = "",
                   rationale: str = "",
                   problems_found: str = "",
                   next_version: str = "") -> list:
    """
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
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.describe import _fig_b64
        from art.diagnosis import diagnose, plot_diagnosis
        import matplotlib.pyplot as plt

        _, m = _load_fitted(inp_path)

        # Diagnosis figure
        diag_result = diagnose(m)
        try:
            fig = plot_diagnosis(diag_result, m)
            b64 = _fig_b64(fig)
            plt.close(fig)
        except Exception:
            b64 = None

        lam = float(getattr(m, "boxlam", 0.0) or 0.0)

        note = _record_to_guion(
            model=m, inp_path=inp_path, lam=lam,
            guion_path=guion_path, name=name,
            decision=decision, rationale=rationale,
            problems_found=problems_found, next_version=next_version,
            figure_b64=b64,
        )

        lines = [
            f"### Versión registrada en guion",
            note,
            "",
            f"**loglik** = {m._result.loglik:.3f}",
            f"**AIC** = {m._result.aic:.2f}" if m._result.aic else "",
            f"**Q-pass** = {diag_result.white_noise} | **JB-pass** = {diag_result.normal}",
            f"**Anomalías** = {len(diag_result.extreme)}",
        ]
        items = [TextContent(type="text", text="\n".join(l for l in lines if l))]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: export_guion — render guion.json to HTML  (Bloque P)
# ---------------------------------------------------------------------------

@mcp.tool()
def export_guion(guion_path: str, output_html: str) -> list:
    """
    Render guion.json to a self-contained, navigable HTML report.

    Generates a single HTML file with:
    - Summary table of all versions (loglik, AIC, BIC, Q✓, JB✓, anomalías)
    - One collapsible section per version with equation, spec, stats, figure,
      decision notes, and link to next version

    Parameters
    ----------
    guion_path  : path to guion.json
    output_html : path to write the .html file
    """
    try:
        from mcp.types import TextContent
        from art.guion import load_guion, export_guion_html

        guion_path  = os.path.expanduser(guion_path)
        output_html = os.path.expanduser(output_html)

        guion = load_guion(guion_path)
        html  = export_guion_html(guion)

        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        with open(output_html, "w", encoding="utf-8") as f:
            f.write(html)

        n = len(guion.entries)
        text = (
            f"### Guion exportado\n\n"
            f"- Serie: **{guion.series}**\n"
            f"- Versiones: **{n}**\n"
            f"- HTML guardado en: `{output_html}`\n\n"
            f"Abre el fichero en un navegador para navegar el historial de versiones."
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: compare_versions — side-by-side model comparison  (Bloque Q)
# ---------------------------------------------------------------------------

def _spec_diff(spec_a: dict, spec_b: dict) -> list[str]:
    """Return list of 'key: a→b' strings for each spec field that changed."""
    changes = []
    for key in ("d", "D", "p", "q", "P", "Q", "n_harmonics"):
        a, b = spec_a.get(key, 0), spec_b.get(key, 0)
        if a != b:
            changes.append(f"{key}: {a}→{b}")
    itvs_a = {(iv.get("type", "?"), iv.get("date", "?"))
               for iv in spec_a.get("interventions", [])}
    itvs_b = {(iv.get("type", "?"), iv.get("date", "?"))
               for iv in spec_b.get("interventions", [])}
    for t, d in sorted(itvs_b - itvs_a):
        changes.append(f"+{t}({d})")
    for t, d in sorted(itvs_a - itvs_b):
        changes.append(f"−{t}({d})")
    return changes


def _nested_relation(spec_a: dict, spec_b: dict,
                     npar_a: int, npar_b: int) -> str:
    """
    Return "A_in_B", "B_in_A", or "none".

    A is nested in B if d,D match, p_a≤p_b, q_a≤q_b, P_a≤P_b, Q_a≤Q_b,
    n_h_a≤n_h_b, all interventions of A are in B, and npar_a < npar_b.
    """
    def a_in_b(sa, sb, na, nb):
        if na >= nb:
            return False
        if sa.get("d") != sb.get("d") or sa.get("D") != sb.get("D"):
            return False
        for k in ("p", "q", "P", "Q", "n_harmonics"):
            if sa.get(k, 0) > sb.get(k, 0):
                return False
        itvs_a = {(iv.get("type"), iv.get("date"))
                   for iv in sa.get("interventions", [])}
        itvs_b = {(iv.get("type"), iv.get("date"))
                   for iv in sb.get("interventions", [])}
        return itvs_a <= itvs_b

    if a_in_b(spec_a, spec_b, npar_a, npar_b):
        return "A_in_B"
    if a_in_b(spec_b, spec_a, npar_b, npar_a):
        return "B_in_A"
    return "none"


@mcp.tool()
def compare_versions(inp_path_a: str, inp_path_b: str,
                     lam_a: float = 0.0, lam_b: float = 0.0,
                     guion_path: str = "") -> list:
    """
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
    """
    try:
        from mcp.types import TextContent, ImageContent
        from art.guion import _extract_spec, _build_equation
        from art.diagnosis import diagnose
        from art.describe import _fig_b64
        from art.identification import _default_lags_fug
        from fue.diagnostics import acf as _fue_acf, pacf as _fue_pacf
        from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines
        import numpy as np
        import scipy.stats as sp_stats
        import matplotlib.pyplot as plt

        _, ma = _load_fitted(inp_path_a)
        _, mb = _load_fitted(inp_path_b)

        spec_a = _extract_spec(ma, lam=lam_a)
        spec_b = _extract_spec(mb, lam=lam_b)
        eq_a   = _build_equation(spec_a, ma.series.freq)
        eq_b   = _build_equation(spec_b, mb.series.freq)

        diag_a = diagnose(ma)
        diag_b = diagnose(mb)

        la, lb = ma._result.loglik, mb._result.loglik
        aic_a, bic_a = ma._result.aic, ma._result.bic
        aic_b, bic_b = mb._result.aic, mb._result.bic
        npar_a, npar_b = ma._result.npar, mb._result.npar
        import math
        sa = math.sqrt(ma._result.sigma2) if ma._result.sigma2 > 0 else 0.0
        sb = math.sqrt(mb._result.sigma2) if mb._result.sigma2 > 0 else 0.0

        name_a = os.path.basename(inp_path_a)
        name_b = os.path.basename(inp_path_b)

        # ── Spec diff ──────────────────────────────────────────────────────
        changes = _spec_diff(spec_a, spec_b)
        diff_str = (", ".join(changes)) if changes else "Sin cambios en la estructura"

        # ── Nested LR test ─────────────────────────────────────────────────
        nested = _nested_relation(spec_a, spec_b, npar_a, npar_b)
        lr_lines = []
        if nested == "A_in_B":
            lr = 2.0 * (lb - la)
            df = npar_b - npar_a
            pval = sp_stats.chi2.sf(lr, df) if lr > 0 else 1.0
            verdict = "B mejora significativamente ✓" if pval < 0.05 else "mejora no significativa ✗"
            lr_lines = [
                f"**Test LR** (B es más rico, A ⊂ B):",
                f"LR = 2·({lb:.3f}−{la:.3f}) = **{lr:.3f}**, df={df}, p={pval:.4f} → {verdict}",
            ]
        elif nested == "B_in_A":
            lr = 2.0 * (la - lb)
            df = npar_a - npar_b
            pval = sp_stats.chi2.sf(lr, df) if lr > 0 else 1.0
            verdict = "A mejora significativamente ✓" if pval < 0.05 else "mejora no significativa ✗"
            lr_lines = [
                f"**Test LR** (A es más rico, B ⊂ A):",
                f"LR = 2·({la:.3f}−{lb:.3f}) = **{lr:.3f}**, df={df}, p={pval:.4f} → {verdict}",
            ]
        else:
            lr_lines = ["Modelos no anidados — test LR no aplicable."]

        # ── Stats comparison table ─────────────────────────────────────────
        def _fmt(v, fmt=".2f"):
            return f"{v:{fmt}}" if v is not None else "—"

        delta_loglik = lb - la
        delta_aic    = (bic_b or 0) - (bic_a or 0)  # use BIC for penalty
        delta_aic_v  = (aic_b or 0) - (aic_a or 0)

        rows = [
            ("", f"**{name_a}**", f"**{name_b}**", "**Δ (B−A)**"),
            ("loglik", _fmt(la, ".3f"), _fmt(lb, ".3f"), f"{delta_loglik:+.3f}"),
            ("AIC",    _fmt(aic_a), _fmt(aic_b), f"{delta_aic_v:+.2f}"),
            ("BIC",    _fmt(bic_a), _fmt(bic_b), f"{delta_aic:+.2f}"),
            ("σ_a",   f"{sa:.5f}", f"{sb:.5f}", f"{sb-sa:+.5f}"),
            ("npar",  str(npar_a), str(npar_b), f"{npar_b-npar_a:+d}"),
            ("Q✓",    "✓" if diag_a.white_noise else "✗",
                      "✓" if diag_b.white_noise else "✗", ""),
            ("JB✓",   "✓" if diag_a.normal else "✗",
                      "✓" if diag_b.normal else "✗", ""),
            ("Anomalías", str(len(diag_a.extreme)), str(len(diag_b.extreme)), ""),
        ]
        col_w = [max(len(r[i]) for r in rows) for i in range(4)]
        tbl = []
        for row in rows:
            tbl.append("| " + " | ".join(cell.ljust(col_w[i]) for i, cell in enumerate(row)) + " |")
        sep = "|" + "|".join("-" * (w + 2) for w in col_w) + "|"
        tbl.insert(1, sep)

        # ── ACF/PACF comparison figure ─────────────────────────────────────
        res_a = np.asarray(diag_a.residuals, dtype=float)
        res_b = np.asarray(diag_b.residuals, dtype=float)
        freq  = ma.series.freq
        lags  = _default_lags_fug(min(len(res_a), len(res_b)), freq)
        lag_x = np.arange(1, lags + 1)

        acf_a_arr  = np.asarray(_fue_acf(res_a,  lags=lags), dtype=float)
        acf_b_arr  = np.asarray(_fue_acf(res_b,  lags=lags), dtype=float)
        pacf_a_arr = np.asarray(_fue_pacf(res_a, lags=lags), dtype=float)
        pacf_b_arr = np.asarray(_fue_pacf(res_b, lags=lags), dtype=float)

        band_a = 1.96 / np.sqrt(len(res_a))
        band_b = 1.96 / np.sqrt(len(res_b))

        all_acf  = np.concatenate([acf_a_arr,  acf_b_arr])
        all_pacf = np.concatenate([pacf_a_arr, pacf_b_arr])
        cmax = _snap_cmax(all_acf, all_pacf)

        fig, axes = plt.subplots(3, 2, figsize=(14, 10))
        fig.suptitle(f"Comparación: {name_a}  vs  {name_b}", fontsize=11, fontweight="bold")

        # Row 0: standardized residuals
        for col, (res, name_lbl) in enumerate([(res_a, name_a), (res_b, name_b)]):
            ax = axes[0, col]
            r_std_v = res.std(ddof=1) if len(res) > 1 else 1.0
            r_z = (res - res.mean()) / r_std_v if r_std_v > 0 else res
            ax.axhline(0, color="black", lw=0.8)
            ax.axhline(+2, color="red", lw=0.6, ls="--")
            ax.axhline(-2, color="red", lw=0.6, ls="--")
            ax.plot(np.arange(len(r_z)), r_z, color="#333333", lw=0.8)
            ax.set_title(f"Residuos — {name_lbl}", fontsize=9)
            _tj_spines(ax)

        # Rows 1-2: ACF and PACF
        acf_pacf_panels = [
            (axes[1, 0], acf_a_arr,  band_a, f"ACF — {name_a}"),
            (axes[1, 1], acf_b_arr,  band_b, f"ACF — {name_b}"),
            (axes[2, 0], pacf_a_arr, band_a, f"PACF — {name_a}"),
            (axes[2, 1], pacf_b_arr, band_b, f"PACF — {name_b}"),
        ]
        for ax, vals, band, title in acf_pacf_panels:
            _draw_acf_panel(ax, lag_x, vals, band=band, cmax=cmax,
                            freq=freq, lags=lags, label=title)

        fig.tight_layout()
        b64 = _fig_b64(fig)
        plt.close(fig)

        # ── Compose text ───────────────────────────────────────────────────
        lines = [
            f"## Comparación de versiones",
            f"",
            f"**A**: `{name_a}` — `{eq_a}`",
            f"**B**: `{name_b}` — `{eq_b}`",
            f"",
            f"**Cambios (A→B)**: {diff_str}",
            f"",
            "### Estadísticos",
        ] + tbl + [""] + lr_lines

        items = [TextContent(type="text", text="\n".join(lines))]
        if b64:
            items.append(ImageContent(type="image", data=b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: suggest intervention form (B3)
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_intervention_form(inp_path: str, output_path: str,
                               date: str = "",
                               form: str = "auto",
                               context_hint: str = "",
                               include_histogram: bool = False,
                               guion_path: str = "",
                               guion_name: str = "",
                               guion_decision: str = "",
                               guion_rationale: str = "",
                               guion_problems: str = "",
                               guion_next: str = "") -> list:
    """
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

        # Load current model to inspect residuals and build the new spec
        ts, m_src = _load_fitted(inp_path)

        freq  = ts.freq
        start = list(ts.start)
        s0y, s0p = start[0], (start[1] if freq > 1 else 1)

        if not date.strip():
            # Auto-select most extreme residual not already covered by an intervention
            import numpy as np
            from art.diagnosis import diagnose
            # 2.0: wide net for auto-selection so marginal extremes are candidates
            diag_auto = diagnose(m_src, z_threshold=2.0)
            existing_at = {itv.at for itv in (m_src.interventions or [])}
            candidates = [(abs(z), obs) for obs, z in diag_auto.extreme
                          if (obs - 1) not in existing_at]
            if not candidates:
                return _err("No se encontraron residuos extremos sin intervención asignada. "
                            "Proporciona date manualmente.")
            _, obs_1based = max(candidates)
            at_0 = obs_1based - 1
            # Convert obs index → calendar date string for the note
            total = (s0p - 1) + at_0
            if freq == 12:
                auto_date = f"{total % 12 + 1:02d}/{s0y + total // 12}"
            elif freq == 4:
                auto_date = f"Q{total % 4 + 1}/{s0y + total // 4}"
            else:
                auto_date = str(s0y + total)
            date_note = f"Fecha auto-detectada (residuo más extremo sin intervención): **{auto_date}**"
        else:
            period, year = _parse_date(date)
            at_0 = (year - s0y) * freq + (period - s0p)
            if at_0 < 0 or at_0 >= ts.nobs:
                raise ValueError(f"Date {date} gives obs={at_0+1}, outside series range [1, {ts.nobs}].")
            date_note = f"Fecha: **{date}**"

        if form == "auto":
            # Inspect residuals around that observation
            from art.diagnosis import diagnose
            # 2.5: moderate threshold to detect consecutive extremes that signal a step
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

        diag = describe_diagnosis(m_fit)

        try:
            from art.describe import model_equation as _model_eq
            eq_text = _model_eq(ts, m_fit)
        except Exception as _eq_exc:
            eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"

        context_str = f"  Contexto: {context_hint}" if context_hint else ""

        # Optional guion recording
        guion_note = ""
        if guion_path:
            lam_fit = float(getattr(m_fit, "boxlam", 0.0) or 0.0)
            guion_note = _record_to_guion(
                model=m_fit, inp_path=output_path, lam=lam_fit,
                guion_path=guion_path,
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale, problems_found=guion_problems,
                next_version=guion_next,
                figure_b64=diag.figure_b64,
            )

        new_pre_path = os.path.splitext(output_path)[0] + ".pre"
        lam_fit = float(getattr(m_fit, "boxlam", 0.0) or 0.0)
        d_fit   = int(getattr(m_fit, "d", 0) or 0)
        D_fit   = int(getattr(m_fit, "D", 0) or 0)
        p_fit   = len(m_fit.ar)   if getattr(m_fit, "ar",   None) else 0
        q_fit   = len(m_fit.ma)   if getattr(m_fit, "ma",   None) else 0
        P_fit   = len(m_fit.ar_s) if getattr(m_fit, "ar_s", None) else 0
        Q_fit   = len(m_fit.ma_s) if getattr(m_fit, "ma_s", None) else 0
        scan_section, scan_b64 = _auto_scan_section(
            ts, m_fit, lam=lam_fit, d=d_fit, D=D_fit,
            p=p_fit, q=q_fit, P=P_fit, Q=Q_fit,
            inp_path=inp_path, pre_path=new_pre_path,
        )

        text = (
            f"**Intervención añadida:** {form.upper()}  {date_note}{context_str}\n\n"
            + eq_text
            + "\n\n---\n\n"
            + diag.summary + "\n\n---\n" + diag.recommendation
            + scan_section
            + f"\n\n*Modelo actualizado en: {output_path}*"
            + (f"\n\n{guion_note}" if guion_note else "")
        )

        _show_fig(diag.figure_b64, "diagnosis")
        items = [TextContent(type="text", text=text)]
        if diag.figure_b64:
            items.append(ImageContent(type="image",
                                      data=diag.figure_b64, mimeType="image/png"))
        if scan_b64:
            items.append(ImageContent(type="image",
                                      data=scan_b64, mimeType="image/png"))
        if include_histogram:
            hist_b64 = diag.data.get("hist_b64")
            if hist_b64:
                items.append(ImageContent(type="image",
                                          data=hist_b64, mimeType="image/png"))
        return items

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Helpers for autonomous pipeline (Block C)
# ---------------------------------------------------------------------------

def _make_model(ts, lam: float, d: int, D: int,
                p: int, q: int, n_harmonics: int,
                extra_itvs: list | None = None,
                P: int = 0, Q: int = 0,
                estimate_mu: bool = False):
    """
    Build a fue.Model from SARIMA(p,d,q)(P,D,Q)_s spec.

    When D=0: harmonic det-vars (cos/sin + alter) + optional extra interventions.
    When D=1: seasonal AR/MA operators; no harmonics added.
    extra_itvs : list of (at_0based, form_str) tuples for pulse/step/ramp

    Known fue C backend bug: combining ar_s (P≥1) AND ma_s (Q≥1) simultaneously
    crashes the C estimator (Aborted/segfault — see fue/TODO.md, AR_s+MA_s entry).
    Only P=0,Q≥1 or P≥1,Q=0 are safe.  Use estimate_py() as workaround if needed.
    """
    import fue
    freq = ts.freq

    # Workaround for fue C crash when nar=0 AND nma=0: add AR(1) phi=0 fixed.
    if p > 0:
        ar   = [[0.0] * p]
        ar_f = [[True] * p]
    elif q == 0:
        ar   = [[0.0]]
        ar_f = [[False]]
    else:
        ar   = []
        ar_f = []
    ma   = [[-0.3] * q] if q > 0 else []
    ma_f = [[True]  * q] if q > 0 else []

    if D == 0:
        # Deterministic seasonality: pairs 1..freq//2-1 + alter (Nyquist harmonic).
        max_pairs = max(freq // 2 - 1, 0)
        n_harm    = min(n_harmonics, max_pairs)
        itvs = []
        for k in range(1, n_harm + 1):
            itvs.append(fue.Intervention("cos", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
            itvs.append(fue.Intervention("sin", at=0, omega=[0.0], omega_free=[True], harmonic=float(k)))
        itvs.append(fue.Intervention("alter", at=0, omega=[0.0], omega_free=[True]))
        ar_s_val = []; ar_sf_val = []
        ma_s_val = []; ma_sf_val = []
    else:
        itvs = []
        ar_s_val  = [[0.0]  * P] if P > 0 else []
        ar_sf_val = [[True] * P] if P > 0 else []
        ma_s_val  = [[-0.3] * Q] if Q > 0 else []
        ma_sf_val = [[True] * Q]  if Q > 0 else []

    if extra_itvs:
        for at_0, form in extra_itvs:
            itvs.append(fue.Intervention(form, at=int(at_0), omega=[0.0], omega_free=[True]))

    return fue.Model(
        ts,
        d=d, D=D, boxlam=lam,
        ar=ar, ar_free=ar_f,
        ma=ma, ma_free=ma_f,
        ar_s=ar_s_val, ar_s_free=ar_sf_val if ar_sf_val else None,
        ma_s=ma_s_val, ma_s_free=ma_sf_val if ma_sf_val else None,
        interventions=itvs,
        ifadf=[0] * (freq // 2 + 1),
        mu=0.0, estimate_mu=estimate_mu,
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
                run_meg: bool = False,
                guion_path: str = "",
                guion_name: str = "",
                guion_decision: str = "",
                guion_rationale: str = "") -> list:
    """
    Autonomous Box-Jenkins-Treadway pipeline for a single series.

    Automatically selects lambda, d, D, p, q; estimates the model; adds
    interventions for detected outliers and re-estimates until the diagnosis
    is clean or max_rounds is reached. Always returns parameters + residual
    diagnosis figure. Formal tests (DCD, MEG) are run at the end.

    Parameters
    ----------
    inp_path      : source .inp file — only the series is used
    output_path   : path for the final estimated .inp
    max_rounds    : maximum intervention-addition rounds (default 5)
    run_meg       : run MEG stochastic seasonality test (slow; default False)
    guion_path    : (optional) path to guion.json — records the final model
    guion_name    : version name (e.g. "PC1"); auto-assigned if empty
    guion_decision: brief description of the model or pipeline result
    guion_rationale: justification for the auto-selected spec
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
        D        = seas.data.get("recommended_D", 0)
        decision = seas.data.get("decision", "B1")
        # freq//2-1 pairs + alter = full deterministic spec (Nyquist covered by alter)
        n_harmonics = max(ts.freq // 2 - 1, 0) if decision != "A" else 0
        # Use unit root tests (Bloque L) to determine d
        from art.describe import describe_unit_root
        urt = describe_unit_root(ts, lam=lam)
        d   = urt.data.get("recommended_d", 1)
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
            # 3.0: autonomous pipeline uses a tighter threshold than user-facing 3.5
            # to avoid leaving marginal outliers unmodelled in the automated cycle.
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

        # ── Model equation and final description ──────────────────────────
        if m_fit is not None:
            try:
                from art.describe import model_equation as _model_eq
                eq_text = _model_eq(ts, m_fit)
            except Exception as _eq_exc:
                eq_text = f"⚠ *[model_equation error: {_eq_exc}]*"
            diag_desc = describe_diagnosis(m_fit)
            diag_text = diag_desc.summary + "\n\n---\n" + diag_desc.recommendation
        else:
            eq_text   = "*Modelo no estimado.*"
            diag_text = "*Sin diagnosis disponible.*"

        formal_md = _format_dcd_meg(dcd_results, meg_results)

        # Optional guion recording of final model
        guion_note = ""
        if guion_path and m_fit is not None:
            guion_note = _record_to_guion(
                model=m_fit, inp_path=output_path, lam=lam,
                guion_path=guion_path,
                name=guion_name, decision=guion_decision,
                rationale=guion_rationale,
                figure_b64=diag_desc.figure_b64 if m_fit is not None else None,
            )

        text = (
            "\n".join(log)
            + "\n\n" + eq_text
            + "\n\n---\n\n" + diag_text
            + "\n\n---\n\n### Contrastes formales\n\n" + formal_md
            + f"\n\n*Modelo guardado en: {output_path}*"
            + (f"\n\n{guion_note}" if guion_note else "")
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
                D        = seas.data.get("recommended_D", 0)
                decision = seas.data.get("decision", "B1")
                n_harm   = max(ts.freq // 2 - 1, 0) if decision != "A" else 0
                from art.describe import describe_unit_root as _durt
                urt = _durt(ts, lam=lam)
                d   = urt.data.get("recommended_d", 1)

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
                    # 3.0: tighter than user-facing 3.5 to catch marginal outliers in automated cycle
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
# Block R helpers — forecasting
# ---------------------------------------------------------------------------

def _forecast_date(start: tuple, nobs: int, freq: int, offset: int = 0) -> str:
    """Calendar label for obs index nobs-1+offset (0-based offset from obs nobs)."""
    y0, p0 = int(start[0]), int(start[1])
    total = (p0 - 1) + (nobs - 1) + offset
    if freq == 12:
        return f"{total % 12 + 1:02d}/{y0 + total // 12}"
    if freq == 4:
        return f"Q{total % 4 + 1}/{y0 + total // 4}"
    return str(y0 + total)


def _fuf_path(path: str) -> str:
    """Ensure fuf file path ends with .inp (required by fue.load_fuf)."""
    if not path.endswith(".inp") and not path.endswith(".pre"):
        path += ".inp"
    return path


# ---------------------------------------------------------------------------
# Tool: generate_forecast — fuf previsión desde modelo estimado  (Bloque R)
# ---------------------------------------------------------------------------

@mcp.tool()
def generate_forecast(inp_path: str,
                      horizon: int,
                      output_fuf_path: str,
                      output_html: str) -> list:
    """
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
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        from fue.report_forecast import write_forecast_report

        # 1. Fit from .pre → write fuf
        _, m = _load_fitted(inp_path)

        output_fuf_path = _fuf_path(os.path.expanduser(output_fuf_path))
        os.makedirs(os.path.dirname(os.path.abspath(output_fuf_path)), exist_ok=True)
        m.write_fuf(horizon=horizon, path=output_fuf_path)

        # 2. Reload as fuf model → forecast_fuf (correct fuf workflow)
        ts_fuf, m_fuf = _fue.load_fuf(output_fuf_path)
        fr = m_fuf.forecast_fuf()

        # 3. Write HTML report
        output_html = os.path.expanduser(output_html)
        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        write_forecast_report(m_fuf, fr, path=output_html,
                              title=ts_fuf.name or "", source=inp_path)

        last_date = _forecast_date(ts_fuf.start, ts_fuf.nobs, ts_fuf.freq, 0)
        end_date  = _forecast_date(ts_fuf.start, ts_fuf.nobs + 1, ts_fuf.freq, horizon - 1)

        text = (
            f"## Previsiones — {ts_fuf.name or 'Serie'} "
            f"({last_date} → {end_date}, horizonte={horizon})\n\n"
            f"σ̂_a = {fr.sigma2**0.5:.6f}\n\n"
            f"Archivo fuf: {output_fuf_path}\n"
            f"Informe HTML: {output_html}"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: update_and_forecast — añade observaciones y actualiza previsiones
# ---------------------------------------------------------------------------

@mcp.tool()
def update_and_forecast(fuf_path: str,
                        new_values: list,
                        output_html: str,
                        output_fuf_path: str = "",
                        actual_dates: list = []) -> list:
    """
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
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        import numpy as np
        from fue.report_forecast import write_forecast_report

        fuf_path = _fuf_path(os.path.expanduser(fuf_path))
        ts_old, m_old = _fue.load_fuf(fuf_path)
        L_old = m_old._fuf_horizon
        sig2  = m_old._fuf_sigma2

        fr_old  = m_old.forecast_fuf()
        n_new   = len(new_values)
        new_arr = np.array(new_values, dtype=float)

        # Tracking: actual vs previous forecast
        track_lines = []
        for i, actual in enumerate(new_arr):
            if i < len(fr_old.level):
                prev    = fr_old.level[i]
                err_pct = 100.0 * (actual - prev) / prev if prev != 0 else float("nan")
                date_lbl = (actual_dates[i] if actual_dates and i < len(actual_dates)
                            else _forecast_date(ts_old.start, ts_old.nobs + 1,
                                                ts_old.freq, i))
                track_lines.append(
                    f"  {date_lbl}: obs={actual:.4f}  prev={prev:.4f}  "
                    f"err={err_pct:+.2f}%"
                )

        # Build updated series and model (same spec, fixed params)
        new_data = list(ts_old.data) + list(new_arr)
        ts_new   = _fue.TimeSeries(new_data, freq=ts_old.freq,
                                   start=ts_old.start, name=ts_old.name)
        m_new = _fue.Model(
            ts_new,
            ar=m_old.ar, ar_free=m_old.ar_free,
            ma=m_old.ma, ma_free=m_old.ma_free,
            ar_s=m_old.ar_s, ar_s_free=m_old.ar_s_free,
            ma_s=m_old.ma_s, ma_s_free=m_old.ma_s_free,
            ar_f=m_old.ar_f, ma_f=m_old.ma_f,
            d=m_old.d, D=m_old.D, ifadf=m_old.ifadf,
            interventions=m_old.interventions,
            mu=m_old.mu0, estimate_mu=m_old.estimate_mu,
            boxlam=m_old.boxlam,
        )
        fr_new = m_new.forecast_fuf(horizon=L_old, sigma2=sig2)

        out_path = _fuf_path(os.path.expanduser(output_fuf_path or fuf_path))
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        m_new.write_fuf(horizon=L_old, sigma2=sig2, path=out_path)

        output_html = os.path.expanduser(output_html)
        os.makedirs(os.path.dirname(os.path.abspath(output_html)), exist_ok=True)
        write_forecast_report(m_new, fr_new, path=output_html,
                              title=ts_new.name or "", source=fuf_path,
                              sps_name=os.path.basename(fuf_path))

        end_date = _forecast_date(ts_new.start, ts_new.nobs + 1, ts_new.freq, L_old - 1)

        track_block = ""
        if track_lines:
            track_block = "\nSeguimiento (actual vs. previsión anterior):\n" + "\n".join(track_lines) + "\n"

        text = (
            f"## Previsiones actualizadas — {ts_new.name or 'Serie'} "
            f"(+{n_new} obs → {end_date})\n"
            + track_block
            + f"\nσ̂_a = {sig2**0.5:.6f}\n"
            + f"Archivo fuf actualizado: {out_path}\n"
            + f"Informe HTML: {output_html}"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: sps_dashboard — informe de seguimiento multi-serie
# ---------------------------------------------------------------------------

@mcp.tool()
def sps_dashboard(sps_dir: str, output_dir: str) -> list:
    """
    Generate a sequential prediction (SPS) dashboard for all series in a directory.

    Scans sps_dir for fuf .inp files, generates a fue HTML forecast report
    for each series in output_dir, and writes an index.html with a summary
    table linking to the per-series reports.

    Parameters
    ----------
    sps_dir    : directory containing fuf .inp files (one per series)
    output_dir : directory to write per-series HTML reports and index.html
    """
    try:
        from mcp.types import TextContent
        import fue as _fue
        from fue.report_forecast import write_forecast_report

        sps_dir    = os.path.expanduser(sps_dir)
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        fuf_files = sorted(
            f for f in os.listdir(sps_dir)
            if f.endswith(".inp") and os.path.isfile(os.path.join(sps_dir, f))
        )
        if not fuf_files:
            return [TextContent(type="text",
                                text=f"No se encontraron archivos .inp en {sps_dir}")]

        entries = []
        for fname in fuf_files:
            fuf_p = os.path.join(sps_dir, fname)
            stem  = os.path.splitext(fname)[0]
            try:
                ts, m = _fue.load_fuf(fuf_p)
                fr    = m.forecast_fuf()

                html_p = os.path.join(output_dir, f"{stem}.html")
                write_forecast_report(m, fr, path=html_p,
                                      title=ts.name or stem,
                                      source=fuf_p,
                                      sps_name=stem)

                last = _forecast_date(ts.start, ts.nobs, ts.freq, 0)
                end  = _forecast_date(ts.start, ts.nobs + 1, ts.freq, fr.horizon - 1)
                entries.append({
                    "name": ts.name or stem,
                    "html": f"{stem}.html",
                    "last": last, "end": end,
                    "horizon": fr.horizon,
                    "level_1": fr.level[0],
                    "diff1_1": fr.diff1[0],
                    "sdiff_1": fr.seasonal_diff[0],
                    "error": None,
                })
            except Exception as exc:
                entries.append({"name": stem, "html": "", "error": str(exc)})

        # Write index.html
        idx_rows = []
        for e in entries:
            if e.get("error"):
                idx_rows.append(
                    f"<tr><td>{e['name']}</td>"
                    f"<td colspan='5' style='color:red'>{e['error']}</td></tr>"
                )
            else:
                sign1 = "+" if e["diff1_1"] >= 0 else ""
                signa = "+" if e["sdiff_1"] >= 0 else ""
                idx_rows.append(
                    f"<tr>"
                    f"<td><a href='{e['html']}'>{e['name']}</a></td>"
                    f"<td>{e['last']}</td><td>{e['end']}</td>"
                    f"<td>{e['level_1']:.4f}</td>"
                    f"<td>{sign1}{e['diff1_1']:.2f}%</td>"
                    f"<td>{signa}{e['sdiff_1']:.2f}%</td>"
                    f"</tr>"
                )
        index_html = (
            "<!DOCTYPE html><html lang='es'><meta charset='utf-8'>"
            "<title>SPS Index</title>"
            "<body style='font-family:sans-serif;max-width:900px;margin:40px auto'>"
            "<h1>SPS — Panel de seguimiento</h1>"
            "<table border='1' cellpadding='6' cellspacing='0' width='100%'>"
            "<tr><th>Serie</th><th>Último dato</th><th>Fin horizonte</th>"
            "<th>Prev₁</th><th>Δ período</th><th>Δ anual</th></tr>"
            + "".join(idx_rows)
            + "</table></body></html>"
        )
        with open(os.path.join(output_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(index_html)

        n_ok = sum(1 for e in entries if not e.get("error"))
        lines = [
            f"### SPS Dashboard — {n_ok}/{len(entries)} series",
            f"Directorio: {output_dir}",
            "",
        ]
        for e in entries:
            if not e.get("error"):
                lines.append(
                    f"- {e['name']}: {e['last']} → {e['end']}  "
                    f"prev₁={e['level_1']:.4f}  "
                    f"Δ={e['diff1_1']:+.2f}%  ΔA={e['sdiff_1']:+.2f}%"
                )
            else:
                lines.append(f"- {e['name']}: ERROR — {e['error']}")

        return [TextContent(type="text", text="\n".join(lines))]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tools: data ingestion (Excel / CSV → .inp)
# ---------------------------------------------------------------------------

@mcp.tool()
def preview_data(source_path: str, sheet: str = "") -> list:
    """
    Preview the contents of an Excel or CSV file before loading.

    Lists available sheets (Excel), column names, number of rows, detected
    date range and frequency. Use this before load_data to choose the right
    column and confirm that dates are parsed correctly.

    Parameters
    ----------
    source_path : path to .xlsx, .xls, or .csv file
    sheet       : sheet name (Excel only; default = first sheet)
    """
    try:
        import pandas as pd
        from mcp.types import TextContent

        source_path = os.path.expanduser(source_path)
        ext = os.path.splitext(source_path)[1].lower()

        # ── Load ──────────────────────────────────────────────────────────────
        if ext in (".xlsx", ".xls", ".ods"):
            xl = pd.ExcelFile(source_path)
            sheet_names = xl.sheet_names
            sname = sheet if sheet in sheet_names else sheet_names[0]
            df = xl.parse(sname, index_col=0, parse_dates=True)
        elif ext == ".csv":
            sheet_names = ["(CSV — sin hojas)"]
            sname = sheet_names[0]
            df = pd.read_csv(source_path, index_col=0, parse_dates=True)
        else:
            return _err(f"Formato no soportado: {ext}. Usa .xlsx, .xls, .ods o .csv")

        # ── Date detection ────────────────────────────────────────────────────
        idx = df.index
        if isinstance(idx, (pd.DatetimeIndex, pd.PeriodIndex)):
            date_ok = True
            d0 = idx[0]
            d1 = idx[-1]
            # Infer freq
            if hasattr(idx, "freqstr") and idx.freqstr:
                fs = idx.freqstr.upper()
                if fs.startswith(("A", "Y")):  freq_detected = 1
                elif fs.startswith("Q"):        freq_detected = 4
                elif fs.startswith("M"):        freq_detected = 12
                else:                           freq_detected = None
            else:
                # Guess from gap between first two obs
                freq_detected = None
                gap = None
                if len(idx) >= 2:
                    try:
                        gap = (idx[1] - idx[0]).days
                        if gap >= 340:  freq_detected = 1
                        elif gap >= 85: freq_detected = 4
                        elif gap >= 25: freq_detected = 12
                    except Exception:
                        pass
            freq_str = {1: "anual", 4: "trimestral", 12: "mensual"}.get(
                freq_detected, f"desconocida (gap≈{gap if gap is not None else '?'} días)"
            )
            date_info = (
                f"Índice de fechas detectado ✓\n"
                f"  Inicio : {d0}\n"
                f"  Fin    : {d1}\n"
                f"  Frecuencia inferida: {freq_str}"
                + (f" (freq={freq_detected})" if freq_detected else "")
            )
        else:
            date_ok = False
            date_info = (
                "⚠ El índice no contiene fechas reconocibles.\n"
                "  → En load_data deberás indicar freq, start_year y start_period."
            )

        # ── Column summary ────────────────────────────────────────────────────
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        col_lines = []
        for c in numeric_cols:
            s = df[c].dropna()
            col_lines.append(
                f"  {str(c):<30}  n={len(s)}  "
                f"rango=[{s.min():.4g}, {s.max():.4g}]"
                + ("  ⚠ tiene NaN" if df[c].isna().any() else "")
            )

        sheets_info = (
            f"Hojas disponibles: {', '.join(sheet_names)}\n"
            f"Hoja activa: «{sname}»\n"
        ) if ext != ".csv" else ""

        text = (
            f"## Preview: {os.path.basename(source_path)}\n\n"
            + sheets_info
            + f"Filas: {len(df)}   Columnas numéricas: {len(numeric_cols)}\n\n"
            + date_info + "\n\n"
            "**Columnas disponibles:**\n"
            + "\n".join(col_lines)
            + "\n\n---\n"
            "**Próximo paso:** `load_data(source_path, output_inp, column=\"<nombre>\", ...)`"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


@mcp.tool()
def load_data(
    source_path: str,
    output_inp: str,
    column: str,
    series_name: str = "",
    sheet: str = "",
    freq: int = 0,
    start_year: int = 0,
    start_period: int = 1,
) -> list:
    """
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
    """
    try:
        import pandas as pd
        import fue
        from mcp.types import TextContent

        source_path = os.path.expanduser(source_path)
        output_inp  = os.path.expanduser(output_inp)
        if not output_inp.endswith(".inp") and not output_inp.endswith(".pre"):
            output_inp += ".inp"

        ext = os.path.splitext(source_path)[1].lower()

        # ── Load dataframe ────────────────────────────────────────────────────
        if ext in (".xlsx", ".xls", ".ods"):
            xl = pd.ExcelFile(source_path)
            sname = sheet if sheet in xl.sheet_names else xl.sheet_names[0]
            df = xl.parse(sname, index_col=0, parse_dates=True)
        elif ext == ".csv":
            sname = "(CSV)"
            df = pd.read_csv(source_path, index_col=0, parse_dates=True)
        else:
            return _err(f"Formato no soportado: {ext}")

        # ── Select column ─────────────────────────────────────────────────────
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if column.isdigit():
            idx_col = int(column)
            if idx_col >= len(numeric_cols):
                return _err(f"Índice de columna {idx_col} fuera de rango "
                            f"(hay {len(numeric_cols)} columnas numéricas)")
            col_name = numeric_cols[idx_col]
        elif column in df.columns:
            col_name = column
        else:
            return _err(
                f"Columna «{column}» no encontrada.\n"
                f"Columnas disponibles: {', '.join(str(c) for c in numeric_cols)}"
            )

        series = df[col_name].dropna()
        name   = series_name or str(col_name)

        # ── Build TimeSeries ──────────────────────────────────────────────────
        idx = series.index
        has_dates = isinstance(idx, (pd.DatetimeIndex, pd.PeriodIndex))

        if has_dates:
            ts = fue.TimeSeries.from_pandas(series.rename(name),
                                            freq=freq if freq > 0 else None)
            if freq > 0:
                ts = fue.TimeSeries(ts.data, freq=freq,
                                    start=ts.start, name=name)
            date_note = f"Fechas inferidas del índice."
        else:
            if freq <= 0 or start_year <= 0:
                return _err(
                    "El índice no contiene fechas. Proporciona:\n"
                    "  freq (1/4/12), start_year, start_period"
                )
            ts = fue.TimeSeries(
                series.to_numpy(dtype=float),
                freq=freq, start=(start_year, start_period), name=name
            )
            date_note = f"Fechas asignadas manualmente: inicio {start_year}/{start_period}, freq={freq}."

        # ── Write .inp ────────────────────────────────────────────────────────
        _write_bare_inp(ts, output_inp)

        freq_label = {1: "anual", 4: "trimestral", 12: "mensual"}.get(ts.freq, str(ts.freq))
        begyear, begtime = ts.start
        endtotal = (begtime - 1) + ts.nobs - 1
        if ts.freq == 12:
            end_str = f"{endtotal % 12 + 1:02d}/{begyear + endtotal // 12}"
            start_str = f"{begtime:02d}/{begyear}"
        elif ts.freq == 4:
            end_str = f"Q{endtotal % 4 + 1}/{begyear + endtotal // 4}"
            start_str = f"Q{begtime}/{begyear}"
        else:
            end_str = str(begyear + ts.nobs - 1)
            start_str = str(begyear)

        text = (
            f"## Serie cargada: {name}\n\n"
            f"Fuente : {os.path.basename(source_path)}"
            + (f"  (hoja: {sname})" if ext != ".csv" else "") + "\n"
            f"Columna: {col_name}\n"
            f"Período: {start_str} → {end_str}  "
            f"(n={ts.nobs}, {freq_label})\n"
            f"{date_note}\n\n"
            f"Archivo .inp: `{output_inp}`\n\n"
            "---\n"
            "**Próximo paso:**\n"
            f"```\nguided_identification(inp_path=\"{output_inp}\")\n```"
        )
        return [TextContent(type="text", text=text)]

    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Tool: fue .out ASCII report
# ---------------------------------------------------------------------------

@mcp.tool()
def get_out_report(inp_path: str) -> list:
    """
    Return the full fue .out ASCII report for an estimated model.

    Produces the same output as the C 'fue' binary: parameter estimates with
    standard errors, AR/MA polynomials, sigma, log-likelihood, AIC/BIC,
    correlation matrix, residual statistics, outlier table, and ACF of residuals.

    Useful for detailed review of the estimated model beyond what the diagnosis
    summary shows.

    Parameters
    ----------
    inp_path : path to the .inp or .pre file with the model specification
    """
    try:
        from mcp.types import TextContent
        ts, m = _load_ts_model(inp_path)
        m.fit()
        out_text = m.write_out()
        return [TextContent(type="text", text=f"```\n{out_text}\n```")]
    except Exception:
        return _err(traceback.format_exc())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
