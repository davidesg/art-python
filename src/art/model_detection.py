"""
Automatic ARIMA order detection via ACF/PACF pattern similarity.
Python port of ART C model_detection.c adaptive_grid_search.

Algorithm:
  For each candidate (p,q,P,Q) structure:
    1. Pre-filter: validate AR/MA pattern against empirical ACF/PACF
    2. Compute theoretical ACF/PACF with representative coefficients
       (ART's C simulator, ported in `_acf_teorica` — no coefficient grid)
    3. Extract structural features from both empirical and theoretical patterns
    4. Score similarity (weighted 60/25/15: short lags / seasonal lags / cut-off points)
    5. Apply parsimony penalty (mirrors C evaluate_model_similarity exactly)
  Return top-N candidates sorted by final score.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from fue.diagnostics import ljung_box as _fue_ljung_box
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fue import TimeSeries
from fue.diagnostics import acf as _fue_acf, pacf as _fue_pacf
from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines

from ._acf_teorica import acf_pacf as _acf_pacf_bj

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
    aicc: float | None = None   # BUG-0198: the fit that ranks (quick estimates)
    weight: float | None = None # its Akaike weight among the listed candidates

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


def _validate_white_noise(w: np.ndarray, lags: int, alpha: float = 0.05) -> bool:
    """¿Es admisible el candidato (0,0,0,0)?

    BUG-0048. `_validate_ar(0, ...)` y `_validate_ma(0, ...)` devuelven True sin
    mirar nada: para un orden 0 no hay «retardo p» que comprobar. Mientras el
    ruido blanco estaba excluido de la enumeración eso no tenía consecuencia.
    Admitido por BUG-0044, la tuvo: pasó a ser el ÚNICO candidato que entra en la
    papeleta sin pasar la puerta que pasan todos los demás.

    Y la bonificación de parsimonia lo empuja hacia arriba. Sobre ∇ln PGAS
    --PACF(1)=+0.58 y PACF(2)=-0.31, las dos FUERA de la banda de 0.215, o sea un
    AR(2) de manual-- el ruido blanco salía CUARTO y el AR(2) quinto, aunque la
    similitud cruda favorece al AR(2) (0.7649 contra 0.7614). Los invierte el
    ajuste: +0.02 al ruido blanco (no paga parámetros y cobra el bonus) contra
    -0.01 al AR(2). Un modelo con dos retardos significativos por debajo de «no
    hace falta modelo» es insensato.

    **El ruido blanco tiene su propio CONTRASTE, y es el que se usa aquí.** No se
    cuenta cuántos retardos salen de la banda --eso es un sucedáneo, y además
    depende de cuántos retardos se miren-- sino que se pregunta a la Q de
    Ljung-Box, que es el mismo instrumento con el que la diagnosis decide si unos
    residuos son blancos. Si la Q rechaza, «no hace falta modelo» no es una
    hipótesis sostenible y el candidato no entra.

    `df_correction=0` a propósito: aquí no se han estimado parámetros todavía, se
    está preguntando por los DATOS.
    """
    lb = _fue_ljung_box(w, lags=lags, df_correction=0)
    return float(lb["pvalue"][-1]) > alpha


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

    # BUG-0194. The regular AR orders are searched as before, up to 3. An AR
    # of order s/2 (or a multiple within p_max) enters ONLY on its own
    # pattern: the PACF bar at s/2 significant and ISOLATED, every lag from 4
    # to s/2 - 1 inside the band — the half-year wave of HICP_ES_m01's
    # residuals (+0.18 at 1, +0.23 at 6, 2..5 inside). Decided 29-sep-2026: a
    # block of significant PACF lags is persistence, not a high-order AR —
    # on Chile's ∇ln CPI (an I(2) series, PACF significant at 1, 2, 3, 5, 6)
    # letting any AR up to s/2 compete made an AR(6) win and absorb the unit
    # root that the final DCD has to find.
    eff_p = _last_sig(pacf, min(p_max, 3))
    # Generalised on the analyst's remark (29-sep-2026): with HYBRID
    # seasonality and only a regular AR specified, a high-order AR can show at
    # any badly represented seasonal frequency, not only at f = 2. So every
    # submultiple s/k >= 4 is looked at (monthly: 6, f = 2; 4, f = 3), with
    # the same isolation rule. The MEG is what settles the specification.
    if s > 1:
        subs = sorted({s // k for k in range(1, s + 1) if s % k == 0 and 4 <= s // k <= p_max})
        for lag in subs:
            if (lag <= lags and abs(pacf[lag - 1]) > thr
                    and all(abs(pacf[k - 1]) <= thr for k in range(4, lag))):
                eff_p = max(eff_p, lag)
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
# Theoretical ACF/PACF: ART's C simulator (ARMA.c), ported in `_acf_teorica`
# ---------------------------------------------------------------------------

def _yule_walker_template(p, acf_emp):
    """The AR(p) coefficients for a high-order template (BUG-0194)."""
    base = np.array([0.5 / (i + 1) for i in range(p)])
    scaled = base * (0.8 / base.sum())
    if acf_emp is None or len(acf_emp) < p:
        return scaled
    r = np.r_[1.0, np.asarray(acf_emp, float)[:p]]
    R = np.array([[r[abs(i - j)] for j in range(p)] for i in range(p)])
    try:
        phi = np.linalg.solve(R, r[1:p + 1])
    except np.linalg.LinAlgError:
        return scaled
    roots = np.roots(np.r_[1.0, -phi][::-1])
    return phi if np.all(np.abs(roots) > 1.0) else scaled


def _theoretical_acf_pacf(
    p: int, q: int, P: int, Q: int,
    s: int, lags: int,
    sparse_ar_lag: int = 0,
    sparse_ma_lag: int = 0,
    acf_emp: np.ndarray | None = None,
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

    # BUG-0194. For p >= 4 the representative 0.5/(i+1) (the C's high-order
    # fallback) sums to more than 1 — 1.04 at p = 4, 1.225 at p = 6 — so the
    # template was NOT STATIONARY and the candidate vanished in silence: no AR
    # of order 4 or more could ever enter the list. And a decaying template has
    # no bar at p, which is what a high-order AR is proposed for (the half-year
    # wave at 6 in monthly data). Decided 29-sep-2026: for a complete AR of
    # order >= 4 the template is the AR(p) of Yule-Walker on the EMPIRICAL ACF
    # — what an AR(p) looks like on these data —; if that is not stationary,
    # the representative one scaled to sum 0.8. Orders <= 3 are unchanged.
    if p >= 4 and not sparse_ar_lag:
        phi = _yule_walker_template(p, acf_emp)

    # The polynomials in the Box-Jenkins convention, as the C:
    #   (1 − φ₁B − …)(1 − Φ₁Bˢ − …) wₜ = (1 − θ₁B − …)(1 − Θ₁Bˢ − …) aₜ
    # BUG-0192: through statsmodels' ArmaProcess the port wrote the MA as
    # (1 + θB)(1 + ΘBˢ), since it takes the polynomial as written and the C's
    # θ > 0 were passed unchanged; the representative θ = 0.3 then gave +0.275
    # at lag 1 instead of the C's negative bar, and on series G the airline came
    # fourth. `_acf_teorica` is the C's own computation (ψ weights, Durbin-
    # Levinson), so the convention is the C's by construction.
    try:
        return _acf_pacf_bj(phi, theta, Phi, Theta, s, lags)
    except Exception:
        return None, None


# ---------------------------------------------------------------------------
# The template of a candidate, SEARCHED as ART's C does (BUG-0198)
# ---------------------------------------------------------------------------
#
# The port had replaced the C's search by one set of «representative»
# coefficients per order (φᵢ = 0.5/(i+1), θᵢ = 0.3/(i+1)…), on the belief that
# "the structural pattern is determined by (p,q,P,Q,s), not by exact
# coefficients". It is not: the representative AR(2), 1 − 0.5B − 0.25B², has
# REAL roots and cannot oscillate, so an AR(2) with complex roots — a cycle,
# the pattern the school looks for in monthly CPI and that `ar_factorization`
# turns into AR_f candidates for the MEG — never looked like its own
# correlogram and ranked behind the AR(1): 1 in 12 simulated series, and on
# the muskrat neither the AR(2) nor Jenkins and Alavi's AR(6) entered the
# list. The C (ART_18 model_detection.c, adaptive_grid_search):
#
#   * a pure AR (q = Q = 0) takes the Yule-Walker coefficients of the
#     empirical ACF (`estimate_ar_yule_walker`), the seasonal AR those of the
#     ACF at the seasonal lags;
#   * any other model searches a coarse grid (step 0.30 in [−0.9, 0.9]; the
#     seasonal MA in [0.1, 0.8]), every coefficient of a polynomial at the same
#     value, then refines each coefficient by ±0.2 in steps of 0.1;
#   * past p + q + P + Q = 10, the representative coefficients.
#
# The best similarity reached is the candidate's; the parsimony penalty then
# charges its orders, as before.

GRID_MIN, GRID_MAX = -0.9, 0.9
COARSE_STEP, FINE_STEP = 0.30, 0.10
SMA_MIN, SMA_MAX = 0.1, 0.8


def _contract(c, limit=0.95):
    """A polynomial 1 − Σ cᵢBⁱ made stationary (invertible) WITHOUT moving its
    cycles: cᵢ·ρⁱ scales every inverse root by ρ and keeps its angle — the
    period of a complex pair. Untouched when already inside.

    Not the C's guard. `estimate_ar_yule_walker` rescales any AR with
    Σ|φ| ≥ 0.99 to 0.95 (Hannan-Rissanen at 0.95 → 0.90), and an AR(2) with
    complex roots — φ = (1.0, −0.5): inverse roots of modulus 0.71, a period
    of 8 — has Σ|φ| = 1.5: the guard flattened exactly the cycles this
    identifier must find (BUG-0198), to (0.63, −0.32), whose AICc then lost
    by 30 points to an ARMA(3,1)."""
    c = np.asarray(c, float)
    if c.size == 0:
        return c
    if not np.all(np.isfinite(c)):
        return None
    mx = float(np.max(np.abs(np.roots(np.r_[1.0, -c]))))   # inverse roots
    if mx < 1.0:
        return c
    rho = limit / mx
    return c * rho ** np.arange(1, c.size + 1)


def _yw(r, p):
    """Yule-Walker AR(p) from autocorrelations r[0..p] (r[0] = 1), made
    stationary by `_contract` if it is not (never otherwise)."""
    R = np.array([[r[abs(i - j)] for j in range(p)] for i in range(p)])
    try:
        phi = np.linalg.solve(R, np.asarray(r[1:p + 1], float))
    except np.linalg.LinAlgError:
        return None
    return _contract(phi)


def _score(phi, theta, Phi, Theta, s, lags, emp_feat, nw):
    acf_th, pacf_th = _acf_pacf_bj(phi, theta, Phi, Theta, s, lags)
    if acf_th is None:
        return None, None, -1.0
    th = _pattern_features(acf_th, pacf_th, s, nw)
    return acf_th, pacf_th, _pattern_similarity(th, emp_feat, s, lags)


def _searched_template(p, q, P, Q, s, lags, acf_emp, emp_feat, nw,
                       sparse_ar=0, sparse_ma=0, w=None):
    """(acf, pacf, raw similarity) of the candidate's best template."""
    if sparse_ar or sparse_ma or p + q + P + Q > 10:
        acf_th, pacf_th = _theoretical_acf_pacf(
            p, q, P, Q, s, lags, sparse_ar_lag=sparse_ar, sparse_ma_lag=sparse_ma,
            acf_emp=acf_emp)
        if acf_th is None:
            return None, None, 0.0
        th = _pattern_features(acf_th, pacf_th, s, nw)
        return acf_th, pacf_th, _pattern_similarity(th, emp_feat, s, lags)

    r = np.r_[1.0, np.asarray(acf_emp, float)]
    if q == 0 and Q == 0:                                   # pure AR: Yule-Walker
        phi = _yule_walker_template(p, acf_emp) if p >= 4 else (
            _yw(r, p) if p else np.zeros(0))
        Phi = np.zeros(0)
        if P:
            rs = np.r_[1.0, [r[i * s] if i * s < len(r) else 0.0 for i in range(1, P + 1)]]
            Phi = _yw(rs, P)
        if phi is not None and Phi is not None:
            a, pa, sim = _score(phi, [], Phi, [], s, lags, emp_feat, nw)
            if a is not None:
                return a, pa, sim
        # a singular or non-stationary Yule-Walker: fall back to the grid

    grid = np.arange(GRID_MIN, GRID_MAX + 1e-9, COARSE_STEP)
    sgrid = np.arange(SMA_MIN, SMA_MAX + 1e-9, COARSE_STEP)
    best = (None, None, -1.0, None)
    for a in (grid if p else [0.0]):
        for b in (grid if q else [0.0]):
            for c in (grid if P else [0.0]):
                for e in (sgrid if Q else [0.0]):
                    co = [np.full(p, a), np.full(q, b), np.full(P, c), np.full(Q, e)]
                    acf_th, pacf_th, sim = _score(*co, s, lags, emp_feat, nw)
                    if sim > best[2]:
                        best = (acf_th, pacf_th, sim, co)
    # The fitted coefficients compete with the grid (option B, BUG-0198): a
    # pure AR's template is Yule-Walker — fitted to these data —, and a grid
    # whose coefficients start all equal cannot fit an MA as closely; on
    # series G the AR(3)×SAR(1) reached 0.973 against the airline's 0.882 on
    # that alone. Hannan-Rissanen refined by conditional least squares gives
    # the MA models their own fitted template.
    if w is not None:
        fit = _refined_fit(w, acf_emp, s, p, q, P, Q)
        if fit is not None:
            a_, pa_, sim_ = _score(*fit, s, lags, emp_feat, nw)
            if sim_ > best[2]:
                best = (a_, pa_, sim_, [np.asarray(c, float) for c in fit])
    if best[3] is None:
        return None, None, 0.0
    co = [x.copy() for x in best[3]]
    for kind in range(4):                                    # the refinement
        lo, hi = (SMA_MIN, SMA_MAX) if kind == 3 else (GRID_MIN, GRID_MAX)
        for i in range(len(co[kind])):
            orig = float(best[3][kind][i])
            for delta in np.arange(-0.2, 0.2 + 1e-9, FINE_STEP):
                trial = [x.copy() for x in co]
                trial[kind][i] = min(max(orig + delta, lo), hi)
                acf_th, pacf_th, sim = _score(*trial, s, lags, emp_feat, nw)
                if sim > best[2]:
                    best = (acf_th, pacf_th, sim, trial)
            co[kind][i] = best[3][kind][i]
    return best[0], best[1], best[2]


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
    # BUG-0044. Aquí había un caso especial `if total == 0: return 0.0`: la
    # función de PARSIMONIA daba la peor nota al modelo más parsimonioso. Era una
    # rama «esto no puede pasar» —el candidato (0,0,0,0) estaba excluido de la
    # enumeración— que, admitido éste, se convirtió en el ranking. Medido sobre
    # los residuos del ITCER: similitud cruda 0.9197, la más alta de ocho
    # candidatas, y salía última con 0.0000.
    #
    # Ya no hay caso especial, y ésa es la corrección: la fórmula general lo
    # trata bien sola. Con total=0 la penalización es la base (0.03, sin término
    # por parámetro) y le alcanza la bonificación de «simple y con buen ajuste»,
    # de modo que a igual similitud cruda queda 0.015 por encima de un modelo de
    # un parámetro — que es lo que la parsimonia debe hacer— y por debajo cuando
    # la forma prefiere al otro.
    #
    # Los dos intentos anteriores fallaron por los dos lados y conviene dejarlo
    # escrito: sin penalización y CON bonificación, el ruido blanco ganaba al
    # MA(1) en el caso dorado del proyecto pese a tener peor similitud cruda
    # (0.7880 contra 0.8173) y empeoraba el AIC en 10 puntos; sin penalización y
    # SIN bonificación, perdía a igual similitud cruda. La fórmula general no
    # tiene ninguno de los dos problemas.
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

