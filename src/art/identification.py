"""
Identification listing for time series — Python reimplementation of fug usid mode.

Workflow:
  1. plot_boxcox_selection(ts)  — choose lambda: shows original vs log with m-dt scatter
  2. identification_listing(ts, lam=chosen)  — choose d/D: series + ACF/PACF per transformation

All computation is pure Python/NumPy; plots use matplotlib.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fue import TimeSeries
from fue.diagnostics import acf as _fue_acf, pacf as _fue_pacf, ljung_box as _fue_ljung_box
from .seasonal_detection import detect_seasonality, plot_seasonality


# ---------------------------------------------------------------------------
# Box-Cox transform (mirrors fug BoxCox with geometric=False, shift=0)
# ---------------------------------------------------------------------------

def desfase_observaciones(model) -> int:
    """Cuántas observaciones consume la diferenciación — BUG-0172.

    Los residuos de un modelo diferenciado empiezan N observaciones después de
    la serie, y **hay que contarlas todas**:

        d          · cada diferencia regular consume 1
        D · s      · cada diferencia estacional consume s
        ifadf[f]   · cada RAÍZ ESTACIONAL ESTOCÁSTICA consume el grado de su
                     factor: 2 en una frecuencia interior
                     (1 − 2cos(ω)B + B²), 1 en el Nyquist (1 + B)

    **El tercer sumando faltaba en los CINCO sitios que hacían esta cuenta**, y
    cada uno la escribía a mano como `d + D·s`:

        configuracion.py   las configuraciones candidatas del incidente
        escalera.py        el arranque de los peldaños
        interventions.py   la regla de Treadway
        mcp_server.py ×2   la fecha de un episodio y DÓNDE se coloca la
                           intervención que el analista pide

    Los dos últimos son los graves: no desplazan una etiqueta, desplazan **el
    modelo**. Medido sobre `ES_CPI_B_m11` —dos frecuencias reformuladas, consumo
    4— una intervención pedida para 03/2022 se colocaba en 07/2022, y Treadway
    leía el residuo de 07/2022 para juzgarla. Publicaba «2 de 4 pasan» donde las
    cuatro pasaban.

    Comprobado contra el recuento real de residuos en cuatro modelos del run 3:

        B_m11  n=293  nres=288  d=1  ifadf=[2,3]  consumo 4  ✓
        B_m08  n=293  nres=290  d=1  ifadf=[2]    consumo 2  ✓
        A_m06  n=216  nres=213  d=1  ifadf=[3]    consumo 2  ✓
        B_m01  n=293  nres=292  d=1  ifadf=[]     consumo 0  ✓

    Vivía aquí, en un solo sitio, porque escrita en cinco es una costumbre:
    basta que alguien añada un operador nuevo para que vuelva a divergir.
    Desde BUG-0023 de fue vive en fue, que es el dueño del modelo
    (`fue.diagnostics.differencing_offset`): también la necesita la figura de
    residuos de fue. Aquí queda el nombre, para los que ya la llaman.
    """
    from fue.diagnostics import differencing_offset
    return differencing_offset(model)


def _default_lags_fug(n: int, freq: int) -> int:
    """Default ACF/PACF lags — fug C's rule, which lives in fue (BUG-0023)."""
    from fue.diagnostics import default_lags
    return default_lags(n, freq)


def boxcox_transform(y: np.ndarray, lam: float, shift: float = 0.0) -> np.ndarray:
    """Apply Box-Cox transform: lam=0 → log, lam=1 → identity."""
    z = y + shift
    if lam == 0.0:
        return np.log(z)
    elif lam == 1.0:
        return z.copy()
    else:
        return (z ** lam - 1.0) / lam


def boxcox_label(lam: float) -> str:
    if lam == 0.0:
        return "ln"
    elif lam == 1.0:
        return ""
    else:
        return f"λ={lam:.1f}"


# ---------------------------------------------------------------------------
# Differencing (mirrors fug DelOp / DiffGraph differencing logic)
# ---------------------------------------------------------------------------

