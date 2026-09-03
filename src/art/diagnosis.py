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
try:
    from fue.plots import _draw_acf_panel, _snap_cmax, _tj_spines
    _FUE_PLOTS = True
except ImportError:
    _FUE_PLOTS = False

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
    # Residual mean against zero — Brajín's adequacy criterion, see `centred`
    mean: float = 0.0
    mean_t: float = 0.0

    @property
    def white_noise(self) -> bool:
        """True if all Q p-values > 0.05."""
        return all(p > 0.05 for p in self.q_pvalues)

    @property
    def normal(self) -> bool:
        """True if JB p-value > 0.05 (cannot reject normality)."""
        return self.jb_pvalue > 0.05

    @property
    def centred(self) -> bool:
        """True if the residual mean is not significantly different from zero.

        Brajín (2004) §2 lists it among the adequacy criteria — "la media
        residual es pequeña en relación con su desviación típica" — and it was
        the one criterion art did not test. It is also the criterion that
        catches a MISSING MEAN, which is exactly what the drift of a price index
        becomes when `estimate_mu` is off: it leaks into the residuals.

        The instrument was blind to it BY CONSTRUCTION. `diagnose` computes the
        residual mean only to CENTRE the residuals before the z-scores, so a
        systematic offset is subtracted away before anything looks for it —
        and Q and Jarque-Bera run on centred residuals too. All three verdicts
        could not see it (BUG-0013).
        """
        return abs(self.mean_t) <= 2.0

    @property
    def residuals_ok(self) -> bool:
        """The residual-shape verdict: white noise, normal, no seasonality.

        This is what the OUTLIER LOOP must consult, and the reason it is
        separate from `clean`. Adding an intervention can fix a residual that
        misbehaves; it cannot fix a mean that is missing from the model, and
        letting the loop try is a category error — the same one as
        re-specifying a transfer's shape around an anomaly.

        Measured: folding `centred` into the stop condition made the autonomous
        run on IPC_ES add TWO interventions it had not added before, chasing a
        drift that no dummy can absorb.
        """
        seas_ok = (self.seasonal is None) or (not self.seasonal.seasonal_detected)
        return self.white_noise and self.normal and seas_ok

    @property
    def clean(self) -> bool:
        """True if the model is adequate: centred AND its residuals well behaved.

        `centred` belongs here — a model whose drift sits in the residuals is
        not adequate, and Brajín lists the criterion — but NOT in the loop's
        stop condition. See `residuals_ok`.
        """
        return self.centred and self.residuals_ok

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

AVISO_COV_DEGENERADA = (
    "provienen de la semilla del BFGS (c·I), no del hessiano — el optimizador "
    "no actualizó esas direcciones. Dos causas: (a) la estimación arrancó ya en "
    "el óptimo, que es lo que un `.pre` es por diseño — reestima desde el `.inp` "
    "(semillas), porque reejecutar un `.pre` VERIFICA que los parámetros no se "
    "mueven, no estima; (b) el modelo tiene solución cerrada y no hay nada que "
    "optimizar — el caso de una media sola sin ARMA, cuyo estimador es la media "
    "muestral. En (b) el parámetro es correcto y sólo su error típico es "
    "inservible: tómalo del `.out` de un modelo estimado, o de la desviación "
    "típica muestral. Ver bugs/BUG-0027."
)


def bfgs_seed_var(result) -> float | None:
    """La varianza con que `fue` inicializa la inversa del hessiano del BFGS.

    NO es una constante: es **2/n**, con n el número de residuos. Medido:

        n = 83  ->  2/83  = 0.0240964     (ITCER, PGAS: 84 obs, d=1)
        n = 119 ->  2/119 = 0.0168067     (sintético de 120 obs, d=1)

    Que sea calculable es lo que permite detectar la degeneración PARCIAL: una
    varianza que sigue valiendo exactamente 2/n es una dirección que el
    optimizador nunca actualizó, aunque otras sí se hayan movido.
    """
    if result is None:
        return None
    res = getattr(result, "residuals", None)
    n = len(res) if res is not None else 0
    return (2.0 / n) if n > 0 else None


