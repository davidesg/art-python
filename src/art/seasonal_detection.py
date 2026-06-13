"""
Seasonal detection via harmonic regression with HAC F-test.
Python port of ART C seasonal_detection.c / gtk_seasonal_plot.c.

Algorithm (mirrors C implementation exactly):
  1. Apply 100*log() transform (lam=0.0) or identity (lam=1.0)
  2. Apply d regular differences: ∇^d z_t
  3. Fit harmonic regression with differenced basis
       X[t, f] = ∇^d cos(2πft/s),  ∇^d sin(2πft/s)   f=1..s/2
  4. HAC covariance (Newey-West, Bartlett) → robust F-test
  5. OLS covariance → stable confidence bands
  6. A0 matrix: harmonic coefficients γ → seasonal dummy coefficients ω
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats as sp_stats

from fue import TimeSeries
from fue.plots import _tj_spines


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FreqResult:
    """Per-frequency Wald test result."""
    freq_idx: int    # harmonic frequency index (1-based)
    df: int          # degrees of freedom (2 for full harmonic, 1 for Nyquist)
    wald_stat: float # HAC Wald statistic
    p_value: float
    significant: bool


@dataclass
class SeasonalDetectionResult:
    name: str
    freq: int              # seasonal period s
    d: int                 # regular differences applied
    lam: float             # 0.0 = 100*log applied, 1.0 = no transform
    seasonal_detected: bool
    f_stat: float
    p_value: float
    dummies: np.ndarray    # shape (s,) — dummy effects in 100*log units (≈ %)
    dummy_se: np.ndarray   # shape (s,) — OLS-based standard errors
    harmonic_coeffs: np.ndarray  # shape (s-1,) — harmonic γ coefficients
    freq_results: list[FreqResult]  # per-frequency HAC Wald tests
    n_obs: int             # observations after differencing
    message: str


# ---------------------------------------------------------------------------
# Core numerical routines (mirrors seasonal_detection.c)
# ---------------------------------------------------------------------------

def _build_differenced_harmonic_matrix(n: int, d: int, s: int) -> np.ndarray:
    """
    Design matrix for harmonic regression with d-th differenced basis.

    Column 0: intercept.
    For each harmonic freq f=1..s/2:
      - f < s/2: two columns  ∇^d cos(2πft/s),  ∇^d sin(2πft/s)
      - f = s/2 (Nyquist, s even): one column  ∇^d cos(2πft/s)
    t = i + d + 1  (original 1-based time index, matching C code).
    """
    num_harmonics = s - 1
    total_params  = num_harmonics + 1
    X = np.zeros((n, total_params))
    X[:, 0] = 1.0

    col = 1
    for freq in range(1, s // 2 + 1):
        omega = 2.0 * math.pi * freq / s
        for i in range(n):
            t = i + d + 1  # original time (1-based)
            cos_v = [math.cos(omega * (t - k)) for k in range(d + 1)]
            sin_v = [math.sin(omega * (t - k)) for k in range(d + 1)]

            if d == 0:
                dc, ds = cos_v[0], sin_v[0]
            elif d == 1:
                dc = cos_v[0] - cos_v[1]
                ds = sin_v[0] - sin_v[1]
            else:  # d == 2
                dc = cos_v[0] - 2.0 * cos_v[1] + cos_v[2]
                ds = sin_v[0] - 2.0 * sin_v[1] + sin_v[2]

            if freq < s // 2:
                X[i, col]     = dc
                X[i, col + 1] = ds
            elif s % 2 == 0 and freq == s // 2:
                X[i, col] = dc

        col += (2 if freq < s // 2 else 1)

    return X


def _newey_west_hac(X: np.ndarray, u: np.ndarray, max_lags: int) -> np.ndarray:
    """Newey-West HAC sandwich covariance (Bartlett kernel)."""
    n, p = X.shape
    xu = X * u[:, None]          # score matrix (n, p)

    # Meat S (lag 0 + lagged terms with Bartlett weights)
    S = (xu.T @ xu) / n
    for lag in range(1, max_lags + 1):
        w = 1.0 - lag / (max_lags + 1.0)
        cross = (xu[lag:].T @ xu[:-lag]) / n
        S += w * (cross + cross.T)

    try:
        XtX_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        XtX_inv = np.eye(p)

    return XtX_inv @ S @ XtX_inv


def _generate_A0_matrix(s: int) -> np.ndarray:
    """
    A0 matrix (s-1) × (s-1): transforms harmonic coefficients γ → dummy coefficients ω.
    Matches generate_A0_matrix() in seasonal_detection.c.
    """
    m = s - 1
    A0 = np.zeros((m, m))
    col = 0
    for freq in range(1, s // 2 + 1):
        for i in range(m):
            angle = 2.0 * math.pi * freq * (i + 1) / s
            if freq < s // 2:
                A0[i, col]     = math.cos(angle)
                A0[i, col + 1] = math.sin(angle)
            elif s % 2 == 0 and freq == s // 2:
                A0[i, col] = math.cos(angle)
        col += (2 if freq < s // 2 else 1)
    return A0


# ---------------------------------------------------------------------------
# Main detection function
# ---------------------------------------------------------------------------

def detect_seasonality(
    ts: TimeSeries,
    d: int = 1,
    lam: float = 0.0,
    significance: float = 0.05,
) -> SeasonalDetectionResult:
    """
    Detect seasonality via harmonic regression with HAC F-test.

    Parameters
    ----------
    ts           : fue.TimeSeries
    d            : regular differences to apply before regression (default 1)
    lam          : 0.0 → apply 100*log() transform;  1.0 → no transform
    significance : significance level for F-test (default 0.05)

    Returns
    -------
    SeasonalDetectionResult  with dummy coefficients, SEs and test statistics.
    """
    s    = ts.freq
    name = getattr(ts, 'name', 'series')
    y    = np.asarray(ts.data, dtype=float)

    # --- Transform (mirrors apply_log_transform_rescaled in C) ---
    if lam == 0.0:
        y = 100.0 * np.log(np.where(y > 0, y, 1e-6))

    # --- Regular differences ---
    w = y.copy()
    for _ in range(d):
        w = np.diff(w)
    n = len(w)

    num_harmonics = s - 1
    total_params  = num_harmonics + 1

    _fail = SeasonalDetectionResult(
        name=name, freq=s, d=d, lam=lam,
        seasonal_detected=False, f_stat=0.0, p_value=1.0,
        dummies=np.zeros(s), dummy_se=np.zeros(s),
        harmonic_coeffs=np.zeros(num_harmonics),
        freq_results=[], n_obs=n, message="Insufficient observations",
    )
    if n <= 2 * s:
        return _fail

    # --- OLS ---
    X = _build_differenced_harmonic_matrix(n, d, s)
    coeffs, _, _, _ = np.linalg.lstsq(X, w, rcond=None)
    residuals = w - X @ coeffs
    intercept = float(coeffs[0])
    gamma     = coeffs[1:]         # harmonic coefficients (s-1,)

    sse    = float(residuals @ residuals)
    df_res = max(n - total_params, 1)
    s2_ols = sse / df_res
    try:
        XtX_inv = np.linalg.inv(X.T @ X)
    except np.linalg.LinAlgError:
        XtX_inv = np.eye(total_params)
    cov_ols = s2_ols * XtX_inv

    # --- HAC covariance ---
    max_lags = 1 if n <= 100 else (2 if n <= 200 else 3)
    cov_hac  = _newey_west_hac(X, residuals, max_lags)

    # --- HAC F-test on harmonic coefficients (joint H0: γ = 0) ---
    V_gamma = cov_hac[1:, 1:]
    try:
        f_stat = float(gamma @ np.linalg.inv(V_gamma) @ gamma) / num_harmonics
    except np.linalg.LinAlgError:
        f_stat = 0.0

    df1 = num_harmonics
    df2 = max(n - total_params, 1)
    p_value  = float(1.0 - sp_stats.f.cdf(f_stat, df1, df2))
    f_crit   = float(sp_stats.f.ppf(1.0 - significance, df1, df2))
    detected = bool(f_stat > f_crit)

    # --- Harmonics γ → dummy coefficients ω via A0 ---
    A0    = _generate_A0_matrix(s)
    omega = A0 @ gamma                            # (s-1,)
    dummies = np.append(omega, -omega.sum())      # sum-to-zero: ω_s = -Σω_i

    # --- OLS standard errors for dummies ---
    cov_gamma_ols  = cov_ols[1:, 1:]
    cov_omega_ols  = A0 @ cov_gamma_ols @ A0.T   # (s-1, s-1)
    se_first = np.sqrt(np.maximum(np.diag(cov_omega_ols), 1e-12))
    var_last = float(np.sum(cov_omega_ols))
    se_last  = math.sqrt(max(var_last, 1e-12))
    dummy_se = np.append(se_first, se_last)

    # --- Per-frequency HAC Wald tests ---
    freq_results: list[FreqResult] = []
    col_idx = 0
    for f in range(1, s // 2 + 1):
        nyquist = (s % 2 == 0 and f == s // 2)
        df_f = 1 if nyquist else 2
        idx = slice(col_idx, col_idx + df_f)
        g_f = gamma[idx]
        V_f = V_gamma[idx, idx]
        try:
            w_stat = float(g_f @ np.linalg.inv(V_f) @ g_f)
        except np.linalg.LinAlgError:
            w_stat = 0.0
        p_f = float(1.0 - sp_stats.chi2.cdf(w_stat, df_f))
        f_crit_f = float(sp_stats.chi2.ppf(1.0 - significance, df_f))
        freq_results.append(FreqResult(
            freq_idx=f, df=df_f,
            wald_stat=w_stat, p_value=p_f,
            significant=bool(w_stat > f_crit_f),
        ))
        col_idx += df_f

    msg = (
        f"Seasonality {'detected' if detected else 'not detected'} "
        f"(s={s}): HAC F={f_stat:.3f} (p={p_value:.4f}), d={d}"
    )
    return SeasonalDetectionResult(
        name=name, freq=s, d=d, lam=lam,
        seasonal_detected=detected,
        f_stat=f_stat, p_value=p_value,
        dummies=dummies, dummy_se=dummy_se,
        harmonic_coeffs=gamma,
        freq_results=freq_results,
        n_obs=n, message=msg,
    )


# ---------------------------------------------------------------------------
# Plot (mirrors gtk_seasonal_plot.c draw_seasonal_plot())
# ---------------------------------------------------------------------------

_MONTHS_12 = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def plot_seasonality(result: SeasonalDetectionResult) -> plt.Figure:
    """
    Two-panel figure:
      Top: impulse plot of seasonal dummy coefficients with OLS ±1 SE bands.
      Bottom: per-frequency HAC Wald chi-sq statistics with chi-sq critical value.

    Values are in 100*log units (≈ percentage points) when lam=0.0.
    """
    s       = result.freq
    x       = np.arange(s)
    dummies = result.dummies
    se      = result.dummy_se
    labels  = _MONTHS_12 if s == 12 else [f"P{i+1}" for i in range(s)]

    has_freq = bool(result.freq_results)
    n_harmonics = len(result.freq_results) if has_freq else 0

    fig_h = 5.8 if has_freq else 3.8
    fig, axes = plt.subplots(
        2 if has_freq else 1, 1,
        figsize=(9.0, fig_h),
        gridspec_kw={'height_ratios': [2.4, 1.0]} if has_freq else {},
    )
    ax = axes[0] if has_freq else axes

    # --- Top: impulse plot ---
    y_abs = max(float(np.abs(dummies).max()), 2.0 * float(se.max()))
    y_pad = y_abs * 0.20
    y_min, y_max = -y_abs - y_pad, y_abs + y_pad

    _tj_spines(ax, sides=('left', 'bottom'))

    for i in range(s):
        ax.bar(x[i], 2 * se[i], bottom=-se[i],
               color='#cc3333', alpha=0.18, width=0.55, zorder=1)
    ax.vlines(x, 0, dummies, colors='k', linewidth=3.2, zorder=3)
    ax.axhline(0, color='k', lw=1.0, zorder=2)

    for i in range(s):
        v = dummies[i]
        offset = 0.06 * y_abs if v >= 0 else -0.06 * y_abs
        va = 'bottom' if v >= 0 else 'top'
        ax.text(x[i], v + offset, f"{v:.2f}%", ha='center', va=va, fontsize=8)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_xlim(-0.6, s - 0.4)
    ax.set_ylim(y_min, y_max)
    ax.tick_params(direction='out', labelsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.1f}%"))

    status = "DETECTED" if result.seasonal_detected else "not detected"
    lam_str = "100·log" if result.lam == 0.0 else f"λ={result.lam}"
    ax.set_title(
        f"{result.name}  [{lam_str}, d={result.d}]  —  Seasonal pattern  ({status})\n"
        f"HAC  F({result.freq - 1}, {result.n_obs - result.freq}) = {result.f_stat:.3f}"
        f"   p = {result.p_value:.4f}",
        fontsize=10, pad=6,
    )
    if not has_freq:
        ax.set_xlabel("Shaded: ±1 OLS SE  (inference: HAC F-test)", fontsize=9, color='#555')

    # --- Bottom: per-frequency Wald statistics ---
    if has_freq:
        ax2 = axes[1]
        _tj_spines(ax2, sides=('left', 'bottom'))

        fx = np.arange(n_harmonics)
        w_stats = [fr.wald_stat for fr in result.freq_results]
        p_vals  = [fr.p_value   for fr in result.freq_results]
        sigs    = [fr.significant for fr in result.freq_results]
        dfs     = [fr.df for fr in result.freq_results]
        freq_labels = [f"f={fr.freq_idx}" for fr in result.freq_results]

        colors = ['#c00' if sig else '#aaa' for sig in sigs]
        ax2.bar(fx, w_stats, color=colors, width=0.55, zorder=3, alpha=0.75)
        ax2.axhline(0, color='k', lw=0.6, zorder=2)

        # critical values (chi-sq at 5% — use df=2 for most, 1 for Nyquist)
        # draw a step line for the critical value (varies by df)
        for i, fr in enumerate(result.freq_results):
            crit = float(sp_stats.chi2.ppf(0.95, fr.df))
            ax2.plot([i - 0.3, i + 0.3], [crit, crit],
                     color='k', lw=1.4, zorder=4, linestyle='--')

        for i, (w, p, sig) in enumerate(zip(w_stats, p_vals, sigs)):
            ax2.text(i, w + 0.15 * max(w_stats + [1.0]),
                     f"p={p:.2f}", ha='center', va='bottom',
                     fontsize=7.5, color='#c00' if sig else '#555')

        ax2.set_xticks(fx)
        ax2.set_xticklabels(freq_labels, fontsize=9)
        ax2.set_xlim(-0.6, n_harmonics - 0.4)
        ax2.set_ylim(bottom=0)
        ax2.tick_params(direction='out', labelsize=9)
        ax2.set_ylabel("Wald χ²", fontsize=9)
        ax2.set_xlabel(
            "Per-frequency HAC Wald test  (red = significant at 5%;  -- = χ²₂ critical value)",
            fontsize=8.5, color='#555',
        )

    fig.tight_layout(pad=0.8)
    return fig


def save_seasonality(
    ts: TimeSeries,
    path: str,
    d: int = 1,
    lam: float = 0.0,
    significance: float = 0.05,
) -> SeasonalDetectionResult:
    """Detect seasonality and save the plot as a self-contained HTML file."""
    import base64, io
    result = detect_seasonality(ts, d=d, lam=lam, significance=significance)
    fig    = plot_seasonality(result)
    buf    = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    lam_str = "100·log" if lam == 0.0 else f"λ={lam}"
    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8">
<title>Seasonal Detection — {result.name}</title>
<style>body{{font-family:Arial,sans-serif;margin:20px}}
h1{{font-size:15px}}p{{font-size:12px;color:#555}}</style>
</head>
<body>
<h1>Seasonal Detection: {result.name}  [{lam_str}, d={result.d}]</h1>
<p>{result.message}</p>
<p>Impulse = estimated seasonal dummy effect (100·log units ≈ %).<br>
   Shaded band = ±1 OLS SE.  F-test uses HAC (Newey-West) covariance.</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%">
</body></html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    return result