def _seasonal_poly(freq: int) -> np.ndarray:
    """Coefficients of (1 + B + B^2 + ... + B^{freq-1}), i.e. ∇_freq = 1 - B^freq
    expressed as the full seasonal polynomial filter [1, 1, 1, ..., 1] (length freq).
    Actually we want the operator (1 - B^s), whose polynomial is [1, 0, ..., 0, -1]."""
    poly = np.zeros(freq + 1)
    poly[0] = 1.0
    poly[freq] = -1.0
    return poly


def apply_differences(z: np.ndarray, freq: int,
                      nrdiff: int, nadiff: int) -> np.ndarray:
    """
    Apply nrdiff regular differences (1-B)^nrdiff and nadiff seasonal
    differences (1-B^freq)^nadiff to z.  Returns the differenced series
    (shorter by nrdiff + freq*nadiff observations).
    """
    w = z.copy()
    for _ in range(nrdiff):
        w = np.diff(w)
    for _ in range(nadiff):
        w = w[freq:] - w[:-freq]
    return w


_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def transform_label(lam: float, nrdiff: int, nadiff: int, freq: int,
                    name: str = "") -> str:
    """Human-readable label for the transformed series, e.g. '∇²∇₁₂ ln IPC_ES'.

    *name* is the series name (the variable being transformed); when given it is
    appended so titles read e.g. '∇ ln IPC_ES' instead of a generic '∇ ln'.
    """
    bc = boxcox_label(lam)
    diff = ""
    if nrdiff == 1:
        diff = "∇"
    elif nrdiff > 1:
        diff = f"∇{str(nrdiff).translate(_SUP)}"
    sdiff = ""
    if nadiff == 1:
        sdiff = f"∇{str(freq).translate(_SUB)}"
    elif nadiff > 1:
        sdiff = f"∇{str(freq).translate(_SUB)}{str(nadiff).translate(_SUP)}"
    op = f"{diff}{sdiff}{bc}"
    if name:
        sep = " " if op else ""
        return f"{op}{sep}{name}"
    return op


# ---------------------------------------------------------------------------
# Sample statistics
# ---------------------------------------------------------------------------

@dataclass
class SeriesStats:
    n: int
    mean: float
    se_mean: float
    variance: float
    std: float
    skewness: float
    kurtosis: float       # excess kurtosis
    jarque_bera: float
    ljung_box_stat: float
    ljung_box_df: int
    acf: np.ndarray       # length = lags
    pacf: np.ndarray      # length = lags
    lags: int


def compute_stats(w: np.ndarray, lags: int | None = None,
                  npar: int = 0) -> SeriesStats:
    """Estadísticos de una serie o de unos residuos.

    `npar` son los parámetros ARMA libres del modelo del que salen los
    residuos. BUG-0074: sin él, la etiqueta del gráfico imprimía el número de
    RETARDOS donde van los GRADOS DE LIBERTAD. Sobre residuos de un modelo
    estimado los grados de libertad de un Ljung-Box son `retardos − npar`, y el
    `.out` del motor ya lo reportaba bien — la discrepancia entre las dos
    salidas era la señal. Con `npar=0` (una serie cruda, sin modelo) las dos
    cantidades coinciden y no hay nada que restar.
    """
    n = len(w)
    if lags is None:
        lags = min(3 * 13, n - 1)  # default, overridden per-panel

    mu = float(np.mean(w))
    var = float(np.var(w))
    std = math.sqrt(var)
    se_mean = std / math.sqrt(n)

    # skewness and excess kurtosis (population moments, matching fug)
    skew = float(np.mean(((w - mu) / std) ** 3)) if std > 1e-20 else 0.0
    kurt = float(np.mean(((w - mu) / std) ** 4)) - 3.0 if std > 1e-20 else 0.0
    jb = n / 6.0 * (skew ** 2 + kurt ** 2 / 4.0)

    r  = _fue_acf(w, lags=lags)
    p  = _fue_pacf(w, lags=lags)
    lb = _fue_ljung_box(w, lags=lags)

    return SeriesStats(
        n=n, mean=mu, se_mean=se_mean, variance=var, std=std,
        skewness=skew, kurtosis=kurt, jarque_bera=jb,
        ljung_box_stat=float(lb["statistic"][-1]),
        ljung_box_df=max(int(lb["lags"][-1]) - int(npar), 1),
        acf=r, pacf=p, lags=lags,
    )