def degenerate_variance_indices(result) -> list[int]:
    """Qué parámetros tienen una varianza que es todavía la semilla del BFGS.

    (BUG-0027) La degeneración puede ser PARCIAL, y ése es el caso peligroso.
    Con `niter = 0` no se actualiza nada y toda la covarianza es la semilla; pero
    con `niter = 1` el BFGS actualiza UNA dirección y deja el resto intacto —
    medido sobre un modelo de 7 parámetros: cinco varianzas seguían en la semilla
    y dos se habían movido. Unos errores típicos válidos y otros no, sin nada que
    los distinga en la salida.
    """
    if result is None:
        return []
    semilla = bfgs_seed_var(result)
    cov = getattr(result, "cov_matrix", None)
    if cov is None or semilla is None:
        return []
    cov = np.asarray(cov, dtype=float)
    if cov.ndim == 1:
        k = int(round(cov.size ** 0.5))
        if k * k == cov.size:
            cov = cov.reshape(k, k)
        else:
            return []
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        return []
    d = np.diag(cov)
    return [i for i in range(len(d)) if abs(d[i] - semilla) <= 1e-5 * semilla]


# Distancia relativa a la semilla por debajo de la cual una varianza es
# SOSPECHOSA aunque no sea la semilla exacta. Ver `near_seed_variance_indices`.
BANDA_CASI_SEMILLA = 0.25

AVISO_COV_CASI_SEMILLA = (
    "están MUY CERCA de la semilla del BFGS (2/n), lo que sugiere direcciones "
    "que el optimizador apenas movió. No es prueba de que sean inválidos —una "
    "varianza puede valer eso legítimamente— pero conviene contrastarlos antes "
    "de apoyar una decisión en ellos: el `.out` del modelo trae la covarianza "
    "completa, y para una media sin ARMA el error típico correcto es la "
    "desviación típica residual dividida por √n."
)


def near_seed_variance_indices(result, tol: float = BANDA_CASI_SEMILLA) -> list[int]:
    """Varianzas SOSPECHOSAMENTE cerca de la semilla del BFGS, sin ser la semilla.

    (BUG-0041) `degenerate_variance_indices` compara con tolerancia `1e-5`, o
    sea igualdad: caza la dirección que el optimizador no tocó NUNCA (`niter=0`)
    y nada más. Pero una dirección que se movió un 7% tampoco lleva información
    del hessiano, y no dispara ningún aviso.

    Medido sobre ITCER de la réplica del TFM, un modelo de dos parámetros con
    `niter=2`: la varianza de μ salió 0.022473 contra una semilla de 0.024096 —
    el 93% de ella. El error típico publicado fue 0.1499 cuando el correcto,
    para un modelo sin ARMA, es la desviación típica residual sobre √n = 0.2864.
    **La mitad de lo que debía, sin ningún aviso.** El mismo modelo con `niter=5`
    dio 0.2687, que sí coincide.

    Esto es una SOSPECHA y no un veredicto, y por eso va aparte: una varianza
    puede valer 2/n legítimamente, y marcarla como inválida sería un falso
    positivo caro. Lo que se publica es la distancia relativa, para que quien lea
    decida.

    Devuelve los índices cuya varianza está dentro de `tol` (relativo) de la
    semilla **excluyendo** las que ya son la semilla exacta — ésas las reporta
    `degenerate_variance_indices` con un veredicto más fuerte.
    """
    if result is None:
        return []
    semilla = bfgs_seed_var(result)
    cov = getattr(result, "cov_matrix", None)
    if cov is None or semilla is None or semilla <= 0:
        return []
    cov = np.asarray(cov, dtype=float)
    if cov.ndim == 1:
        k = int(round(cov.size ** 0.5))
        if k * k != cov.size:
            return []
        cov = cov.reshape(k, k)
    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        return []
    exactas = set(degenerate_variance_indices(result))
    d = np.diag(cov)
    return [i for i in range(len(d))
            if i not in exactas and abs(d[i] - semilla) <= tol * semilla]


def near_seed_distances(result) -> dict[int, float]:
    """Distancia relativa a la semilla de cada varianza sospechosa (BUG-0041)."""
    semilla = bfgs_seed_var(result)
    if semilla is None or semilla <= 0:
        return {}
    cov = np.asarray(getattr(result, "cov_matrix", None), dtype=float)
    if cov.ndim == 1:
        k = int(round(cov.size ** 0.5))
        cov = cov.reshape(k, k)
    d = np.diag(cov)
    return {i: (d[i] - semilla) / semilla for i in near_seed_variance_indices(result)}


