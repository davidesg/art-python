"""
Diagnosis of a fitted fue.Model.

Stage 3 of the Box-Jenkins-Treadway cycle: check that residuals are
white noise (Ljung-Box Q), normally distributed (Jarque-Bera), and
free of residual seasonality.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import scipy.stats as sp_stats

from fue import TimeSeries
from fue.diagnostics import (
    acf  as _fue_acf,
    pacf as _fue_pacf,
    ljung_box,
    jarque_bera,
)
from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines

from .identification import _default_lags_fug
from .seasonal_detection import detect_seasonality, SeasonalDetectionResult


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DiagnosisResult:
    # residuals
    residuals: np.ndarray          # standardized residuals (length = n - d - D*s)
    nobs: int
    npar: int                      # number of ARMA parameters (for Q df correction)
    # Ljung-Box
    q_lags: list[int]
    q_stats: list[float]
    q_pvalues: list[float]
    # Normality (Jarque-Bera)
    jb_stat: float
    jb_pvalue: float
    skewness: float
    excess_kurtosis: float
    # Extreme residuals: (1-based obs index, z-value)
    extreme: list[tuple[int, float]]
    # ACF/PACF of residuals
    acf: np.ndarray
    pacf: np.ndarray
    # Seasonal pattern in residuals
    seasonal: SeasonalDetectionResult | None = None
    # Model label (for titles)
    label: str = ""
    # Over-parametrization (Bloque I)
    param_labels: list[str] | None = None          # label for each free param
    param_corr: np.ndarray | None = None           # full correlation matrix
    high_corr_pairs: list | None = None            # (i, j, r, lbl_i, lbl_j) with |r|>threshold

    @property
    def white_noise(self) -> bool:
        """True if all Q p-values > 0.05."""
        return all(p > 0.05 for p in self.q_pvalues)

    @property
    def normal(self) -> bool:
        """True if JB p-value > 0.05 (cannot reject normality)."""
        return self.jb_pvalue > 0.05

    @property
    def clean(self) -> bool:
        """True if white noise, normal, and no residual seasonality."""
        seas_ok = (self.seasonal is None) or (not self.seasonal.seasonal_detected)
        return self.white_noise and self.normal and seas_ok

    def summary(self) -> str:
        lines = [f"Diagnosis: {self.label}",
                 f"  n={self.nobs}, npar={self.npar}",
                 "  Ljung-Box Q:"]
        for l, q, p in zip(self.q_lags, self.q_stats, self.q_pvalues):
            flag = "" if p > 0.05 else "  *** SIGNIFICANT"
            lines.append(f"    lag={l:3d}  Q={q:6.2f}  p={p:.4f}{flag}")
        lines.append(f"  Jarque-Bera:  stat={self.jb_stat:.3f}  p={self.jb_pvalue:.4f}"
                     f"  skew={self.skewness:.3f}  kurt={self.excess_kurtosis:.3f}")
        if self.extreme:
            lines.append(f"  Extreme residuals (|z|>3): {len(self.extreme)}")
            for obs, z in self.extreme[:5]:
                lines.append(f"    obs {obs}: z={z:.3f}")
        if self.seasonal:
            lines.append(f"  Seasonal in residuals: {self.seasonal.seasonal_detected} "
                         f"(p={self.seasonal.p_value:.4f})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parameter labeling and correlation (Bloque I)
# ---------------------------------------------------------------------------

def _build_param_labels(model) -> list[str]:
    """Human-readable label for each free parameter in model.params order.

    Order matches fue cast_us._build_initial_x:
      1. omega_free per intervention
      2. delta_free per intervention
      3. AR regular (free)
      4. AR seasonal (free)
      5. MA regular (free)
      6. MA seasonal (free)
      7. AR_f free coefs
      8. MA_f free coefs
      9. mu (if estimate_mu)
    """
    labels: list[str] = []
    freq = model.series.freq if model.series is not None else 12

    # 1. Intervention omega_free
    for itv in (model.interventions or []):
        t    = itv.type
        om_f = (list(itv.omega_free)
                if (hasattr(itv, "omega_free") and itv.omega_free) else [])
        h    = int(round(getattr(itv, "harmonic", 1)))
        for i, free in enumerate(om_f):
            if not free:
                continue
            if t == "cos":
                labels.append(f"cos(k={h})")
            elif t == "sin":
                labels.append(f"sin(k={h})")
            elif t == "alter":
                labels.append("alter")
            else:
                xi = {"step": "S", "pulse": "I", "impulse": "I",
                      "ramp": "R", "compimp": "CI"}.get(t, t)
                labels.append(f"ω({xi})" if i == 0 else f"ω({xi},l{i})")

    # 2. Intervention delta_free
    for itv in (model.interventions or []):
        df = (list(itv.delta_free)
              if (hasattr(itv, "delta_free") and itv.delta_free) else [])
        for i, free in enumerate(df):
            if free:
                labels.append(f"δ(l{i})")

    # 3. AR regular
    for fi, factor in enumerate(model.ar or []):
        fl = (model.ar_free[fi]
              if (model.ar_free and fi < len(model.ar_free))
              else [True] * len(factor))
        for li, free in enumerate(fl):
            if free:
                labels.append(f"AR({li+1})")

    # 4. AR seasonal
    for fi, factor in enumerate(model.ar_s or []):
        fl = (model.ar_s_free[fi]
              if (hasattr(model, "ar_s_free") and model.ar_s_free
                  and fi < len(model.ar_s_free))
              else [True] * len(factor))
        for li, free in enumerate(fl):
            if free:
                labels.append(f"AR_s({(li+1)*freq})")

    # 5. MA regular
    for fi, factor in enumerate(model.ma or []):
        fl = (model.ma_free[fi]
              if (model.ma_free and fi < len(model.ma_free))
              else [True] * len(factor))
        for li, free in enumerate(fl):
            if free:
                labels.append(f"MA({li+1})")

    # 6. MA seasonal
    for fi, factor in enumerate(model.ma_s or []):
        fl = (model.ma_s_free[fi]
              if (hasattr(model, "ma_s_free") and model.ma_s_free
                  and fi < len(model.ma_s_free))
              else [True] * len(factor))
        for li, free in enumerate(fl):
            if free:
                labels.append(f"MA_s({(li+1)*freq})")

    # 7. AR_f free coefs
    for f_idx, ff in enumerate(model.ar_f or []):
        if ff.free:
            labels.append(f"AR_f(f={f_idx})")

    # 8. MA_f free coefs
    for f_idx, ff in enumerate(model.ma_f or []):
        if ff.free:
            labels.append(f"MA_f(f={f_idx})")

    # 9. mu
    if getattr(model, "estimate_mu", False):
        labels.append("μ")

    return labels


def _compute_param_corr(model,
                         threshold: float = 0.7) -> tuple[np.ndarray | None, list, list[str]]:
    """
    Compute correlation matrix of estimated parameters from cov_matrix.

    Returns (corr_matrix, high_corr_pairs, param_labels).
    high_corr_pairs: list of (i, j, r, label_i, label_j) for |r| > threshold.
    Returns (None, [], []) when the covariance matrix is unavailable.
    """
    if model._result is None:
        return None, [], []
    cov_raw = getattr(model._result, "cov_matrix", None)
    if cov_raw is None:
        return None, [], []

    cov = np.asarray(cov_raw, dtype=float)
    n   = cov.shape[0]
    if n < 2:
        return None, [], []

    var = np.diag(cov)
    if np.any(var < 0) or np.any(np.sqrt(np.maximum(var, 0)) < 1e-15):
        return None, [], []

    stds = np.sqrt(var)
    corr = cov / np.outer(stds, stds)
    np.clip(corr, -1.0, 1.0, out=corr)

    labels = _build_param_labels(model)
    # Safety: align label count with matrix dimension
    if len(labels) < n:
        labels = labels + [f"p{i}" for i in range(len(labels), n)]
    labels = labels[:n]

    pairs = [
        (i, j, float(corr[i, j]), labels[i], labels[j])
        for i in range(n)
        for j in range(i + 1, n)
        if abs(corr[i, j]) > threshold
    ]

    return corr, pairs, labels


# ---------------------------------------------------------------------------
# Main diagnosis function
# ---------------------------------------------------------------------------

def _npar(model) -> int:
    """Count free ARMA + mu parameters (used for Q df correction)."""
    n = 0
    for factor in (model.ar or []):
        n += len(factor)
    for factor in (model.ar_s or []):
        n += len(factor)
    for factor in (model.ma or []):
        n += len(factor)
    for factor in (model.ma_s or []):
        n += len(factor)
    if model.mu0 != 0.0:
        n += 1
    return n


def diagnose(model, z_threshold: float = 3.0) -> DiagnosisResult:
    """
    Diagnose a fitted fue.Model.

    Parameters
    ----------
    model        : fue.Model, already fitted (.fit() called)
    z_threshold  : absolute residual threshold for "extreme" flag (default 3)

    Returns
    -------
    DiagnosisResult
    """
    r_ts  = model.residuals          # fue.TimeSeries
    r     = np.asarray(r_ts.data, dtype=float)
    n     = len(r)
    npar  = _npar(model)
    s     = model.series.freq if model.series is not None else 1
    lags  = _default_lags_fug(n, s)

    # --- ACF/PACF of residuals ---
    acf_r  = np.asarray(_fue_acf(r,  lags=lags), dtype=float)
    pacf_r = np.asarray(_fue_pacf(r, lags=lags), dtype=float)

    # --- Ljung-Box Q-test at standard lags ---
    if s > 1:
        q_check_lags = [s // 2, s, 2 * s, 3 * s]
    else:
        q_check_lags = [6, 12, 24]
    q_check_lags = [l for l in q_check_lags if l <= lags]

    lb = ljung_box(r, q_check_lags, df_correction=npar)
    q_stats   = [float(x) for x in lb['statistic']]
    q_pvalues = [float(x) for x in lb['pvalue']]

    # --- Jarque-Bera normality ---
    jb = jarque_bera(r)
    jb_stat   = float(jb.statistic)
    jb_pvalue = float(jb.pvalue)
    skew      = float(sp_stats.skew(r))
    kurt      = float(sp_stats.kurtosis(r))   # excess kurtosis (Fisher)

    # --- Extreme residuals (compare standardized residuals against threshold) ---
    r_mean = r.mean()
    r_std  = r.std(ddof=1) if len(r) > 1 else 1.0
    r_z    = (r - r_mean) / r_std if r_std > 0 else r
    extreme = [(i + 1, float(z)) for i, z in enumerate(r_z) if abs(z) > z_threshold]
    extreme.sort(key=lambda x: abs(x[1]), reverse=True)

    # --- Seasonal detection on residuals ---
    # Use lam=1.0 (identity, no Box-Cox): residuals are already transformed.
    seasonal = None
    if s > 1:
        try:
            seasonal = detect_seasonality(r_ts, d=0, lam=1.0)
        except Exception:
            pass

    # --- Model label ---
    name = getattr(model.series, 'name', '') if model.series else ''
    label = name or "model"

    # --- Over-parametrization: correlation matrix (Bloque I) ---
    param_corr, high_corr_pairs, param_labels = _compute_param_corr(model)

    return DiagnosisResult(
        residuals=r,
        nobs=n,
        npar=npar,
        q_lags=q_check_lags,
        q_stats=q_stats,
        q_pvalues=q_pvalues,
        jb_stat=jb_stat,
        jb_pvalue=jb_pvalue,
        skewness=skew,
        excess_kurtosis=kurt,
        extreme=extreme,
        acf=acf_r,
        pacf=pacf_r,
        seasonal=seasonal,
        label=label,
        param_labels=param_labels,
        param_corr=param_corr,
        high_corr_pairs=high_corr_pairs,
    )


# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

def _period_label(start: tuple[int, int], offset: int, freq: int) -> str:
    """Convert (year, month) + 0-based offset to 'MM/YYYY' string."""
    y0, m0 = start
    total_months = (y0 - 1900) * freq + (m0 - 1) + offset if freq == 12 else offset
    if freq == 12:
        month = (m0 - 1 + offset) % 12 + 1
        year  = y0 + (m0 - 1 + offset) // 12
        return f"{month:02d}/{year}"
    elif freq == 4:
        q = (m0 - 1 + offset) % 4 + 1
        year = y0 + (m0 - 1 + offset) // 4
        return f"Q{q}/{year}"
    else:
        return str(y0 + offset)


def plot_diagnosis(result: DiagnosisResult, model=None) -> plt.Figure:
    """
    Four-panel diagnosis figure:
      top-left:  standardized residuals time series
      top-right: QQ-normal plot
      bot-left:  ACF of residuals
      bot-right: PACF of residuals
    """
    r     = result.residuals
    n     = result.nobs
    lags  = len(result.acf)
    band  = 1.96 / math.sqrt(n)

    s = 1
    start = (1900, 1)
    if model is not None and model.series is not None:
        s     = model.series.freq
        start = model.series.start

    fig, axes = plt.subplots(2, 2, figsize=(13, 7))
    fig.suptitle(f"Diagnosis: {result.label}", fontweight='bold', fontsize=13)

    # ---- top-left: residuals time series ----
    ax = axes[0, 0]
    x = np.arange(n)
    ax.axhline(0,   color='black', lw=0.8)
    ax.axhline(+2,  color='red',   lw=0.6, ls='--')
    ax.axhline(-2,  color='red',   lw=0.6, ls='--')
    ax.axhline(+3,  color='red',   lw=0.4, ls=':')
    ax.axhline(-3,  color='red',   lw=0.4, ls=':')
    ax.plot(x, r, color='#333333', lw=0.8)
    for obs, z in result.extreme:
        ax.scatter(obs - 1, z, color='red', s=20, zorder=5)
    ax.set_title("Residuals", fontsize=10)
    ax.set_xlabel("obs")
    ax.set_ylabel("z")
    _tj_spines(ax)

    # ---- top-right: QQ normal ----
    ax = axes[0, 1]
    (osm, osr), (slope, intercept, _) = sp_stats.probplot(r, dist='norm')
    ax.plot(osm, osr, 'o', ms=2.5, color='#333333', alpha=0.7)
    lo, hi = osm[0], osm[-1]
    ax.plot([lo, hi], [slope * lo + intercept, slope * hi + intercept],
            color='red', lw=1.2)
    ax.set_title("QQ Normal", fontsize=10)
    ax.set_xlabel("Theoretical quantiles")
    ax.set_ylabel("Sample quantiles")
    _tj_spines(ax)

    # ---- bottom-left: ACF of residuals ----
    ax = axes[1, 0]
    lag_x = np.arange(1, lags + 1)
    cmax  = max(float(np.abs(result.acf).max()),
                float(np.abs(result.pacf).max())) * 1.15 + 0.05
    _draw_acf_panel(ax, lag_x, result.acf, band=band, cmax=cmax,
                    freq=s, lags=lags, label="ACF")

    # ---- bottom-right: PACF of residuals ----
    ax = axes[1, 1]
    _draw_acf_panel(ax, lag_x, result.pacf, band=band, cmax=cmax,
                    freq=s, lags=lags, label="PACF")

    # Add Q-test annotation
    q_str = "  ".join(
        f"Q({l})={q:.1f}" + ("*" if p < 0.05 else "")
        for l, q, p in zip(result.q_lags, result.q_stats, result.q_pvalues)
    )
    jb_str = f"JB={result.jb_stat:.2f} (p={result.jb_pvalue:.3f})"
    fig.text(0.5, 0.01, f"{q_str}    {jb_str}",
             ha='center', fontsize=8.5, style='italic')

    fig.tight_layout(rect=[0, 0.03, 1, 0.97])
    return fig


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def save_diagnosis_report(model, path: str, z_threshold: float = 3.0) -> DiagnosisResult:
    """
    Run diagnose(), generate figure, save self-contained HTML report.
    """
    import base64, io

    result = diagnose(model, z_threshold=z_threshold)
    fig    = plot_diagnosis(result, model)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    # Q-test rows
    q_rows = "\n".join(
        f"<tr><td>{l}</td><td>{q:.2f}</td>"
        f"<td style='color:{'red' if p<0.05 else 'green'}'>{p:.4f}</td></tr>"
        for l, q, p in zip(result.q_lags, result.q_stats, result.q_pvalues)
    )

    # Extreme residuals table
    if result.extreme:
        ext_rows = "\n".join(
            f"<tr><td>{obs}</td><td>{z:+.3f}</td></tr>"
            for obs, z in result.extreme[:15]
        )
        ext_table = (
            "<h3>Residuos extremos (|z| &gt; {:.1f})</h3>"
            "<table border='1' cellpadding='4' cellspacing='0' "
            "style='font-size:12px;border-collapse:collapse'>"
            "<tr><th>obs</th><th>z</th></tr>"
            f"{ext_rows}</table>"
        ).format(z_threshold)
    else:
        ext_table = f"<p>No hay residuos con |z| &gt; {z_threshold:.1f}.</p>"

    # Seasonal check
    if result.seasonal:
        seas_txt = (
            f"<p>Estacionalidad residual: "
            f"<b>{'Sí' if result.seasonal.seasonal_detected else 'No'}</b> "
            f"(F={result.seasonal.f_stat:.2f}, p={result.seasonal.p_value:.4f})</p>"
        )
    else:
        seas_txt = ""

    # Overall verdict
    verdict_color = '#2a7a2a' if result.clean else '#cc3333'
    verdict_text  = 'APROBADO ✓' if result.clean else 'REVISAR ✗'

    name_str = result.label
    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>Diagnosis {name_str}</title>
<style>
  body {{ font-family: Arial, sans-serif; max-width: 900px; margin: 2em auto; }}
  table {{ border-collapse: collapse; font-size: 12px; }}
  th, td {{ padding: 4px 8px; border: 1px solid #ccc; }}
  th {{ background: #eee; }}
</style>
</head>
<body>
<h1>Diagnosis: {name_str}</h1>
<p>n={result.nobs}, par ARMA={result.npar} &nbsp;&nbsp;
<span style='color:{verdict_color};font-weight:bold'>{verdict_text}</span></p>

<img src='data:image/png;base64,{b64}' style='max-width:100%'>

<h3>Contraste de ruido blanco (Ljung-Box Q)</h3>
<table>
<tr><th>Lag</th><th>Q</th><th>p-valor</th></tr>
{q_rows}
</table>

<h3>Normalidad (Jarque-Bera)</h3>
<p>JB = {result.jb_stat:.3f} &nbsp; p = {result.jb_pvalue:.4f} &nbsp;
{'<b>Normal ✓</b>' if result.normal else '<b style="color:red">No normal ✗</b>'}
&nbsp;&nbsp; asimetría = {result.skewness:.3f} &nbsp; curtosis exceso = {result.excess_kurtosis:.3f}</p>

{seas_txt}
{ext_table}
</body>
</html>"""

    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(html)

    return result