# ---------------------------------------------------------------------------
# Mean–standard deviation plot (fug graph_m_dt / DesvMed algorithm)
# ---------------------------------------------------------------------------

@dataclass
class MeanStdData:
    means_std: np.ndarray     # standardised group means  (x-axis)
    stds_std: np.ndarray      # standardised group stdevs (y-axis)
    nog: int                  # observations per group
    ng: int                   # number of groups


def mean_stdev_data(z: np.ndarray, nog: int) -> MeanStdData:
    """
    Compute standardised (mean, std) scatter for Box-Cox adequacy.

    Divide z into ng = n//nog non-overlapping groups.  Compute mean and
    std of each group, then standardise both vectors.  A horizontal cloud
    (stds_std ≈ 0 across means) indicates variance-stabilising transform.
    """
    n = len(z)
    ng = n // nog
    groups = z[: ng * nog].reshape(ng, nog)

    m = groups.mean(axis=1)
    s = groups.std(axis=1, ddof=0)

    def standardise(v):
        mu, sigma = v.mean(), v.std(ddof=0)
        return (v - mu) / sigma if sigma > 1e-20 else v - mu

    return MeanStdData(
        means_std=standardise(m),
        stds_std=standardise(s),
        nog=nog,
        ng=ng,
    )


# ---------------------------------------------------------------------------
# Single identification panel (one d, D combination)
# ---------------------------------------------------------------------------

@dataclass
class Panel:
    label: str           # e.g. "∇²ln"
    nrdiff: int
    nadiff: int
    w: np.ndarray        # transformed + differenced series
    stats: SeriesStats


def build_panel(z: np.ndarray, freq: int,
                nrdiff: int, nadiff: int,
                lam: float, lags: int) -> Panel:
    w = apply_differences(z, freq, nrdiff, nadiff)
    stats = compute_stats(w, lags=lags)
    label = transform_label(lam, nrdiff, nadiff, freq)
    return Panel(label=label, nrdiff=nrdiff, nadiff=nadiff, w=w, stats=stats)


# ---------------------------------------------------------------------------
# Full identification listing
# ---------------------------------------------------------------------------

@dataclass
class IdentificationListing:
    name: str
    freq: int
    lam: float
    nog: int
    panels: list[Panel]
    mdt: MeanStdData      # computed on z = boxcox(y), no differencing


# ---------------------------------------------------------------------------
# Unit root tests — Bloque L
#
# ADF and KPSS are SPECIFICATION TOOLS for choosing initial d.
# They are exploratory aids (like visual inspection of ACF/residuals),
# not formal hypothesis tests on an estimated model.
#
# The formal test for d in an estimated ARMAX model is Shin-Fuller (1998);
# see formal_tests.shin_fuller(), which applies after estimation and diagnosis.
# ---------------------------------------------------------------------------

@dataclass
class UnitRootResult:
    """ADF + KPSS result for one differencing level (initial d specification)."""
    d: int
    label: str           # e.g. "∇ln P"
    n: int               # length of differenced series
    adf_stat: float
    adf_pvalue: float
    adf_rejects: bool    # True → stationary (H₀ unit root rejected at 5%)
    kpss_stat: float
    kpss_pvalue: float
    kpss_rejects: bool   # True → non-stationary (H₀ stationarity rejected at 5%)
    verdict: str         # "stationary" | "unit_root" | "ambiguous"