def covariance_is_degenerate(result) -> bool:
    """¿Hay errores típicos que son la semilla del BFGS y no el hessiano? (BUG-0027)

    `fue` inicializa la inversa del hessiano como `c·I` y la actualiza en cada
    iteración. Lo que no se actualiza vuelve como covarianza siendo la semilla.
    Y el resultado se declara `converged=True`, así que nada avisa.

    Dos formas, y la segunda se escapaba al primer arreglo:

    * **Total** — `niter = 0`: no se actualizó nada. Ocurre al arrancar
      EXACTAMENTE en el óptimo, que es lo que un `.pre` es por diseño; y también
      en el modelo más simple de todos, media sola sin ARMA, porque su estimador
      máximo-verosímil es la media muestral y el optimizador no tiene nada que
      hacer. Es decir: en la línea base de cualquier análisis.
    * **Parcial** — alguna varianza sigue en `BFGS_SEED_VAR`: el optimizador
      actualizó unas direcciones y otras no.

    El primer arreglo exigía diagonal constante y fuera de la diagonal nula, y
    además excluía `npar = 1` para no marcar un caso indistinguible. Las dos
    decisiones estaban mal: con `npar = 1` el modelo de media sola cae de lleno
    aquí, y la degeneración parcial no tiene la diagonal constante.
    """
    if result is None:
        return False
    if int(getattr(result, "niter", -1) or 0) == 0 and \
            getattr(result, "cov_matrix", None) is not None:
        return True
    return bool(degenerate_variance_indices(result))


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
    #
    # BUG-0075. El conjunto anterior era `[s//2, s, 2s, 3s]`, y tenía dos
    # problemas que se pagaron juntos.
    #
    # `s//2` es el retardo 2 en trimestral: tras restar los parámetros ARMA
    # quedan UNO o CERO grados de libertad. Como el veredicto de ruido blanco
    # se toma con `min(q_pvalues)`, ese punto —el más frágil de todos— decidía
    # casi siempre.
    #
    # Y el conjunto se paraba en `3s`, sin llegar al punto de decisión de la
    # convención, que para datos trimestrales y mensuales es **f·3+3** — 15 y
    # 39— y para series anuales o sin estacionalidad, 10.
    #
    # El motor tampoco estaba de acuerdo: el `.out` de `fue` reporta el
    # Ljung-Box en {4, 8, 12, 15} para un trimestral, con sus DF corregidos. La
    # diagnosis de Python y el motor evaluaban la adecuación en sitios
    # distintos.
    #
    # Lo que costó, medido sobre PGAS: dos especificaciones rivales de la misma
    # intervención daban Q(2) de 0,0655 y 0,0392 —la simplificada se descartaba
    # por inadecuada— mientras que a la convención dan 0,3599 y **0,4421**: la
    # simplificada es la mejor de las dos. El veredicto se invertía.
    #
    # Es un Portmanteau y el número de retardos es hasta cierto punto
    # arbitrario; mirarlos todos siempre es bueno. Lo que no puede ser es que
    # el punto donde se DECIDE tenga un grado de libertad.
    # Nota: `_default_lags_fug` devuelve `3*(freq+1)` para series
    # estacionales, que ES f·3+3. La longitud del correlograma del motor ya era
    # la convención; lo único que faltaba era EVALUAR ahí.
    if s > 1:
        q_check_lags = [s, 2 * s, 3 * s, 3 * s + 3]
    else:
        # Sin estacionalidad, 9. Y no es una adaptación a lo que hay: es que
        # `_default_lags_fug` devuelve 9 para freq=1 porque es lo que hace
        # `diagnose.c` de `fug`, así que **el 9 ES la convención del motor**.
        # Una décima de retardo arriba o abajo no cambia nada en un Portmanteau;
        # lo que importa es que Python y el motor decidan en el mismo sitio.
        q_check_lags = [5, 9]
    q_check_lags = sorted({l for l in q_check_lags if 1 <= l <= lags})
    if not q_check_lags:                       # serie muy corta
        q_check_lags = [max(1, min(lags, npar + 1))]

    lb = ljung_box(r, q_check_lags, df_correction=npar)
    q_stats   = [float(x) for x in lb['statistic']]
    q_pvalues = [float(x) for x in lb['pvalue']]

    # --- Jarque-Bera normality ---
    jb = jarque_bera(r)
    jb_stat   = float(jb.statistic)
    jb_pvalue = float(jb.pvalue)
    skew      = float(sp_stats.skew(r))
    kurt      = float(sp_stats.kurtosis(r))   # excess kurtosis (Fisher)

    # --- Residual mean against zero -----------------------------------------
    # It is computed here anyway, to centre the z-scores. What was missing is
    # CONTRASTING it: t = mean / (sd/sqrt(n)). With a free mu the residual mean
    # is ~0 by construction, so a large t is the signature of a mean that is
    # NOT in the model -- the drift of a trending series, sitting in the
    # residuals. See the `centred` property.
    r_mean = r.mean()
    r_std  = r.std(ddof=1) if len(r) > 1 else 1.0
    mean_t = (float(r_mean) / (r_std / np.sqrt(len(r)))) if (r_std > 0 and len(r) > 1) else 0.0

    # --- Extreme residuals (compare standardized residuals against threshold) ---
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
        mean=float(r_mean),
        mean_t=float(mean_t),
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
    """Treadway-Jenkins diagnostic panel (fue layout).

    When *model* is fitted, delegates to fue.plots.plot_model_diagnostics which
    produces the canonical layout: residuals time-series (left, full height) +
    stacked ACF/PACF (right).  This is the basic diagnostic module; the
    histogram is a separate optional figure (see plot_diagnosis_histogram).
    """
    if not _FUE_PLOTS:
        raise ImportError("fue.plots is not available; diagnosis graphics require the fue package with plots support")

    if model is not None and getattr(model, "_result", None) is not None:
        from fue.plots import plot_model_diagnostics
        fig, _ = plot_model_diagnostics(model)
        return fig

    # Fallback when no fitted model object is available (should not happen in
    # normal ART usage, but kept for defensive completeness).
    r    = result.residuals
    n    = result.nobs
    lags = len(result.acf)
    band = 1.96 / math.sqrt(n)
    s    = 1
    if model is not None and model.series is not None:
        s = model.series.freq

    fig, axes = plt.subplots(2, 2, figsize=(13, 7))
    fig.suptitle(f"Diagnosis: {result.label}", fontweight='bold', fontsize=13)

    ax = axes[0, 0]
    ax.axhline(0, color='black', lw=0.8)
    ax.axhline(+2, color='red', lw=0.6, ls='--')
    ax.axhline(-2, color='red', lw=0.6, ls='--')
    ax.plot(np.arange(n), r, color='#333333', lw=0.8)
    for obs, z in result.extreme:
        ax.scatter(obs - 1, z, color='red', s=20, zorder=5)
    ax.set_title("Residuals"); _tj_spines(ax)

    ax = axes[0, 1]
    (osm, osr), (slope, intercept, _) = sp_stats.probplot(r, dist='norm')
    ax.plot(osm, osr, 'o', ms=2.5, color='#333333', alpha=0.7)
    ax.plot([osm[0], osm[-1]],
            [slope * osm[0] + intercept, slope * osm[-1] + intercept],
            color='red', lw=1.2)
    ax.set_title("QQ Normal"); _tj_spines(ax)

    lag_x = np.arange(1, lags + 1)
    cmax  = max(float(np.abs(result.acf).max()),
                float(np.abs(result.pacf).max())) * 1.15 + 0.05
    _draw_acf_panel(axes[1, 0], lag_x, result.acf,  band=band,
                    cmax=cmax, freq=s, lags=lags, label="ACF")
    _draw_acf_panel(axes[1, 1], lag_x, result.pacf, band=band,
                    cmax=cmax, freq=s, lags=lags, label="PACF")

    fig.tight_layout()
    return fig