# ---------------------------------------------------------------------------
# The ranking by fit (ART_18's rank_shortlist_by_fit — BUG-0198)
# ---------------------------------------------------------------------------
#
# The pattern similarity proposes; the FIT ranks. With searched templates a
# larger model always looks at least as similar — the AR(3)×SAR(1) of series G
# reached 0.973 against the airline's 0.882 — and a per-parameter penalty in
# similarity units cannot say by how much it should. The C closes the loop
# with a light estimation of every candidate (Yule-Walker for a pure AR,
# iterated Hannan-Rissanen for an ARMA, Yule-Walker at the seasonal lags for
# Φ, Θ₁ by inverting ρ_s) and its AICc on a COMMON sample, and breaks ties
# within ΔAICc < 1 by Box-Jenkins' parsimony: fewer parameters win; at equal
# count the C asks its MLP, here the pattern similarity. The candidates are
# still what the correlogram proposes; the MLE of `confirm_and_estimate`
# decides in the end.

TIE_AICC = 2.0


def _hannan_rissanen(y, p, q, niter=4):
    """ARMA(p, q) by iterated Hannan-Rissanen, as the C: a long AR (Yule-
    Walker) for the first residuals, then OLS of y on its lags and the
    residuals' lags, the residuals refiltered with the model each iteration.
    Box-Jenkins convention: y_t = Σ φ y_{t−i} + e_t − Σ θ e_{t−j}. None if it
    fails."""
    y = np.asarray(y, float)
    n = y.size
    yc = y - y.mean()
    m = max(p, q) + int(math.sqrt(n))
    m = max(m, max(p, q) + 2)
    m = min(m, n - 10)
    if m < 1:
        return None
    ac = np.asarray(_fue_acf(yc, lags=min(m + 5, n - 2)), float)
    phl = _yw(np.r_[1.0, ac], m)
    if phl is None:
        return None
    e = np.zeros(n)
    for t in range(m, n):
        e[t] = yc[t] - phl @ yc[t - m:t][::-1]
    start = max(m + q, max(p, q))
    nobs = n - start
    k = p + q
    if nobs < k + 5:
        return None
    beta = np.zeros(k)
    for _ in range(niter):
        X = np.column_stack([yc[start - j - 1:n - j - 1] for j in range(p)]
                            + [e[start - j - 1:n - j - 1] for j in range(q)])
        Y = yc[start:]
        try:
            beta = np.linalg.solve(X.T @ X + 1e-6 * np.eye(k), X.T @ Y)
        except np.linalg.LinAlgError:
            return None
        for t in range(start, n):
            e[t] = yc[t] - (beta[:p] @ yc[t - p:t][::-1] if p else 0.0) \
                - (beta[p:] @ e[t - q:t][::-1] if q else 0.0)
    # the C rescaled Σ|coef| > 0.95 to 0.90; here only what is outside moves
    if not np.all(np.isfinite(beta)):
        return None
    phi, theta = _contract(beta[:p], 0.90), _contract(-beta[p:], 0.90)
    return None if phi is None or theta is None else (phi, theta)