def unit_root_tests(ts: "TimeSeries",
                    lam: float = 0.0,
                    max_d: int = 2) -> list[UnitRootResult]:
    """
    Initial d specification via ADF + KPSS for d = 0, 1, …, max_d.

    This is an exploratory tool for choosing the starting value of d before
    estimation — not a formal hypothesis test.  The formal test for d on an
    estimated model is Shin-Fuller (1998); see formal_tests.shin_fuller().

    For each d, applies d regular differences to boxcox(y) and runs:
      - ADF (H₀: unit root, autolag='AIC');  reject → evidence of stationarity
      - KPSS (H₀: stationary, nlags='auto'); reject → evidence of non-stationarity

    Verdict by consensus:
      'stationary'  — ADF rejects AND KPSS does not reject
      'unit_root'   — ADF does not reject AND KPSS rejects
      'ambiguous'   — tests disagree or both fail to reject

    Parameters
    ----------
    ts    : fue.TimeSeries (provides ts.data and ts.freq)
    lam   : Box-Cox lambda (0.0 = log)
    max_d : highest differencing order to test (default 2)

    Returns
    -------
    list[UnitRootResult], one entry per d from 0 to max_d
    (may be shorter if the differenced series becomes too short)
    """
    import warnings
    from ._raiz_unitaria import adf as _adf, kpss as _kpss

    y = np.asarray(ts.data, dtype=float)
    z = boxcox_transform(y, lam)
    freq = ts.freq

    results = []
    for d in range(max_d + 1):
        w = apply_differences(z, freq, d, 0)
        if len(w) < 10:
            break
        lbl = transform_label(lam, d, 0, freq)

        adf_stat, adf_p, *_ = _adf(w)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            kpss_stat, kpss_p, *_ = _kpss(w)

        adf_rejects  = adf_p   < 0.05
        kpss_rejects = kpss_p  < 0.05

        if adf_rejects and not kpss_rejects:
            verdict = "stationary"
        elif not adf_rejects and kpss_rejects:
            verdict = "unit_root"
        else:
            verdict = "ambiguous"

        results.append(UnitRootResult(
            d=d, label=lbl, n=len(w),
            adf_stat=adf_stat, adf_pvalue=adf_p, adf_rejects=adf_rejects,
            kpss_stat=kpss_stat, kpss_pvalue=kpss_p, kpss_rejects=kpss_rejects,
            verdict=verdict,
        ))

    return results


def recommended_d(results: list[UnitRootResult]) -> int:
    """Smallest d for which the unit-root evidence stops requiring a difference.

    ADF directly tests the unit root, so its **rejection** is decisive evidence
    that a (further) difference is *not* needed.  We therefore pick the smallest d
    at which ADF rejects, **regardless of KPSS**: a KPSS rejection on its own only
    reflects low-frequency persistence in a bounded / mean-reverting series (common
    in climate counts and quantities), and letting it escalate d over a clear ADF
    rejection over-differences and injects a spurious MA unit root (BUG-0002).

    Order of decision:
      1. smallest d with ``adf_rejects``  (ADF beats KPSS — no over-differencing);
      2. else smallest d with the strict consensus verdict ``'stationary'``;
      3. else the last d tested (nothing conclusive — e.g. a genuine unit root
         where ADF never rejects within max_d).

    This never recommends d≥1 while ADF is significant at a lower d, and only
    reaches d=2 when ADF fails to reject at both d=0 and d=1.  The choice is a
    starting value; the formal test on the estimated model is Shin-Fuller.

    **"Only when ADF fails at d=0 and d=1" is NOT a safeguard** (BUG-0023).
    Failing to reject at both is exactly what a strongly seasonal series does:
    the ADF regression carries no seasonal terms, so the pattern lands in its
    residual variance and biases the test towards "difference again".  This
    function is the EVIDENCE layer and deliberately keeps reporting what the
    tests say — the cap belongs ABOVE it, and there are two:

      · autonomous lane : ``policy.decide_d`` (max_step=1, plus the seasonal cap)
      · guided lane     : the caller passes ``max_d=current_d + 1``, so a node
                          evaluating from d=0 never tabulates d=2 at all

    Do not move either cap in here; ``tests/test_bug_0015_0016_policy_domain_and_d_cap``
    fixes that boundary on purpose.
    """
    if not results:
        return 0
    for r in results:                       # 1) ADF rejection governs
        if r.adf_rejects:
            return r.d
    for r in results:                       # 2) strict consensus fallback
        if r.verdict == "stationary":
            return r.d
    return results[-1].d                     # 3) nothing conclusive