def plot_diagnosis_histogram(model) -> plt.Figure:
    """Residuals histogram with normal overlay (optional complement to
    plot_diagnosis).  Delegates to fue.plots.plot_model_diagnostics fig2."""
    if not _FUE_PLOTS:
        raise ImportError("fue.plots is not available; diagnosis graphics require the fue package with plots support")
    from fue.plots import plot_model_diagnostics
    _, fig_hist = plot_model_diagnostics(model)
    return fig_hist


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


# ---------------------------------------------------------------------------
# Admisibilidad de los operadores estimados (BUG-0062)
# ---------------------------------------------------------------------------

def _raices_factor(coefs) -> list[float]:
    """Módulos de las raíces de `(1 − c₁B − c₂B² − … − c_pBᵖ)`.

    Es la convención de `fue` para AR y MA por igual, comprobada contra la
    ecuación que imprime ART: `ar=[0.7647, −0.2640]` se renderiza
    `(1 − 0.7647·B + 0.2640·B²)`, y `ma=[−0.7879, −0.2760]` como
    `(1 + 0.7879·B + 0.2760·B²)`.

    Para un factor ESTACIONAL el polinomio va en `u = Bˢ`; comprobar |u|>1 basta,
    porque |B| = |u|^(1/s) y la desigualdad se conserva.
    """
    import numpy as np
    c = [float(x) for x in (coefs or [])]
    if not c:
        return []
    # np.roots quiere potencias decrecientes: [−c_p, …, −c₁, 1]
    poly = [-x for x in reversed(c)] + [1.0]
    try:
        r = np.roots(poly)
    except Exception:
        return []
    return [float(abs(z)) for z in r]