def _seasonal_ma1(rho_s):
    """Θ₁ by inverting ρ_s = −Θ/(1 + Θ²), the invertible root (as the C)."""
    if abs(rho_s) < 1e-6:
        return 0.0
    rho_s = max(min(rho_s, 0.49), -0.49)
    return (-1.0 + math.sqrt(max(1.0 - 4.0 * rho_s * rho_s, 0.0))) / (2.0 * rho_s)


def _stable(coef):
    if coef is None:
        return False
    c = np.asarray(coef, float)
    if c.size == 0:
        return True
    if not np.all(np.isfinite(c)):
        return False
    return bool(np.all(np.abs(np.roots(np.r_[1.0, -c][::-1])) > 1.0))


_FITS: dict = {}          # refined light estimates, per suggest_orders call


def _refined_fit(w, acf_emp, s, p, q, P, Q):
    """`_quick_fit` refined by conditional least squares on the candidate's own
    start, computed once per candidate and call: the template search and the
    AICc information share it."""
    key = (p, q, P, Q)
    if key not in _FITS:
        fit = _quick_fit(w, acf_emp, s, p, q, P, Q)
        if fit is not None and p + q + P + Q:
            fit = _css_refine(np.asarray(w, float), fit, s, max(p + P * s, q + Q * s))
        _FITS[key] = fit
    return _FITS[key]