# ---------------------------------------------------------------------------
# Plotting — the figures are drawn by pyfug (_listing_figures, plot_boxcox_selection)
# ---------------------------------------------------------------------------









# ---------------------------------------------------------------------------
# Box-Cox selection (step 0: choose lambda before identification)
# ---------------------------------------------------------------------------

@dataclass
class BoxCoxSelection:
    name: str
    freq: int
    nog: int
    y_raw: np.ndarray    # original series (λ=1)
    y_log: np.ndarray    # log series (λ=0)
    mdt_raw: MeanStdData
    mdt_log: MeanStdData


def boxcox_selection(ts: TimeSeries, nog: int | None = None) -> BoxCoxSelection:
    """Compute data for Box-Cox selection: original vs log with mean-std scatters."""
    freq  = ts.freq
    y     = np.asarray(ts.data, dtype=float)
    name  = getattr(ts, 'name', 'series')
    if nog is None:
        nog = freq if freq > 1 else 8
    y_raw = y.copy()
    y_log = np.log(y)
    return BoxCoxSelection(
        name=name, freq=freq, nog=nog,
        y_raw=y_raw, y_log=y_log,
        mdt_raw=mean_stdev_data(y_raw, nog),
        mdt_log=mean_stdev_data(y_log, nog),
    )


def plot_boxcox_selection(ts: TimeSeries, nog: int | None = None) -> plt.Figure:
    """The m-dt figure for choosing λ: level (λ=1) beside log (λ=0).

    Drawn by pyfug (`plot_mean_deviation_pair`), the one Jenkins-Treadway
    graphics engine. art used to draw its own version here, with a series
    panel whose year axis followed none of fug's rules.
    """
    from pyfug.core import Tseries as _Tseries
    from pyfug.graphics import plot_mean_deviation_pair
    bcs = boxcox_selection(ts, nog)
    start = getattr(ts, 'start', (1, 1))
    pf = _Tseries(name=bcs.name or "", freq=ts.freq, nobs=len(ts.data),
                  begyear=int(start[0]), begtime=int(start[1]),
                  data=np.asarray(ts.data, dtype=float))
    return plot_mean_deviation_pair(pf, nog=bcs.nog, name=bcs.name or "")


def save_boxcox_selection(ts: TimeSeries, path: str, nog: int | None = None) -> None:
    """Save the Box-Cox selection figure as a self-contained HTML file."""
    import base64, io
    fig = plot_boxcox_selection(ts, nog)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    name = getattr(ts, 'name', 'series')
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<title>Box-Cox selection — {name}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}}h1{{font-size:15px}}</style>
</head>
<body>
<h1>Box-Cox selection: {name}</h1>
<p>Positive slope in the mean–std scatter → variance depends on level → use log.</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%">
</body></html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)


