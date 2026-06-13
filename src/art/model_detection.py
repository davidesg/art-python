"""
Automatic ARIMA order detection via ACF/PACF pattern similarity.
Python port of ART C model_detection.c adaptive_grid_search.

Algorithm:
  For each candidate (p,q,P,Q) structure:
    1. Pre-filter: validate AR/MA pattern against empirical ACF/PACF
    2. Compute theoretical ACF/PACF with representative coefficients
       (statsmodels ArmaProcess — no coefficient grid needed)
    3. Extract structural features from both empirical and theoretical patterns
    4. Score similarity (weighted 60/25/15: short lags / seasonal lags / cut-off points)
    5. Apply parsimony penalty (mirrors C evaluate_model_similarity exactly)
  Return top-N candidates sorted by final score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.arima_process import ArmaProcess

from fue import TimeSeries
from fue.diagnostics import acf as _fue_acf, pacf as _fue_pacf
from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines

from .identification import boxcox_transform, apply_differences, _default_lags_fug


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PatternFeatures:
    acf_cutting_lag: int       # first lag where ACF cuts off (3 consec. non-sig.)
    pacf_cutting_lag: int
    combined_cutting_lag: int  # min of the two (non-zero)
    acf_decay_rate: float      # geom-weighted avg of |acf[i]/acf[i-1]|, lags 2-8
    pacf_decay_rate: float
    acf_initial_spikes: int    # |acf[i]| > threshold for i=1..5
    pacf_initial_spikes: int
    mixed_pattern_score: float # [0,1]: ARMA indicator
    seasonal_acf_strength: float
    seasonal_pacf_strength: float
    seasonal_pattern: float    # avg of the two strengths
    acf: np.ndarray            # full ACF values (lags 1..lags)
    pacf: np.ndarray           # full PACF values


@dataclass
class ModelSpec:
    p: int; d: int; q: int
    P: int; D: int; Q: int; s: int
    similarity: float           # final score after parsimony adjustment
    raw_similarity: float       # score before parsimony
    acf_theoretical: np.ndarray
    pacf_theoretical: np.ndarray
    sparse_ar_lag: int = 0      # >0: AR only at this lag (φ₁=...=0, φₖ≠0)
    sparse_ma_lag: int = 0

    def label(self) -> str:
        if self.sparse_ar_lag > 0:
            ar_str = f"AR[{self.sparse_ar_lag}]"
        elif self.p > 0:
            ar_str = f"AR({self.p})"
        else:
            ar_str = ""
        if self.sparse_ma_lag > 0:
            ma_str = f"MA[{self.sparse_ma_lag}]"
        elif self.q > 0:
            ma_str = f"MA({self.q})"
        else:
            ma_str = ""
        base = "+".join(x for x in [ar_str, ma_str] if x) or "WN"
        seas = ""
        if self.s > 1 and (self.P > 0 or self.Q > 0):
            seas = f"({self.P},{self.D},{self.Q})_{self.s}"
        return f"({self.d},{self.D})  {base}{seas}"


# ---------------------------------------------------------------------------
# Geometric weight helper
# ---------------------------------------------------------------------------

def _geom_w(i: int, base: float = 0.8) -> float:
    return base ** i


# ---------------------------------------------------------------------------
# Pattern feature extraction  (mirrors extract_pattern_features in C)
# ---------------------------------------------------------------------------

def _pattern_features(
    acf: np.ndarray,
    pacf: np.ndarray,
    s: int,
    n: int,
) -> PatternFeatures:
    """
    Extract structural features from an ACF/PACF array (lags 1..lags).
    n is used to compute the significance threshold.
    """
    lags      = len(acf)
    threshold = 1.96 / math.sqrt(n)

    # --- 1. Cutting-off lags (3 consecutive non-significant) ---
    acf_cut = pacf_cut = 0
    for i in range(lags - 2):
        lag = i + 1        # 1-based
        if acf_cut == 0 and all(abs(acf[i + k]) < threshold for k in range(3)):
            acf_cut = lag
        if pacf_cut == 0 and all(abs(pacf[i + k]) < threshold for k in range(3)):
            pacf_cut = lag
        if acf_cut and pacf_cut:
            break

    combined = min(x for x in (acf_cut, pacf_cut) if x > 0) if (acf_cut or pacf_cut) else 0
    if combined == 0:
        combined = max(acf_cut, pacf_cut)

    # --- 2. Decay rates (lags 2..min(8, lags)) ---
    def _decay(vals):
        s_val = s_w = 0.0
        for i in range(1, min(8, lags)):
            if abs(vals[i - 1]) > 1e-6:
                w = _geom_w(i + 1, 0.9)
                s_val += abs(vals[i] / vals[i - 1]) * w
                s_w   += w
        return s_val / s_w if s_w > 0 else 0.0

    acf_decay  = _decay(acf)
    pacf_decay = _decay(pacf)

    # --- 3. Initial spikes (lags 1..5) ---
    thr_init = threshold * 1.2
    acf_spikes  = sum(1 for i in range(min(5, lags)) if abs(acf[i])  > thr_init)
    pacf_spikes = sum(1 for i in range(min(5, lags)) if abs(pacf[i]) > thr_init)

    # --- 4. Mixed pattern score ---
    mixed = sum([
        acf_cut == 0 and pacf_cut == 0,
        acf_decay  > 0.3 and pacf_decay  > 0.3,
        acf_spikes > 0   and pacf_spikes > 0,
    ]) / 3.0

    # --- 5. Seasonal strengths ---
    seas_acf = seas_pacf = 0.0
    seas_count = 0
    if s > 1:
        thr_seas = threshold * 1.5
        for k in range(1, 6):
            lag = k * s
            if lag > lags:
                break
            seas_count += 1
            seas_acf  += abs(acf[lag - 1])
            seas_pacf += abs(pacf[lag - 1])
            # satellites (weight 0.3)
            if lag - 1 >= 1:
                seas_acf  += abs(acf[lag - 2]) * 0.3
                seas_pacf += abs(pacf[lag - 2]) * 0.3
            if lag < lags:
                seas_acf  += abs(acf[lag]) * 0.3
                seas_pacf += abs(pacf[lag]) * 0.3
        if seas_count > 0:
            seas_acf  /= seas_count
            seas_pacf /= seas_count

    seasonal_pattern = (seas_acf + seas_pacf) / 2.0

    return PatternFeatures(
        acf_cutting_lag=acf_cut,
        pacf_cutting_lag=pacf_cut,
        combined_cutting_lag=combined,
        acf_decay_rate=acf_decay,
        pacf_decay_rate=pacf_decay,
        acf_initial_spikes=acf_spikes,
        pacf_initial_spikes=pacf_spikes,
        mixed_pattern_score=mixed,
        seasonal_acf_strength=seas_acf,
        seasonal_pacf_strength=seas_pacf,
        seasonal_pattern=seasonal_pattern,
        acf=acf.copy(),
        pacf=pacf.copy(),
    )


# ---------------------------------------------------------------------------
# AR/MA pattern validators  (mirrors validate_ar/ma_pattern in C)
# ---------------------------------------------------------------------------

def _validate_ar(p: int, pacf: np.ndarray, threshold: float) -> bool:
    if p == 0:
        return True
    lags = len(pacf)
    if p <= lags and abs(pacf[p - 1]) < threshold * 0.8:
        return False
    sig_after = sum(1 for i in range(p, min(p + 3, lags)) if abs(pacf[i]) > threshold)
    return sig_after <= 1


def _validate_ma(q: int, acf: np.ndarray, threshold: float) -> bool:
    if q == 0:
        return True
    lags = len(acf)
    if q <= lags and abs(acf[q - 1]) < threshold * 0.8:
        return False
    non_sig = sum(1 for i in range(q, min(q + 3, lags)) if abs(acf[i]) < threshold)
    return non_sig >= 2


# ---------------------------------------------------------------------------
# Effective order limits from empirical significance
# ---------------------------------------------------------------------------

def _effective_orders(
    acf: np.ndarray, pacf: np.ndarray,
    s: int, n: int,
    p_max: int, q_max: int, P_max: int, Q_max: int,
) -> tuple[int, int, int, int]:
    lags = len(acf)
    thr  = 1.96 / math.sqrt(n)

    def _last_sig(vals, max_ord, thr_mult=1.0):
        result = 0
        t = thr * thr_mult
        for lag in range(1, min(max_ord, lags) + 1):
            if abs(vals[lag - 1]) > t:
                result = lag
            elif lag + 2 <= lags and all(abs(vals[lag - 1 + k]) < t for k in range(3)):
                break
        return result

    eff_p = _last_sig(pacf, p_max)
    eff_q = _last_sig(acf,  q_max)

    eff_P = eff_Q = 0
    if s > 1:
        seas_thr = thr * 1.2
        for k in range(1, P_max + 1):
            lag = k * s
            if lag <= lags and abs(pacf[lag - 1]) > seas_thr:
                eff_P = k
        for k in range(1, Q_max + 1):
            lag = k * s
            if lag <= lags and abs(acf[lag - 1]) > seas_thr:
                eff_Q = k

    return eff_p, eff_q, eff_P, eff_Q


# ---------------------------------------------------------------------------
# Theoretical ACF/PACF via statsmodels ArmaProcess
# ---------------------------------------------------------------------------

def _theoretical_acf_pacf(
    p: int, q: int, P: int, Q: int,
    s: int, lags: int,
    sparse_ar_lag: int = 0,
    sparse_ma_lag: int = 0,
) -> tuple[np.ndarray, np.ndarray] | tuple[None, None]:
    """
    Compute theoretical ACF/PACF of SARIMA(p,0,q)(P,0,Q)_s with representative
    coefficients.  No grid search needed — the structural pattern (cut-offs,
    decay, seasonal peaks) is determined by (p,q,P,Q,s), not by exact coefficients.

    Representative coefficients (same as ART C high-order fallback):
      φᵢ = 0.5/(i+1),  θᵢ = 0.3/(i+1),  Φᵢ = 0.4/(i+1),  Θᵢ = 0.3 + i*0.1 (≤0.8)

    sparse_ar_lag > 0: zero all AR lags except sparse_ar_lag (models φ₁=0, φₖ≠0).
    sparse_ma_lag > 0: same for MA.
    """
    phi   = np.array([0.5 / (i + 1) for i in range(p)])
    theta = np.array([0.3 / (i + 1) for i in range(q)])
    if sparse_ar_lag > 0 and p >= sparse_ar_lag:
        phi = np.zeros(p)
        phi[sparse_ar_lag - 1] = 0.40
    if sparse_ma_lag > 0 and q >= sparse_ma_lag:
        theta = np.zeros(q)
        theta[sparse_ma_lag - 1] = 0.35
    Phi   = np.array([0.4 / (i + 1) for i in range(P)])
    Theta = np.array([min(0.3 + i * 0.1, 0.8) for i in range(Q)])

    # AR poly: (1 - φ₁B - ... - φₚBᵖ)(1 - Φ₁Bˢ - ... - ΦₚB^{Ps})
    ar_reg  = np.r_[1.0, -phi]
    ar_seas = np.zeros(P * s + 1);  ar_seas[0] = 1.0
    for i, v in enumerate(Phi):
        ar_seas[(i + 1) * s] = -v
    ar_poly = np.convolve(ar_reg, ar_seas)

    # MA poly: (1 + θ₁B + ... + θ_qB^q)(1 + Θ₁Bˢ + ...)
    ma_reg  = np.r_[1.0, theta]
    ma_seas = np.zeros(Q * s + 1);  ma_seas[0] = 1.0
    for i, v in enumerate(Theta):
        ma_seas[(i + 1) * s] = v
    ma_poly = np.convolve(ma_reg, ma_seas)

    try:
        proc = ArmaProcess(ar=ar_poly, ma=ma_poly)
        if not proc.isstationary or not proc.isinvertible:
            return None, None
        acf_all  = proc.acf(lags=lags + 1)   # shape (lags+1,), lag 0 = 1.0
        pacf_all = proc.pacf(lags=lags + 1)
        return acf_all[1:lags + 1], pacf_all[1:lags + 1]
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# Pattern similarity  (mirrors pattern_similarity in C — weights 60/25/15)
# ---------------------------------------------------------------------------

def _pattern_similarity(
    theo: PatternFeatures,
    emp:  PatternFeatures,
    s: int,
    lags: int,
) -> float:
    sim = total_w = 0.0

    # --- 60%: first 8 lags (ACF + PACF, geometric weights) ---
    n_first = min(8, lags)
    fs = fw = 0.0
    for i in range(n_first):
        dacf  = abs(float(theo.acf[i])  - float(emp.acf[i]))
        dpacf = abs(float(theo.pacf[i]) - float(emp.pacf[i]))
        lag_sim = 1.0 - (dacf + dpacf) / 2.0
        w = _geom_w(i + 1, 0.8)
        fs += lag_sim * w;  fw += w
    if fw > 0:
        sim     += (fs / fw) * 0.60
        total_w += 0.60

    # --- 25%: seasonal lags s, 2s (ACF → Q, PACF → P) ---
    if s > 1:
        acf_ss = acf_sw = pacf_ss = pacf_sw = 0.0
        for k in range(1, 3):
            lag = k * s
            if lag > lags:
                break
            w = 1.0 / k
            acf_ss  += (1.0 - abs(float(theo.acf[lag-1])  - float(emp.acf[lag-1])))  * w
            acf_sw  += w
            pacf_ss += (1.0 - abs(float(theo.pacf[lag-1]) - float(emp.pacf[lag-1]))) * w
            pacf_sw += w
        seas = 0.0;  seas_w = 0.0
        if acf_sw  > 0: seas += (acf_ss  / acf_sw)  * 0.5;  seas_w += 0.5
        if pacf_sw > 0: seas += (pacf_ss / pacf_sw) * 0.5;  seas_w += 0.5
        if seas_w  > 0:
            sim     += (seas / seas_w) * 0.25
            total_w += 0.25

    # --- 15%: cutting-off points ---
    cs = cw = 0.0
    for (t_cut, e_cut, w) in [
        (theo.acf_cutting_lag,      emp.acf_cutting_lag,      0.4),
        (theo.pacf_cutting_lag,     emp.pacf_cutting_lag,     0.4),
        (theo.combined_cutting_lag, emp.combined_cutting_lag, 0.2),
    ]:
        if t_cut > 0 and e_cut > 0:
            diff = abs(t_cut - e_cut)
            mx   = max(t_cut, e_cut)
            cs  += (1.0 - diff / mx) * w
            cw  += w
    if cw > 0:
        sim     += (cs / cw) * 0.15
        total_w += 0.15

    return sim / total_w if total_w > 0 else 0.0


# ---------------------------------------------------------------------------
# Parsimony penalty  (mirrors evaluate_model_similarity in C exactly)
# ---------------------------------------------------------------------------

def _parsimony_score(
    similarity: float,
    p: int, q: int, P: int, Q: int,
    emp: PatternFeatures,
    s: int,
) -> float:
    total = p + q + P + Q
    if total == 0:
        return 0.0

    penalty  = 0.03 + total * 0.015
    if P > 0 and Q > 0:  penalty += 0.12   # both seasonal AR+MA simultaneously
    if total > 4:         penalty += 0.08
    if total > 6:         penalty += 0.12
    if total > 8:         penalty += 0.20

    final = similarity - penalty

    # Bonus for simple models with good fit
    if total <= 3 and similarity > 0.6:
        final = min(1.0, final + 0.05)

    # Seasonal evidence adjustment
    if s > 1:
        if (Q > 0 and emp.seasonal_acf_strength  > 0.2) or \
           (P > 0 and emp.seasonal_pacf_strength > 0.2):
            final += 0.03
        if (P > 0 or Q > 0) and emp.seasonal_pattern < 0.1:
            final -= 0.08

    return max(0.0, min(1.0, final))


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def _remove_harmonics(w: np.ndarray, s: int, n_harmonics: int) -> np.ndarray:
    """
    OLS-subtract harmonic fit (cos/sin f=1..n_harmonics) + intercept from w.
    Used when D=0 so seasonal structure in ACF/PACF reflects ARMA, not harmonics.
    """
    nw = len(w)
    cols = [np.ones(nw)]
    for f in range(1, n_harmonics + 1):
        omega = 2.0 * math.pi * f / s
        t = np.arange(nw, dtype=float)
        cols.append(np.cos(omega * t))
        if 2 * f < s:            # skip sin at Nyquist
            cols.append(np.sin(omega * t))
    X = np.column_stack(cols)
    coeff, _, _, _ = np.linalg.lstsq(X, w, rcond=None)
    return w - X @ coeff


def suggest_orders(
    ts: TimeSeries,
    d: int = 1,
    D: int = 0,
    lam: float = 0.0,
    p_max: int = 3,
    q_max: int = 3,
    P_max: int = 1,
    Q_max: int = 1,
    top_n: int = 5,
    n_harmonics: int = -1,
) -> list[ModelSpec]:
    """
    Suggest SARIMA orders (p,q,P,Q) by matching theoretical ACF/PACF patterns
    to the empirical ACF/PACF of the transformed+differenced series.

    Parameters
    ----------
    ts           : fue.TimeSeries
    d, D         : differencing orders already decided (from identification listing)
    lam          : Box-Cox lambda (0.0 = log)
    p_max, q_max, P_max, Q_max : maximum orders to consider
    top_n        : number of candidates to return (sorted by score descending)
    n_harmonics  : harmonic pairs to subtract before ACF/PACF.
                   -1 (default) = auto: s//2 when D==0 and s>1, else 0.
                   0 = no subtraction.

    Returns
    -------
    list[ModelSpec]  sorted by similarity score (best first)
    """
    s    = ts.freq
    n    = len(ts.data)

    # --- Prepare series: transform + difference ---
    y = np.asarray(ts.data, dtype=float)
    z = boxcox_transform(y, lam)
    w = apply_differences(z, s, d, D)
    nw = len(w)

    # --- Subtract deterministic harmonics when D=0 ---
    if n_harmonics == -1:
        n_harmonics = (s // 2) if (D == 0 and s > 1) else 0
    if n_harmonics > 0:
        w = _remove_harmonics(w, s, n_harmonics)

    lags = _default_lags_fug(nw, s)

    # --- Empirical ACF/PACF ---
    acf_emp  = np.asarray(_fue_acf(w,  lags=lags), dtype=float)
    pacf_emp = np.asarray(_fue_pacf(w, lags=lags), dtype=float)

    threshold = 1.96 / math.sqrt(nw)

    emp_feat = _pattern_features(acf_emp, pacf_emp, s, nw)

    # --- Reduce search space ---
    eff_p, eff_q, eff_P, eff_Q = _effective_orders(
        acf_emp, pacf_emp, s, nw,
        p_max, q_max, P_max, Q_max,
    )
    eff_p = max(eff_p, p_max) if eff_p == 0 else min(eff_p, p_max)
    eff_q = max(eff_q, q_max) if eff_q == 0 else min(eff_q, q_max)
    eff_P = min(eff_P, P_max)
    eff_Q = min(eff_Q, Q_max)

    # --- Score all candidate structures ---
    candidates: list[ModelSpec] = []
    seen: set[tuple] = set()

    def _add_candidate(p, q, P, Q, sparse_ar=0, sparse_ma=0):
        key = (p, q, P, Q, sparse_ar, sparse_ma)
        if key in seen:
            return
        seen.add(key)
        acf_th, pacf_th = _theoretical_acf_pacf(
            p, q, P, Q, s, lags,
            sparse_ar_lag=sparse_ar, sparse_ma_lag=sparse_ma,
        )
        if acf_th is None:
            return
        th_feat = _pattern_features(acf_th, pacf_th, s, nw)
        raw_sim = _pattern_similarity(th_feat, emp_feat, s, lags)
        final   = _parsimony_score(raw_sim, p, q, P, Q, emp_feat, s)
        candidates.append(ModelSpec(
            p=p, d=d, q=q,
            P=P, D=D, Q=Q, s=s,
            similarity=final,
            raw_similarity=raw_sim,
            acf_theoretical=acf_th,
            pacf_theoretical=pacf_th,
            sparse_ar_lag=sparse_ar,
            sparse_ma_lag=sparse_ma,
        ))

    for p in range(eff_p + 1):
        if not _validate_ar(p, pacf_emp, threshold):
            continue
        for q in range(eff_q + 1):
            if not _validate_ma(q, acf_emp, threshold):
                continue
            for P in range(eff_P + 1):
                for Q in range(eff_Q + 1):
                    if p == 0 and q == 0 and P == 0 and Q == 0:
                        continue
                    _add_candidate(p, q, P, Q)

    # --- Sparse-lag candidates: AR/MA only at lag k (φ₁=...=φₖ₋₁=0, φₖ≠0) ---
    # Handles "AR at lag 2" structures where lag-1 coefficient is constrained to 0.
    # Always generate for lags 2..eff_p; OLS harmonic subtraction can shift the
    # empirical PACF spike so the per-lag significance test is unreliable.
    for lag in range(2, min(eff_p, p_max) + 1):
        _add_candidate(lag, 0, 0, 0, sparse_ar=lag)
    for lag in range(2, min(eff_q, q_max) + 1):
        _add_candidate(0, lag, 0, 0, sparse_ma=lag)

    candidates.sort(key=lambda m: m.similarity, reverse=True)
    return candidates[:top_n]


# ---------------------------------------------------------------------------
# Plot: empirical ACF/PACF vs top-N theoretical
# ---------------------------------------------------------------------------

def plot_model_comparison(
    ts: TimeSeries,
    specs: list[ModelSpec],
    d: int = 1,
    D: int = 0,
    lam: float = 0.0,
    n_harmonics: int = -1,
) -> plt.Figure:
    """
    Multi-row figure comparing empirical ACF/PACF (top row, black)
    with theoretical ACF/PACF of each candidate (coloured overlay).
    """
    s    = ts.freq
    y    = np.asarray(ts.data, dtype=float)
    z    = boxcox_transform(y, lam)
    w    = apply_differences(z, s, d, D)
    nw   = len(w)

    if n_harmonics == -1:
        n_harmonics = (s // 2) if (D == 0 and s > 1) else 0
    if n_harmonics > 0:
        w = _remove_harmonics(w, s, n_harmonics)

    lags = _default_lags_fug(nw, s)

    acf_emp  = np.asarray(_fue_acf(w,  lags=lags), dtype=float)
    pacf_emp = np.asarray(_fue_pacf(w, lags=lags), dtype=float)

    band  = 2.0 / math.sqrt(nw)
    cmax  = float(max(np.abs(acf_emp).max(), np.abs(pacf_emp).max(),
                      *(np.abs(sp.acf_theoretical).max() for sp in specs),
                      *(np.abs(sp.pacf_theoretical).max() for sp in specs))) + 0.05

    n_rows  = 1 + len(specs)
    fig_h   = 2.8 * n_rows
    lag_x   = np.arange(1, lags + 1)
    colors  = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd']

    fig, axes = plt.subplots(n_rows, 2, figsize=(13.0, fig_h),
                             gridspec_kw={'wspace': 0.30, 'hspace': 0.65})
    if n_rows == 1:
        axes = axes[np.newaxis, :]

    name = getattr(ts, 'name', 'series')

    for row, (acf_v, pacf_v, title, lw, color) in enumerate([
        (acf_emp, pacf_emp,
         f"{name}  empirical  [d={d}, D={D}]", 3.0, 'k'),
    ] + [
        (sp.acf_theoretical, sp.pacf_theoretical,
         f"{sp.label()}   score={sp.similarity:.3f}  (raw={sp.raw_similarity:.3f})",
         2.2, colors[row - 1])
        for row, sp in enumerate(specs, start=1)
    ]):
        ax_acf, ax_pacf = axes[row]
        _draw_acf_panel(ax_acf,  lag_x, acf_v,  band, cmax, s, lags, '', lw=lw)
        _draw_acf_panel(ax_pacf, lag_x, pacf_v, band, cmax, s, lags, '', lw=lw)
        ax_acf.set_title(title, fontsize=9.5, pad=4, color=color if row > 0 else 'k')
        ax_acf.set_ylabel('acf',  fontsize=9)
        ax_pacf.set_ylabel('pacf', fontsize=9)

        if row == 0:
            ax_acf.set_xlabel('empirical', fontsize=8.5, color='#555')

    fig.suptitle(
        f"Model detection — {name}  [λ={lam}, d={d}, D={D}, s={s}]",
        fontsize=11, fontweight='bold', y=1.01,
    )
    return fig


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

def save_model_detection_report(
    ts: TimeSeries,
    path: str,
    d: int = 1,
    D: int = 0,
    lam: float = 0.0,
    p_max: int = 3,
    q_max: int = 3,
    P_max: int = 1,
    Q_max: int = 1,
    top_n: int = 5,
) -> list[ModelSpec]:
    """
    Run suggest_orders, generate comparison figure, save self-contained HTML.
    """
    import base64, io

    specs = suggest_orders(ts, d=d, D=D, lam=lam,
                           p_max=p_max, q_max=q_max,
                           P_max=P_max, Q_max=Q_max,
                           top_n=top_n)
    fig = plot_model_comparison(ts, specs, d=d, D=D, lam=lam)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode()

    name    = getattr(ts, 'name', 'series')
    lam_str = "100·log" if lam == 0.0 else f"λ={lam}"
    rows = "\n".join(
        f"<tr><td>{i+1}</td><td><b>{sp.label()}</b></td>"
        f"<td>{sp.similarity:.3f}</td><td>{sp.raw_similarity:.3f}</td></tr>"
        for i, sp in enumerate(specs)
    )
    table = (
        "<table border='1' cellpadding='4' cellspacing='0' "
        "style='font-size:12px;border-collapse:collapse'>"
        "<tr style='background:#ddd'><th>#</th><th>Model</th>"
        "<th>Score</th><th>Raw</th></tr>"
        + rows + "</table>"
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Model Detection — {name}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 30px; max-width: 1200px; }}
    h1   {{ font-size: 16px; border-bottom: 2px solid #333; padding-bottom: 5px; }}
    h2   {{ font-size: 13px; margin-top: 24px; color: #333; }}
    p    {{ font-size: 12px; color: #555; }}
  </style>
</head>
<body>
<h1>Model Detection: {name}</h1>
<p>
  [{lam_str}, d={d}, D={D}, s={ts.freq}] &nbsp;|&nbsp;
  p_max={p_max}, q_max={q_max}, P_max={P_max}, Q_max={Q_max}
</p>
<p>
  Scores: pattern similarity (weighted 60% short lags / 25% seasonal / 15% cut-offs)
  with parsimony adjustment.<br>
  Estimate candidates with <code>fue</code> MVENC and use diagnosis to select the final model.
</p>

<h2>Top-{top_n} candidates</h2>
{table}

<h2>ACF/PACF comparison</h2>
<p>Top row: empirical. Coloured rows: theoretical pattern of each candidate.</p>
<img src="data:image/png;base64,{b64}" style="max-width:100%">
</body>
</html>
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

    return specs