def _quick_fit(w, acf_emp, s, p, q, P, Q):
    """The light estimates of a candidate, or None if unstable (as the C)."""
    r = np.r_[1.0, np.asarray(acf_emp, float)]
    if q == 0:
        phi = _yw(r, p) if p else np.zeros(0)
        theta = np.zeros(0)
    else:
        hr = _hannan_rissanen(w, p, q)
        if hr is None:
            phi = np.array([0.3 / (i + 1) for i in range(p)])
            theta = np.array([0.3 / (i + 1) for i in range(q)])
        else:
            phi, theta = hr
    if phi is None:
        return None
    Phi = np.zeros(0)
    if P:
        rs = np.r_[1.0, [r[i * s] if i * s < len(r) else 0.0 for i in range(1, P + 1)]]
        Phi = _yw(rs, P)
        if Phi is None:
            return None
    Theta = np.zeros(Q)
    if Q:
        Theta[0] = _seasonal_ma1(r[s]) if s < len(r) else SMA_MIN
        Theta[1:] = SMA_MIN
    if not (_stable(phi) and _stable(Phi) and _stable(theta) and _stable(Theta)):
        return None
    return phi, theta, Phi, Theta


def _css_rss(y, phi, theta, Phi, Theta, s, start):
    """Conditional sum of squares from `start`: the residuals of
    ar(B) y = ma(B) e filtered from zero pre-sample values (scipy's lfilter,
    the recursion of the C's compute_sarima_aicc), the first `start` dropped."""
    from scipy.signal import lfilter
    ar = np.convolve(np.r_[1.0, -np.asarray(phi, float)], _seasonal_poly(Phi, s))
    ma = np.convolve(np.r_[1.0, -np.asarray(theta, float)], _seasonal_poly(Theta, s))
    e = lfilter(ar, ma, y - y.mean())[start:]
    return float(e @ e)