def _listing_figures(listing: IdentificationListing,
                     panels: list[Panel],
                     start: tuple = (1, 1)) -> list[plt.Figure]:
    """One figure per panel of the listing: the transformed and differenced
    series with its acf/pacf, drawn by pyfug's `plot_combined` — the same
    figure as fug -c and the guided lane.

    The series keeps the ORIGINAL start and the observations lost to
    differencing go in `timeout`, so the year axis starts where fug C starts
    it (BUG-0006 of pyfug). It used to be one tall figure drawn here, with its
    own geometry and year axis.
    """
    from pyfug.core import Tseries as _Tseries
    from pyfug.graphics import plot_combined
    figs = []
    for p in panels:
        lost = int(p.nrdiff) + int(p.nadiff) * int(listing.freq)
        name = transform_label(listing.lam, p.nrdiff, p.nadiff, listing.freq,
                               name=listing.name or "")
        pf = _Tseries(name=name, freq=listing.freq, nobs=len(p.w),
                      begyear=int(start[0]), begtime=int(start[1]),
                      data=np.asarray(p.w, dtype=float))
        figs.append(plot_combined(pf, timeout=lost, tsnobs=len(p.w) + lost,
                                  nlags=int(p.stats.lags), title=name,
                                  percent=(float(listing.lam) == 0.0
                                           and lost > 0)))   # BUG-0219
    return figs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def identification_listing(
    ts: TimeSeries,
    lam: float = 0.0,
    shift: float = 0.0,
    max_d: int = 2,
    max_D: int = 1,
    lags: int | None = None,
    nog: int | None = None,
    output_path: str | None = None,
) -> IdentificationListing:
    """
    Build a complete identification listing for *ts*.

    Parameters
    ----------
    ts          : fue.TimeSeries
    lam         : Box-Cox lambda (0.0 = log, 1.0 = none)
    shift       : additive shift before Box-Cox (boxm in fug)
    max_d       : maximum regular differencing order (default 2)
    max_D       : maximum seasonal differencing order (default 1)
    lags        : ACF/PACF lags; defaults to min(3*freq+3, n//4)
    nog         : observations per group for mean-std plot;
                  defaults to freq (12 for monthly)
    output_path : if given, save the HTML listing to this path

    Returns
    -------
    IdentificationListing  (panels + mdt data)
    """
    freq  = ts.freq
    y     = np.asarray(ts.data, dtype=float)
    name  = getattr(ts, "name", "series")
    start = getattr(ts, "start", (1, 1))

    z = boxcox_transform(y, lam, shift)

    if lags is None:
        lags = _default_lags_fug(len(y), freq)
    if nog is None:
        nog = freq if freq > 1 else 8

    panels = []
    if freq == 1:
        for d in range(max_d + 1):
            panels.append(build_panel(z, freq, d, 0, lam, lags))
    else:
        for D in range(max_D + 1):
            for d in range(max_d + 1):
                panels.append(build_panel(z, freq, d, D, lam, lags))

    mdt = mean_stdev_data(z, nog)

    listing = IdentificationListing(
        name=name, freq=freq, lam=lam, nog=nog,
        panels=panels, mdt=mdt,
    )

    if output_path is not None:
        save_listing(listing, output_path, start=start)

    return listing