def admissibility_problems(model, tol: float = 1e-6) -> list[tuple[str, float]]:
    """Operadores cuyas raíces caen DENTRO del círculo unidad.

    Un AR con raíz dentro no es estacionario; un MA con raíz dentro no es
    invertible. Las dos cosas invalidan la lectura del modelo, y ninguna se
    anunciaba: `fue` declara «Check for invertibility: constrained search» en la
    cabecera del `.out` y aun así devolvió Θ₄ = −2.0989 tras 45 iteraciones —
    módulo de la raíz 0.831 — presentado como cualquier otro resultado. Sólo la
    diagnosis rota (Q) delataba que algo iba mal.

    Devuelve [(etiqueta, módulo mínimo de raíz, "dentro"|"frontera"), …], vacío
    si todo es admisible.

    **`ar_f`/`ma_f` quedan FUERA a propósito.** El testigo del MEG vive ahí y
    apunta deliberadamente a la frontera (λ → −1): marcarlo sería avisar de lo
    que el contraste está buscando.
    """
    # El módulo se devuelve SIEMPRE en B, para que se compare con el mismo
    # círculo unidad en los cuatro casos. En un factor estacional el polinomio va
    # en u = Bˢ, así que |B| = |u|^(1/s): sobre Θ₄ = −2.0989 eso es |u| = 0.4764
    # y |B| = 0.831 — las dos por dentro, pero sólo la segunda es la que el
    # analista compara con 1 al leer la ecuación en B.
    s_freq = getattr(getattr(model, "series", None), "freq", 1) or 1
    problemas = []
    for attr, etq, estacional in (("ar", "AR", False), ("ma", "MA", False),
                                  ("ar_s", "AR estacional", True),
                                  ("ma_s", "MA estacional", True)):
        factores = getattr(model, attr, None) or []
        for k, fac in enumerate(factores):
            mods = _raices_factor(fac)
            if not mods:
                continue
            m = min(mods)
            if estacional and s_freq > 1:
                m = m ** (1.0 / s_freq)
            if m <= 1.0 + tol:
                sufijo = f" #{k + 1}" if len(factores) > 1 else ""
                # DENTRO y EN LA FRONTERA no significan lo mismo y no se
                # arreglan igual. Barridos los 214 modelos de la réplica salen
                # los dos casos, uno de cada:
                #   Θ₄ = −2.0989  →  |raíz| = 0.831, DENTRO: no invertible.
                #   MA(4) con dos raíces de módulo 1.000000 y d=1  →  FRONTERA:
                #     el MA ha absorbido la diferencia, que es la firma de la
                #     sobrediferenciación, no un operador inutilizable.
                donde = "frontera" if abs(m - 1.0) <= 1e-4 else "dentro"
                problemas.append((f"{etq}{sufijo}", m, donde))
    return problemas