def _css_refine(y, fit, s, start):
    """The light estimates refined by conditional least squares (BUG-0198):
    so that the AICc compares FITS, not the roughness of Hannan-Rissanen —
    with a true MA(1) the rough MA lost to a Yule-Walker AR(3) that imitated
    it. Stationary and invertible, or the light estimates are kept."""
    from scipy.optimize import minimize
    sizes = [len(c) for c in fit]
    x0 = np.concatenate([np.asarray(c, float) for c in fit])
    if x0.size == 0:
        return fit

    def split(x):
        out, i = [], 0
        for k in sizes:
            out.append(x[i:i + k]); i += k
        return out

    def obj(x):
        parts = split(x)
        if not all(_stable(c) for c in parts):
            return 1e30
        return _css_rss(y, *parts, s, start)

    try:
        r = minimize(obj, x0, method="Powell",
                     options={"xtol": 1e-4, "ftol": 1e-8, "maxfev": 400 * x0.size})
    except Exception:                                        # noqa: BLE001
        return fit
    if not r.success and r.fun >= obj(x0):
        return fit
    best = split(r.x) if r.fun < obj(x0) else fit
    return best


def _sarima_aicc(y, phi, theta, Phi, Theta, s, min_start, refine=True):
    """AICc of the multiplicative SARMA on a common start (the C's
    compute_sarima_aicc), its coefficients refined by conditional least
    squares from the light estimates. White noise: k = 0."""
    y = np.asarray(y, float)
    n = y.size
    k = len(phi) + len(theta) + len(Phi) + len(Theta)
    dar = len(phi) + len(Phi) * s
    dma = len(theta) + len(Theta) * s
    if dar >= n // 2 or dma >= n // 2:
        return math.inf
    start = max(dar, dma, min_start)
    if start >= n - 2:
        return math.inf
    if refine and k:
        phi, theta, Phi, Theta = _css_refine(y, (phi, theta, Phi, Theta), s, start)
    used = n - start
    rss = _css_rss(y, phi, theta, Phi, Theta, s, start)
    if used <= k + 2 or rss <= 0.0:
        return math.inf
    return used * math.log(rss / used) + 2.0 * k + 2.0 * k * (k + 1.0) / (used - k - 1)