def save_listing(listing: IdentificationListing, path: str,
                 start: tuple = (1, 1)) -> None:
    """Save identification listing as a multi-page HTML with embedded PNGs."""
    import base64
    import io

    def fig_to_b64(fig: plt.Figure) -> str:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    panels = listing.panels

    # Page 1: first 6 panels (d=0,1,2 × D=0,1 for monthly)
    # Page 2: mean-std plot
    # All panels in one tall figure (one row per transform)
    chunks = [panels[i:i+6] for i in range(0, len(panels), 6)]
    pages_b64 = []
    for chunk in chunks:
        for fig in _listing_figures(listing, chunk, start=start):
            pages_b64.append(fig_to_b64(fig))

    mdt_b64 = None  # m-dt belongs to the Box-Cox selection step, not here

    # Statistics table (text)
    rows = []
    for p in listing.panels:
        st = p.stats
        rows.append(
            f"<tr><td>{p.label}</td>"
            f"<td>{st.n}</td>"
            f"<td>{st.mean:.6f}</td>"
            f"<td>{st.std:.6f}</td>"
            f"<td>{st.skewness:.3f}</td>"
            f"<td>{st.kurtosis:.3f}</td>"
            f"<td>{st.jarque_bera:.2f}</td>"
            f"<td>{st.ljung_box_stat:.2f} ({st.ljung_box_df})</td></tr>"
        )

    table_html = """
    <table border='1' cellpadding='4' cellspacing='0' style='font-size:12px;border-collapse:collapse'>
      <tr style='background:#ddd'>
        <th>Transform</th><th>n</th><th>Mean</th><th>Std</th>
        <th>Skew</th><th>Excess Kurt</th><th>JB</th><th>Q(df)</th>
      </tr>
    """ + "\n".join(rows) + "\n</table>"

    imgs_html = "\n".join(
        f'<img src="data:image/png;base64,{b64}" style="max-width:100%;margin-bottom:20px"><br>'
        for b64 in pages_b64
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Identification Listing — {listing.name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1   {{ font-size: 16px; }}
    h2   {{ font-size: 13px; margin-top: 30px; }}
  </style>
</head>
<body>
<h1>Identification Listing: {listing.name}
    &nbsp; &nbsp; freq={listing.freq}
    &nbsp; Box-Cox λ={listing.lam}
    &nbsp; nog={listing.nog}</h1>

<h2>Series, ACF and PACF for each transformation</h2>
{imgs_html}

<h2>Statistics table</h2>
{table_html}
</body>
</html>
"""

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)


def save_identification_report(
    ts: TimeSeries,
    path: str,
    lam: float = 0.0,
    shift: float = 0.0,
    max_d: int = 2,
    lags: int | None = None,
    nog: int | None = None,
    seasonal_d: int = 1,
    significance: float = 0.05,
) -> IdentificationListing:
    """
    Generate a complete identification HTML report.

    The listing section adapts to the seasonal detection result:

      No seasonality (freq=1 or not detected)
        Decision A: d = 0, 1, 2  [3 panels, D=0]

      Seasonality detected
        Decision B1: d = 0, 1, 2  +  deterministic harmonics  [D=0, 3 panels]
        Decision B2: d = 0, 1, 2  +  stochastic seasonality    [D=1, 3 panels]

    Sections:
      1. Box-Cox selection
      2. Seasonal detection  [only if freq > 1]
      3. Identification listing  (A or B1 + B2)
      4. Statistics table

    Returns the IdentificationListing (always generated with the full D=0 + D=1
    panels when seasonal, D=0 only otherwise).
    """
    import base64, io

    def fig_to_b64(fig: plt.Figure) -> str:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode()

    start = getattr(ts, "start", (1, 1))
    name  = getattr(ts, "name", "series")
    freq  = ts.freq
    lam_str = "100·log" if lam == 0.0 else f"λ={lam}"

    # --- 1. Box-Cox selection ---
    bcs_b64 = fig_to_b64(plot_boxcox_selection(ts, nog))

    # --- 2. Seasonal detection ---
    seasonal_section = ""
    seasonal = False
    if freq > 1:
        sd_result = detect_seasonality(ts, d=seasonal_d, lam=lam, significance=significance)
        seasonal  = sd_result.seasonal_detected
        sd_b64    = fig_to_b64(plot_seasonality(sd_result))
        status_txt = (
            '<span style="color:#c00;font-weight:bold">DETECTED</span>'
            if seasonal else
            '<span style="color:#555">not detected</span>'
        )
        if seasonal:
            decision_hint = (
                "Seasonality detected. Proceed with <strong>Decision B</strong>: "
                "choose between deterministic harmonics (B1, D=0) "
                "or stochastic seasonal differencing (B2, D=1)."
            )
        else:
            decision_hint = (
                "No seasonality detected. Proceed with <strong>Decision A</strong>: "
                "choose d = 0, 1 or 2."
            )
        seasonal_section = f"""
<h2>2 &nbsp; Seasonal detection &nbsp; [{lam_str}, d={seasonal_d}]</h2>
<p style="font-size:12px;color:#555">
  HAC F({freq - 1}, {sd_result.n_obs - freq}) = {sd_result.f_stat:.3f}
  &nbsp; p = {sd_result.p_value:.4f}
  &nbsp; → {status_txt}
  &nbsp;|&nbsp; {decision_hint}
</p>
<img src="data:image/png;base64,{sd_b64}" style="max-width:100%;margin-bottom:16px"><br>
"""
        listing_sec = 3
        table_sec   = 4
    else:
        listing_sec = 2
        table_sec   = 3

    # --- 3. Identification listing ---
    effective_max_D = 1 if seasonal else 0
    listing = identification_listing(
        ts, lam=lam, shift=shift,
        max_d=max_d, max_D=effective_max_D,
        lags=lags, nog=nog,
    )

    n_d = max_d + 1   # number of d values: 3 (d=0,1,2)

    if not seasonal:
        # Decision A: single block, 3 panels
        panels_A = listing.panels          # all D=0
        img_A = (
            "".join(f'<img src="data:image/png;base64,{fig_to_b64(fg)}"'
                    f' style="max-width:100%;margin-bottom:16px"><br>'
                    for fg in _listing_figures(listing, panels_A, start=start))
        )
        listing_html = f"""
<h2>{listing_sec} &nbsp; Identification listing &nbsp; [{lam_str}]</h2>
<p style="font-size:12px;color:#555">
  <strong>Decision A</strong> — No seasonality.  Choose d = 0, 1 or 2.
</p>
{img_A}
"""
    else:
        # Decision B: panels split by D
        panels_B1 = listing.panels[:n_d]   # D=0
        panels_B2 = listing.panels[n_d:]   # D=1
        img_B1 = (
            "".join(f'<img src="data:image/png;base64,{fig_to_b64(fg)}"'
                    f' style="max-width:100%;margin-bottom:16px"><br>'
                    for fg in _listing_figures(listing, panels_B1, start=start))
        )
        img_B2 = (
            "".join(f'<img src="data:image/png;base64,{fig_to_b64(fg)}"'
                    f' style="max-width:100%;margin-bottom:16px"><br>'
                    for fg in _listing_figures(listing, panels_B2, start=start))
        )
        listing_html = f"""
<h2>{listing_sec} &nbsp; Identification listing &nbsp; [{lam_str}]</h2>
<p style="font-size:12px;color:#555">
  <strong>Decision B</strong> — Seasonality detected.
  Choose between B1 (deterministic) and B2 (stochastic), then choose d.
</p>
<h3 style="font-size:12px;margin-top:20px;color:#333">
  B1 &nbsp; Deterministic seasonality (harmonic dummies, D=0) — choose d
</h3>
{img_B1}
<h3 style="font-size:12px;margin-top:20px;color:#333">
  B2 &nbsp; Stochastic seasonality (D=1) — choose d
</h3>
{img_B2}
"""

    # --- 4. Statistics table ---
    rows = []
    for p in listing.panels:
        st = p.stats
        rows.append(
            f"<tr><td>{p.label}</td><td>{st.n}</td>"
            f"<td>{st.mean:.6f}</td><td>{st.std:.6f}</td>"
            f"<td>{st.skewness:.3f}</td><td>{st.kurtosis:.3f}</td>"
            f"<td>{st.jarque_bera:.2f}</td>"
            f"<td>{st.ljung_box_stat:.2f} ({st.ljung_box_df})</td></tr>"
        )
    table_html = (
        "<table border='1' cellpadding='4' cellspacing='0' "
        "style='font-size:12px;border-collapse:collapse'>"
        "<tr style='background:#ddd'>"
        "<th>Transform</th><th>n</th><th>Mean</th><th>Std</th>"
        "<th>Skew</th><th>Excess Kurt</th><th>JB</th><th>Q(df)</th></tr>"
        + "".join(rows) + "</table>"
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Identification Report — {name}</title>
  <style>
    body  {{ font-family: Arial, sans-serif; margin: 30px; max-width: 1200px; }}
    h1    {{ font-size: 17px; border-bottom: 2px solid #333; padding-bottom: 6px; }}
    h2    {{ font-size: 13px; margin-top: 32px; color: #333; }}
    h3    {{ font-weight: normal; }}
    .meta {{ font-size: 12px; color: #555; margin-bottom: 20px; }}
  </style>
</head>
<body>
<h1>Identification Report: {name}</h1>
<div class="meta">
  freq={listing.freq} &nbsp;|&nbsp; λ={listing.lam} &nbsp;|&nbsp;
  nog={listing.nog} &nbsp;|&nbsp; lags={listing.panels[0].stats.lags}
</div>

<h2>1 &nbsp; Box-Cox selection</h2>
<p style="font-size:12px;color:#555">
  <strong>A priori:</strong> use log for index numbers or when the unit of
  measurement is arbitrary.
  Confirmatory: positive slope in the mean–std scatter → variance depends on
  level → log stabilises it.
</p>
<img src="data:image/png;base64,{bcs_b64}" style="max-width:100%;margin-bottom:16px"><br>

{seasonal_section}
{listing_html}
<h2>{table_sec} &nbsp; Statistics table</h2>
{table_html}
</body>
</html>
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return listing