def _seasonal_poly(c, s):
    b = np.zeros(len(c) * s + 1)
    b[0] = 1.0
    for i, v in enumerate(c):
        b[(i + 1) * s] = -float(v)
    return b


TIE_SIM = 0.04


def _nested_parsimony(cands):
    """Box-Jenkins' parsimony when the pattern cannot tell candidates apart.

    With fitted templates a model that contains another (an ARMA(2,1) and the
    AR(2) inside it) always looks at least as similar, by a hair; and two
    different models can look equally similar (series G: the airline 0.902,
    an AR(1)×SAR(1) 0.905). Within `TIE_SIM` of the best similarity the
    candidate with FEWER parameters goes first; at equal count a PURE model
    (AR or MA at each level, regular and seasonal) before a mixed one — Box-Jenkins' order, and the guard against
    an ARMA(1,1) whose φ ≈ 1 absorbs a missing difference (the thesis'
    Colombian CPI: it tied with the AR(2) and won on AICc) —; then the lower
    AICc: the fit settles what the pattern leaves tied, and only that (option
    B). The others stay in the list, behind."""
    rest = list(cands)
    out = []
    while rest:
        top = rest[0]
        band = [c for c in rest if top.similarity - c.similarity < TIE_SIM]
        pick = min(band, key=lambda c: (c.p + c.q + c.P + c.Q,
                                        (c.p > 0 and c.q > 0) or (c.P > 0 and c.Q > 0),
                                        c.aicc if c.aicc is not None else math.inf,
                                        -c.similarity))
        out.append(pick)
        rest.remove(pick)
    return out


def _fit_information(cands, w, acf_emp, s):
    """Fill `aicc` and the Akaike `weight` of each candidate (light estimates
    refined by conditional least squares, common start) WITHOUT reordering."""
    if not cands:
        return cands
    start = max(max(c.p + c.P * s, c.q + c.Q * s) for c in cands)
    for c in cands:
        # the refined estimates; on the common start they are re-refined only
        # by the few observations the start adds, so they are used as they are
        fit = _refined_fit(w, acf_emp, s, c.p, c.q, c.P, c.Q)
        c.aicc = math.inf if fit is None else _sarima_aicc(w, *fit, s, start, refine=False)
    fin = [c.aicc for c in cands if math.isfinite(c.aicc)]
    if fin:
        best = min(fin)
        ws = [math.exp(-0.5 * (c.aicc - best)) if math.isfinite(c.aicc) else 0.0
              for c in cands]
        tot = sum(ws)
        for c, v in zip(cands, ws):
            c.weight = v / tot
    return cands


def _rank_by_fit(cands, w, acf_emp, s):
    """Order the candidates by AICc of their light estimates, the ties within
    ΔAICc < 1 by fewer parameters and then by similarity; fill `aicc` and the
    Akaike `weight`. Candidates whose estimates are unstable go last."""
    if not cands:
        return cands
    start = max(max(c.p + c.P * s, c.q + c.Q * s) for c in cands)
    for c in cands:
        fit = _quick_fit(w, acf_emp, s, c.p, c.q, c.P, c.Q)
        c.aicc = math.inf if fit is None else _sarima_aicc(w, *fit, s, start)
    cands.sort(key=lambda c: c.aicc)
    best = cands[0].aicc
    if math.isfinite(best):
        band = [c for c in cands if c.aicc - best < TIE_AICC]
        win = min(band, key=lambda c: (c.p + c.q + c.P + c.Q, -c.similarity))
        cands.remove(win)
        cands.insert(0, win)
        ws = [math.exp(-0.5 * (c.aicc - best)) if math.isfinite(c.aicc) else 0.0
              for c in cands]
        tot = sum(ws)
        for c, v in zip(cands, ws):
            c.weight = v / tot if tot > 0 else None
    return cands


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
    p_max: int | None = None,
    q_max: int = 2,
    P_max: int = 1,
    Q_max: int = 1,
    top_n: int = 5,
    n_harmonics: int = -1,
    incluir_dispersos: bool = False,
) -> list[ModelSpec]:
    """
    Suggest SARIMA orders (p,q,P,Q) by matching theoretical ACF/PACF patterns
    to the empirical ACF/PACF of the transformed+differenced series.

    Parameters
    ----------
    ts           : fue.TimeSeries
    d, D         : differencing orders already decided (from identification listing)
    lam          : Box-Cox lambda (0.0 = log)
    p_max, q_max, P_max, Q_max : maximum orders to consider. BUG-0194, the
                   school's criterion (29-sep-2026): high orders make sense in
                   the AR operators only. p_max defaults to max(3, s/2) in
                   seasonal data — 6 in monthly, so the half-year wave (sales
                   twice a year) can be reached — and 3 otherwise; the MA space
                   is q <= 2 and Q <= 1 (q_max was 3).
    top_n        : number of candidates to return (sorted by score descending)
    n_harmonics  : harmonic pairs to subtract before ACF/PACF.
                   -1 (default) = auto: s//2 when D==0 and s>1, else 0.
                   0 = no subtraction.
    incluir_dispersos : incluir los candidatos con un solo coeficiente en el
                   retardo k (φ₁=…=φₖ₋₁=0). **False por defecto** (BUG-0095):
                   eso no es un orden, es una RESTRICCIÓN de identificación
                   impuesta antes de estimar, y la escuela estima el polinomio
                   completo y descubre la estructura en las raíces después
                   (`ar_factorization`). Quien los quiera —para OFRECERLOS
                   aparte, marcados— los pide explícitamente.

    Returns
    -------
    list[ModelSpec]  sorted by similarity score (best first)
    """
    _FITS.clear()
    s    = ts.freq
    n    = len(ts.data)
    if p_max is None:
        p_max = max(3, s // 2) if s > 1 else 3

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
    # With no significant bar the search opens up to 3, not to p_max: a high
    # order enters only on its own pattern (BUG-0194).
    eff_p = min(p_max, 3) if eff_p == 0 else min(eff_p, p_max)
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
        # BUG-0198: the template is SEARCHED, as in the C — Yule-Walker for a
        # pure AR, the coarse grid and its refinement otherwise — so that it
        # has the shape these data can have (an AR(2) with complex roots, a
        # negative MA) and not one fixed shape per order.
        acf_th, pacf_th, raw_sim = _searched_template(
            p, q, P, Q, s, lags, acf_emp, emp_feat, nw,
            sparse_ar=sparse_ar, sparse_ma=sparse_ma, w=w)
        if acf_th is None:
            return
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
                    # BUG-0044: aquí se saltaba (0,0,0,0). El ruido blanco —«no
                    # hace falta ARMA»— quedaba fuera de la papeleta por
                    # construcción, mientras la herramienta imprime la regla
                    # «Sin estructura → p=0, q=0» justo encima de la lista.
                    #
                    # Y a veces es la respuesta. Sobre ITCER, con la intervención
                    # ya puesta, ningún retardo cruza las bandas y ni el AR(1)
                    # (t=1.87) ni el MA(1) (t=1.80) alcanzan significación: el
                    # BIC prefiere el modelo sin ARMA. Un analista sin contexto
                    # previo llegó a esa conclusión y tuvo que hacerlo CONTRA la
                    # lista, que le ofrecía cinco candidatos todos con
                    # parámetros.
                    #
                    # Su teórico es legítimo y calculable: ACF y PACF todo ceros,
                    # que es lo que el ruido blanco ES. No había razón técnica
                    # para excluirlo, sólo la incomodidad de ofrecer «ninguno»
                    # como candidato.
                    #
                    # BUG-0048: pero entra por la MISMA puerta que los demás. Un
                    # correlograma con retardos significativos no admite «no hace
                    # falta modelo», por muy parsimonioso que sea.
                    if p == q == P == Q == 0 and not _validate_white_noise(
                            w, lags):
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

    # LOS SPARSE VAN DETRÁS, NO MEZCLADOS (BUG-0095).
    #
    # Un candidato «AR sólo en B^k» impone φ₁=…=φₖ₋₁=0 **de entrada**, y eso es
    # una restricción de identificación, no un orden. La práctica Box-Jenkins
    # estima el polinomio COMPLETO y reserva las restricciones —frecuencia fija,
    # ceros intermedios— para el análisis de raíces a posteriori
    # (`ar_factorization`), donde la estructura se DESCUBRE en vez de imponerse.
    #
    # Y no es purismo: el significado de la forma sparse **depende del signo del
    # coeficiente que aún no se ha estimado**. Para (1 − θB²) en datos
    # mensuales:
    #
    #     θ < 0  →  raíces imaginarias puras, ω = π/2, periodo 4  →  f=3
    #     θ > 0  →  dos raíces reales; no hay frecuencia fija ninguna
    #
    # Es decir: la misma restricción es un factor estacional de f=3 o no lo es
    # según un signo. Imponerla antes de estimar es comprometerse con una lectura
    # que todavía no se puede hacer. Después, `ar_factorization` la lee sola —y
    # fue tiene operadores AR(2)/MA(2) de frecuencia fija para expresarla bien.
    #
    # No se ELIMINAN: son plausibles y a veces son la respuesta. Se sacan del
    # ranking y se ofrecen aparte, marcados como lo que son.
    # The C's mixed cells (add_arma_grid_candidates): ARMA(p ≤ 3, q ≤ 2) by
    # Hannan-Rissanen and AICc, the best four added if missing. The cut-off
    # gates read PURE models, and a mixed ARMA tails off on both sides — they
    # kept the ARMA(1,1) out of the list (BUG-0198).
    mixed = []
    for pp in range(1, min(3, p_max) + 1):
        for qq in range(1, min(2, q_max) + 1):
            fit = _quick_fit(w, acf_emp, s, pp, qq, 0, 0)
            if fit is not None:
                mixed.append((_sarima_aicc(w, *fit, s, max(pp, qq)), pp, qq))
    for _a, pp, qq in sorted(mixed)[:4]:
        _add_candidate(pp, qq, 0, 0)

    completos = [m for m in candidates
                 if not (m.sparse_ar_lag or m.sparse_ma_lag)]
    completos.sort(key=lambda m: m.similarity, reverse=True)
    _fit_information(completos, w, acf_emp, s)
    completos = _nested_parsimony(completos)
    # BUG-0198, option B (decided 30-sep-2026): the ORDER is the pattern's —
    # the school's reading of the correlogram. The AICc of the light estimates
    # is INFORMATION for the analyst, not the ranking: on the difference taken
    # once it rewards the models that absorb what the formal tests must decide
    # (φ ≈ 1 where a difference is missing, θ ≈ 1 where one is too many, an AR
    # and an MA nearly cancelling), and on the thesis' I(2) CPIs ranking by it
    # changed the MEG's verdict.
    # BUG-0194, kept under the fitted templates (BUG-0198): an AR of order
    # s/k >= 4 opened by an ISOLATED PACF bar enters the list — with the MA
    # and ARMA templates now fitted, the parsimony charge on its order pushed
    # HICP_ES_m01's AR(6) (raw similarity 0.967, the highest) to seventh. It
    # takes the last place shown if it is not already there.
    if eff_p >= 4:
        high = next((m for m in completos if (m.p, m.q, m.P, m.Q) == (eff_p, 0, 0, 0)), None)
        if high is not None and high not in completos[:top_n]:
            completos.remove(high)
            completos.insert(max(top_n - 1, 0), high)
    if not incluir_dispersos:
        return completos[:top_n]
    dispersos = [m for m in candidates
                 if (m.sparse_ar_lag or m.sparse_ma_lag)]
    dispersos.sort(key=lambda m: m.similarity, reverse=True)
    return completos[:top_n] + dispersos[:max(1, top_n // 2)]


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
    p_max: int | None = None,
    q_max: int = 2,
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
