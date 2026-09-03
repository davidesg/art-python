"""
Intervention detection, testing, and simplification (Phase 4 of Box-Jenkins-Treadway).

Phase 4a — Anomaly warnings
    diagnose_interventions: identify extreme residuals and their effect on ACF/JB/Q.

Phase 4b — Intervention hypothesis testing
    test_intervention    : t-test H₀: ω=0 per free omega parameter.
                           For FLT with delta: Wald H₀: g=0, g=α·ω, V(g)=α·COV·αᵀ.
    simplify_interventions: test all interventions, flag non-significant ones.

Phase 4c — Automatic functional form detection  (FUTURO)
    Discriminate pulse/step/ramp via LR test on re-estimations.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from fue.diagnostics import acf as _fue_acf

from .identification import _default_lags_fug


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class OutlierWarning:
    """
    One extreme residual with its distortion profile.

    Attributes
    ----------
    obs_index : int
        0-based index in the residual array.
    date : str
        Formatted date string (e.g. "03/1994" for monthly, "Q1/1994" for quarterly).
    z : float
        Standardised residual value (the fue innovations â_t / h_t, re-centred and
        rescaled to unit sample variance).
    variance_fraction : float
        z_t² / Σ z²: fraction of total squared residuals explained by this observation.
        Large values (> 0.15) indicate the observation is compressing all ACF/PACF
        coefficients globally.
    acf_lags_affected : list[int]
        Lags j for which the direct pair-contribution of this observation to ACF(j)
        exceeds the reporting threshold (see diagnose_interventions).
    """
    obs_index: int
    date: str
    z: float
    variance_fraction: float
    acf_lags_affected: list[int]


@dataclass
class InterventionDiagnosis:
    """
    Result of diagnose_interventions.

    Attributes
    ----------
    outliers : list[OutlierWarning]
        Extreme residuals, sorted by |z| descending.
    jb_unreliable : bool
        True if at least one extreme residual was found; Jarque-Bera is not
        robust to isolated large innovations.
    q_unreliable : bool
        True if at least one extreme residual was found; Ljung-Box Q is not
        robust to isolated large innovations.
    threshold : float
        The |z| threshold used (default 3.5).
    """
    outliers: list[OutlierWarning]
    jb_unreliable: bool
    q_unreliable: bool
    threshold: float

    @property
    def has_outliers(self) -> bool:
        return len(self.outliers) > 0

    def summary(self) -> str:
        lines = [f"Intervention diagnosis  (threshold |z| > {self.threshold:.1f})"]
        if not self.outliers:
            lines.append("  No extreme residuals detected.")
            return "\n".join(lines)

        lines.append(f"  {len(self.outliers)} extreme residual(s) detected:")
        for w in self.outliers:
            pct = 100.0 * w.variance_fraction
            global_note = "  ** compresses all ACF/PACF **" if pct > 15.0 else ""
            lags_str = (
                "  ACF lags: " + ", ".join(str(j) for j in w.acf_lags_affected)
                if w.acf_lags_affected else ""
            )
            lines.append(
                f"    {w.date:>12s}  z = {w.z:+.3f}  "
                f"var% = {pct:4.1f}%{global_note}{lags_str}"
            )
        if self.jb_unreliable:
            lines.append(
                "  WARNING: Jarque-Bera is not robust to isolated anomalies "
                "— interpret with caution."
            )
        if self.q_unreliable:
            lines.append(
                "  WARNING: Ljung-Box Q is not robust to isolated anomalies "
                "— interpret with caution."
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def diagnose_interventions(
    model,
    threshold: float = 3.5,
    acf_contrib_threshold: float = 0.05,
) -> InterventionDiagnosis:
    """
    Detect extreme residuals and report their distortion on ACF/PACF, JB, and Q.

    Parameters
    ----------
    model : fue.Model, already fitted (.fit() called)
    threshold : float
        |z| threshold for flagging an observation as extreme (default 3.5).
    acf_contrib_threshold : float
        Minimum absolute pair-contribution to ACF(j) for a lag to be listed in
        OutlierWarning.acf_lags_affected (default 0.05, i.e. 5 % of the ACF range).

    Returns
    -------
    InterventionDiagnosis

    Raises
    ------
    RuntimeError
        If model has not been fitted.

    Notes
    -----
    The fue residuals (â_t / h_t) are approximately N(0, 1); we re-standardise
    using the sample mean and std so that z reflects the standardised innovation
    relative to the sample distribution.  The pair-contribution formula for
    ACF(j) is  c(i, i+j) = (res[i] − μ)(res[i+j] − μ) / (n · s²).
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    res = np.asarray(model._result.residuals, dtype=float)
    n   = len(res)
    s   = model.series.freq

    mu  = float(res.mean())
    std = float(res.std(ddof=0))
    if std < 1e-20:
        return InterventionDiagnosis(
            outliers=[], jb_unreliable=False, q_unreliable=False, threshold=threshold
        )

    z      = (res - mu) / std
    z2_sum = float((z ** 2).sum())

    # Number of observations skipped at the start of the original series
    # (due to differencing and AR initialisation).
    n_original = len(model.series.data)
    ornsop     = n_original - n

    lags    = _default_lags_fug(n, s)
    acf_arr = np.asarray(_fue_acf(res, lags=lags), dtype=float)

    outliers = []
    for t in range(n):
        if abs(z[t]) <= threshold:
            continue

        # Date of this residual in the original series
        year, period = model.series._obs_to_date(ornsop + t + 1)
        date_str = _format_date(year, period, s)

        var_frac = float(z[t] ** 2 / z2_sum) if z2_sum > 0 else 0.0

        # Pair-contributions of observation t to ACF(j) for j = 1..lags
        affected = []
        var_res  = float(res.var(ddof=0))   # sample variance (ddof=0)
        denom    = n * var_res
        for j in range(1, lags + 1):
            contrib = 0.0
            if t + j < n:
                contrib += (res[t] - mu) * (res[t + j] - mu) / denom
            if t - j >= 0:
                contrib += (res[t - j] - mu) * (res[t] - mu) / denom
            if abs(contrib) >= acf_contrib_threshold:
                affected.append(j)

        outliers.append(OutlierWarning(
            obs_index=t,
            date=date_str,
            z=float(z[t]),
            variance_fraction=var_frac,
            acf_lags_affected=affected,
        ))

    outliers.sort(key=lambda w: abs(w.z), reverse=True)
    has = len(outliers) > 0

    return InterventionDiagnosis(
        outliers=outliers,
        jb_unreliable=has,
        q_unreliable=has,
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 4b — Intervention hypothesis testing
# ---------------------------------------------------------------------------

@dataclass
class InterventionTestResult:
    """
    Hypothesis test result for a single intervention's free parameters.

    For a simple intervention (omega=[ω₀], no delta):
        H₀: ω₀ = 0  via t = ω₀/SE, df = n_obs - npar.

    For a multi-omega intervention (an FLT, with or without delta):
        Individual t-tests per free omega, plus a joint Wald test of
        ZERO LONG-RUN GAIN,
            H₀: ω(1) = 0,   ω(1) = ω₀ − ω₁ − ⋯ − ω_s,
            g = α·ω + c,  α = (1, −1, …, −1),  V(g) = α·COV(ω)·αᵀ,
        χ²(1). `c` carries the contribution of any FIXED omega.

    Why testing the NUMERATOR is testing the GAIN (BUG-0071)
    --------------------------------------------------------
    The gain is ν(1) = ω(1)/δ(1). For H₀: ν(1) = 0 the denominator is
    irrelevant: a ratio is zero exactly when its numerator is, provided
    δ(1) ≠ 0. So the zero-gain test needs NO delta method — it is an exact
    linear Wald on ω. The delta method is only needed for an interval on the
    gain, or to test a gain equal to something other than zero.

    δ(1) → 0 is the inadmissible case (unbounded gain); `gain` comes back NaN
    and `admissibility_problems` in diagnosis.py is what speaks to it.
    """
    itv_index: int              # 0-based index into model.interventions
    itv_type: str               # 'pulse', 'step', 'cos', 'sin', 'alter', …
    itv_at: int                 # 0-based obs index (0 for cos/sin/alter)
    harmonic: float | None      # for cos/sin only
    omega: list[float]          # estimated free omega coefs (in order)
    omega_se: list[float]       # standard errors
    omega_t: list[float]        # individual t-statistics
    omega_p: list[float]        # individual 2-sided p-values
    wald_stat: float | None     # Wald χ²(1) for H₀: ω(1)=0; None if k<2
    wald_p: float | None        # p-value of that Wald test; None if k<2
    df: int                     # degrees of freedom (n_obs - npar) for t-tests
    significant: bool           # True if ANY free omega param is significant at 5%
    omega_1: float | None = None   # ω(1) = ω₀ − ω₁ − ⋯ − ω_s (the numerator)
    # Error típico de ω(1). Se publica en vez de dejar que el consumidor lo
    # despeje del Wald como |g|/√χ², que revienta justo cuando la ganancia es
    # ≈0 — que es el caso interesante.
    se_omega_1: float | None = None
    gain: float | None = None      # ν(1) = ω(1)/δ(1); NaN if δ(1) ≈ 0

    def summary(self, alpha: float = 0.05) -> str:
        t = self.itv_type
        if t in ("cos", "sin") and self.harmonic is not None:
            label = f"{t}(h={self.harmonic:.0f})"
        elif t in ("pulse", "impulse", "step", "ramp"):
            label = f"{t}[obs {self.itv_at + 1}]"
        else:
            label = t
        sig = "✓" if self.significant else "✗ no significativa"
        lines = [f"  [{self.itv_index:2d}] {label:<22} {sig}"]
        for i, (v, se, tval, pv) in enumerate(
                zip(self.omega, self.omega_se, self.omega_t, self.omega_p)):
            star = "**" if pv < alpha else "  "
            lines.append(f"       ω[{i}]={v:+.4f}  SE={se:.4f}  t={tval:+.3f}  p={pv:.4f} {star}")
        if self.wald_stat is not None:
            wstar = "**" if (self.wald_p or 1) < alpha else "  "
            # BUG-0073: el rótulo decía χ²(k) mientras el cálculo usaba df=1.
            # Es UNA restricción lineal —ω(1)=0—, así que es χ²(1), y decir k
            # invitaba a leer el p-valor contra la tabla equivocada.
            lines.append(f"       ganancia ω(1)={self.omega_1:+.4f}   "
                         f"Wald χ²(1)={self.wald_stat:.3f}  p={self.wald_p:.4f} {wstar}")
            lines.append(f"       H₀: ganancia nula ⇒ efecto TRANSITORIO"
                         + ("  (no se rechaza)" if (self.wald_p or 1) >= alpha
                            else "  (se RECHAZA: efecto permanente)"))
        return "\n".join(lines)


def _intervention_param_start(model, itv_idx: int) -> int:
    """
    Return the index in model._result.params where intervention itv_idx's
    free omega parameters begin.

    Parameter ordering (from fue/report.py):
        for each intervention i:
            free omega[i] params
            free delta[i] params
        then: AR, AR_s, MA, MA_s, AR_f, MA_f, mu
    """
    idx = 0
    for i, itv in enumerate(model.interventions or []):
        if i == itv_idx:
            return idx
        om  = itv.omega      or []
        omf = itv.omega_free or [True] * len(om)
        idx += sum(1 for f in omf if f)
        dl  = itv.delta      or []
        dlf = itv.delta_free or [True] * len(dl)
        idx += sum(1 for f in dlf if f)
    raise IndexError(f"itv_idx={itv_idx} out of range ({len(model.interventions)} interventions)")


def test_intervention(model, itv_idx: int,
                      alpha: float = 0.05) -> InterventionTestResult:
    """
    Test H₀: ω = 0 for all free omega parameters of intervention itv_idx.

    For interventions with no delta (simple pulse/step/cos/sin), each free
    omega is tested individually with a t-statistic using df = n_obs − npar.

    For ANY intervention with more than one free omega — with or without a
    delta denominator — an additional joint Wald test of ZERO LONG-RUN GAIN:
        H₀: ω(1) = ω₀ − ω₁ − ⋯ − ω_s = 0,   α = (1, −1, …, −1),   χ²(1).

    That is the test the episode node rests on: N consecutive level steps with
    zero gain are N−1 level impulses, i.e. a TRANSITORY episode of length N−1
    rather than a permanent shift (docs/DISENO-nodo-intervencion.md §2.2).

    Parameters
    ----------
    model   : fue.Model, fitted
    itv_idx : 0-based index into model.interventions
    alpha   : significance level for the ``significant`` flag (default 0.05)

    Returns
    -------
    InterventionTestResult
    """
    import scipy.stats as sp_stats

    if model._result is None:
        raise ValueError("Model is not fitted — call model.fit() first.")
    r      = model._result
    # BUG-0027: con la semilla EXACTAMENTE en el óptimo, `niter=0` y la covarianza
    # que vuelve es la semilla del BFGS (c·I). Los `t` que salen de ahí son
    # ficción, y creíble. Un contraste sobre una covarianza que no existe no es un
    # contraste: se para aquí en vez de publicar el número.
    from art.diagnosis import covariance_is_degenerate, AVISO_COV_DEGENERADA
    if covariance_is_degenerate(r):
        raise ValueError("BUG-0027: " + AVISO_COV_DEGENERADA)
    params = np.asarray(r.params)
    cov    = np.asarray(r.cov_matrix)
    n_obs  = model.series.nobs if model.series else len(r.residuals)
    npar   = int(r.npar)
    df     = max(n_obs - npar, 1)

    itvs = model.interventions or []
    if itv_idx < 0 or itv_idx >= len(itvs):
        raise IndexError(f"itv_idx={itv_idx} out of range (0..{len(itvs)-1})")

    itv  = itvs[itv_idx]
    start = _intervention_param_start(model, itv_idx)

    om  = list(itv.omega      or [])
    omf = list(itv.omega_free or [True] * len(om))
    dl  = list(itv.delta      or [])
    dlf = list(itv.delta_free or [True] * len(dl))

    # Collect free omega indices and values.
    # `free_om_pos` keeps the position each free omega occupies in the FULL
    # omega vector, which is what fixes the sign in α: ω(1) weights ω₀ by +1
    # and every later lag by −1, so the sign follows the POSITION and not the
    # rank among the free ones. Without this, fixing ω₀ silently shifts every
    # sign by one slot.
    free_om_idx = []   # global param indices for free omega coefs
    free_om_val = []
    free_om_pos = []   # position within the full omega vector
    fixed_om_1  = 0.0  # contribution of the FIXED omegas to ω(1)
    local = start
    for pos, (v, f) in enumerate(zip(om, omf)):
        signo = 1.0 if pos == 0 else -1.0
        if f:
            free_om_idx.append(local)
            free_om_val.append(float(params[local]))
            free_om_pos.append(pos)
            local += 1
        else:
            fixed_om_1 += signo * float(v)

    omega_est  = [float(params[i]) for i in free_om_idx]
    omega_se   = [float(np.sqrt(max(cov[i, i], 0.0))) for i in free_om_idx]
    omega_t    = [v / s if s > 0 else float("nan")
                  for v, s in zip(omega_est, omega_se)]
    omega_p    = [float(2 * sp_stats.t.sf(abs(t), df=df))
                  for t in omega_t]

    # ── Joint Wald: H₀ zero long-run gain (BUG-0071, BUG-0072) ───────────
    # α = (1, −1, …, −1) because fue stores the numerator as
    #     ω(B) = ω₀ − ω₁B − ⋯ − ω_sB^s
    # so ω(1) SUBTRACTS every lag ≥ 1. Writing this contrast as a plain sum
    # returns a plausible and systematically wrong number — the same sign
    # convention that produced BUG-0066.
    #
    # No gate on delta (BUG-0072): the test is meaningful for ANY multi-omega
    # intervention, and the case the episode node needs — N level steps with
    # NO denominator — is precisely the one the old gate excluded.
    wald_stat = None
    wald_p    = None
    omega_1   = None
    gain      = None
    se_om1    = None
    k = len(free_om_idx)

    if om:
        alpha_vec = np.array([1.0 if p == 0 else -1.0 for p in free_om_pos])
        g = float(alpha_vec @ np.array(omega_est)) + fixed_om_1
        omega_1 = g
        # δ(1) = 1 − δ₁ − ⋯ − δ_r. At zero the gain is unbounded and the model
        # is inadmissible; the gain is not reported rather than reported wrong.
        delta_1 = 1.0 - sum(float(v) for v in dl)
        gain = g / delta_1 if abs(delta_1) > 1e-10 else float("nan")

        if k > 1:
            sub_cov = cov[np.ix_(free_om_idx, free_om_idx)]
            Vg = float(alpha_vec @ sub_cov @ alpha_vec)
            if Vg > 0:
                se_om1 = float(np.sqrt(Vg))
                wald_stat = g ** 2 / Vg      # χ²(1) under H₀: ω(1)=0
                wald_p    = float(sp_stats.chi2.sf(wald_stat, df=1))

    significant = any(pv < alpha for pv in omega_p)

    return InterventionTestResult(
        itv_index  = itv_idx,
        itv_type   = itv.type,
        itv_at     = int(itv.at),
        harmonic   = float(itv.harmonic) if hasattr(itv, "harmonic") else None,
        omega      = omega_est,
        omega_se   = omega_se,
        omega_t    = omega_t,
        omega_p    = omega_p,
        wald_stat  = wald_stat,
        wald_p     = wald_p,
        omega_1    = omega_1,
        se_omega_1 = se_om1,
        gain       = gain,
        df         = df,
        significant = significant,
    )


def simplify_interventions(model,
                            alpha: float = 0.05,
                            skip_types: tuple[str, ...] = ("cos", "sin", "alter"),
                            ) -> list[InterventionTestResult]:
    """
    Test all model interventions and identify which are non-significant.

    Parameters
    ----------
    model      : fue.Model, fitted
    alpha      : significance level (default 0.05)
    skip_types : intervention types to skip (default: harmonics + alter,
                 which are structural and should not be removed automatically)

    Returns
    -------
    list of InterventionTestResult, one per tested intervention (skip_types excluded).
    Non-significant ones have ``.significant == False``.

    Example
    -------
    results = simplify_interventions(model)
    to_remove = [r.itv_index for r in results if not r.significant]
    """
    results = []
    for i, itv in enumerate(model.interventions or []):
        if itv.type in skip_types:
            continue
        try:
            results.append(test_intervention(model, i, alpha=alpha))
        except Exception:
            pass
    return results


def simplify_summary(results: list[InterventionTestResult],
                     alpha: float = 0.05) -> str:
    """
    Format a Markdown summary of simplify_interventions output.

    Shows significant interventions first, then non-significant ones
    (candidates for removal).
    """
    sig   = [r for r in results if     r.significant]
    nosig = [r for r in results if not r.significant]

    lines = [
        f"## Contraste de intervenciones (α={alpha:.2f})",
        "",
        f"Significativas ({len(sig)}):  Prescindibles ({len(nosig)}):",
        "",
    ]

    if sig:
        lines.append("### Significativas — mantener")
        for r in sig:
            lines.append(r.summary(alpha=alpha))

    if nosig:
        lines.append("\n### Prescindibles — considerar eliminar")
        for r in nosig:
            lines.append(r.summary(alpha=alpha))

    if nosig:
        idx_str = ", ".join(str(r.itv_index) for r in nosig)
        lines += [
            "",
            f"**Sugerencia:** elimina las intervenciones [{idx_str}] y re-estima.",
            "Si el modelo mejora (AIC/BIC menores o diagnosis más limpia), confirma la simplificación.",
        ]
    else:
        lines.append("\n*Todas las intervenciones son significativas — no hay simplificación posible.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_date(year: int, period: int, freq: int) -> str:
    if freq == 1:
        return str(year)
    elif freq == 4:
        return f"Q{period}/{year}"
    elif freq == 12:
        return f"{period:02d}/{year}"
    else:
        return f"{period}/{year}"


# ---------------------------------------------------------------------------
# La regla de Treadway: ¿funcionó la intervención?
# ---------------------------------------------------------------------------
#
# Dos reglas de la escuela, y las dos salen de la misma ecuación:
#
#   1. Si intervienes en una fecha, NO puedes tener un anómalo de vecino, ni
#      antes ni después. Un vecino anómalo es evidencia de que la
#      REPRESENTACIÓN elegida es errónea.
#   2. Que la intervención haya funcionado se ve en que los residuos EN LAS
#      FECHAS de intervención están en la media de los residuos, que es cero.
#
# No bloquea nada: es diagnosis.
#
# ── Por qué, con la matemática ──────────────────────────────────────────────
#
# El modelo es  z_t = ν(B)ξ_t + N_t,  con N_t el ruido ARIMA y a_t sus
# innovaciones. Sea π(B) = θ(B)⁻¹φ(B)∇^d el filtro que blanquea, de modo que
#
#     a_t = π(B)·[ z_t − ν(B)ξ_t ]
#
# Con ν(B) = ω(B)/δ(B) y la convención de fue ω(B) = ω₀ − ω₁B − ⋯, la derivada
# respecto de cada ω_j da el REGRESOR FILTRADO
#
#     x_t^(j) = π(B)·[ B^j / δ(B) ]·ξ_t
#
# y la condición de primer orden de la verosimilitud, ∂ℓ/∂ω_j = 0, es
#
#     Σ_t  a_t · x_t^(j) = 0     para todo j libre
#
# Es decir: **los residuos quedan ORTOGONALES a cada regresor filtrado de la
# intervención.** Son las ecuaciones normales de una regresión, y lo son porque
# con ARMA y δ fijos la intervención entra LINEALMENTE.
#
# **De ahí la regla 2.** En el caso más simple —un impulso puro, s=0, r=0— el
# regresor es x_t = π_{t−T}, y la condición queda
#
#     a_T = − Σ_{k≥1} π_k · a_{T+k}
#
# Sin ARMA y con d=0 se tiene π(B)=1, luego π_k = 0 para k≥1 y **a_T = 0
# EXACTAMENTE**: un ω libre en una fecha absorbe esa observación entera, igual
# que una variable ficticia en regresión. Con ARMA, a_T es una combinación
# pequeña de los residuos siguientes — de ahí que la regla se enuncie como
# «están en la media» y no como «son cero»: es exacta sin filtro y aproximada
# con él, y el filtro dice cuánto.
#
# **Y de ahí la regla 1.** La condición de primer orden sólo obliga a
# ortogonalidad frente a los regresores QUE SE HAN AJUSTADO. Si el suceso real
# ocupa T y T+1 y sólo se ajusta un impulso en T, el ω absorbe T y la parte de
# T+1 no tiene dónde ir: cae entera en a_{T+1}. El vecino anómalo ES la parte no
# modelizada del mismo suceso.
#
# Simétricamente, si se coloca la intervención en T−1 cuando el suceso está en
# T, el ω absorbe la fecha equivocada y queda un residuo grande en T — que es
# BUG-0030, donde además la verosimilitud casi no distingue (Δ logL = 0,03).
#
# Así que un vecino anómalo tiene exactamente dos lecturas, y las dos son
# errores de representación: **la forma se queda corta** (hay episodio) o **la
# fecha está desplazada**.

@dataclass
class InterventionFitCheck:
    """Si una intervención hizo su trabajo, según la regla de Treadway."""

    itv_index: int
    itv_type: str
    at_0based: int                       # índice en la SERIE
    fechas: list[int]                    # obs 1-based en los RESIDUOS
    z_en_fechas: list[float]
    z_antes: float | None
    z_despues: float | None
    umbral_vecino: float
    umbral_absorcion: float
    # El residuo CRUDO, porque el enunciado exacto de la escuela es sobre él:
    # a_T = 0, y por tanto z_T = −media/sd — el tipificado se queda EN LA MEDIA
    # de los residuos, no en cero. Comprobado: a_T = −3,5·10⁻⁸ sobre ruido
    # blanco con un impulso libre. Si μ se estima, la media es ~0 y coinciden.
    residuo_en_fechas: list[float] = field(default_factory=list)

    @property
    def absorbido(self) -> bool:
        """Los residuos en las fechas intervenidas están en la media."""
        return all(abs(v) <= self.umbral_absorcion for v in self.z_en_fechas)

    @property
    def vecino_anomalo(self) -> str | None:
        a = self.z_antes is not None and abs(self.z_antes) > self.umbral_vecino
        d = self.z_despues is not None and abs(self.z_despues) > self.umbral_vecino
        return ("ambos" if a and d else "antes" if a else
                "después" if d else None)

    @property
    def funciona(self) -> bool:
        return self.absorbido and self.vecino_anomalo is None

    def summary(self) -> str:
        et = (f"{self.itv_type}[obs {self.at_0based + 1}]")
        marca = "✓" if self.funciona else "✗"
        L = [f"  [{self.itv_index:2d}] {et:<22} {marca}"]
        zs = "  ".join(f"{v:+.2f}" for v in self.z_en_fechas)
        L.append(f"       z en las fechas: {zs}"
                 + ("   (en la media de los residuos)" if self.absorbido
                    else "   ← NO absorbido"))
        if self.residuo_en_fechas:
            rs = "  ".join(f"{v:+.3g}" for v in self.residuo_en_fechas)
            L.append(f"       residuo crudo:   {rs}")
        vs = []
        if self.z_antes is not None:
            vs.append(f"antes {self.z_antes:+.2f}")
        if self.z_despues is not None:
            vs.append(f"después {self.z_despues:+.2f}")
        if vs:
            L.append(f"       vecinos: {'  ·  '.join(vs)}"
                     + (f"   ← ANÓMALO ({self.vecino_anomalo})"
                        if self.vecino_anomalo else ""))
        if self.vecino_anomalo:
            L.append("       ⇒ la representación es errónea: o la FORMA se "
                     "queda corta (hay episodio) o la FECHA está desplazada.")
        return "\n".join(L)


def check_intervention_fit(model,
                           umbral_vecino: float = 3.0,
                           umbral_absorcion: float = 1.5
                           ) -> list[InterventionFitCheck]:
    """La regla de Treadway sobre cada intervención de un modelo ajustado.

    Diagnosis, no bloqueo: dice si cada intervención hizo su trabajo y, cuando
    no, cuál de los dos errores de representación es más probable.

    Parameters
    ----------
    model            : `fue.Model` ya ajustado
    umbral_vecino    : |z| a partir del cual un vecino cuenta como anómalo
    umbral_absorcion : |z| por debajo del cual un residuo está «en la media»
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    res = np.asarray(model._result.residuals, dtype=float)
    n = len(res)
    std = float(res.std(ddof=0))
    if std < 1e-20:
        return []
    z = (res - float(res.mean())) / std

    freq = int(getattr(model.series, "freq", 1) or 1)
    desfase = int(getattr(model, "d", 0)) + int(getattr(model, "D", 0)) * freq

    fuera = []
    for idx, itv in enumerate(model.interventions or []):
        if itv.type not in ("pulse", "impulse", "step", "ramp", "compimp"):
            continue                       # cos/sin/alter no son sucesos
        s = max(len(itv.omega or [1]) - 1, 0)
        # obs 1-based en RESIDUOS de la primera fecha intervenida
        ini = int(itv.at) + 1 - desfase
        fechas = [ini + k for k in range(s + 1)]
        dentro = [p for p in fechas if 1 <= p <= n]
        if not dentro:
            continue
        antes = dentro[0] - 1
        despues = dentro[-1] + 1
        fuera.append(InterventionFitCheck(
            itv_index=idx, itv_type=itv.type, at_0based=int(itv.at),
            fechas=dentro,
            z_en_fechas=[float(z[p - 1]) for p in dentro],
            residuo_en_fechas=[float(res[p - 1]) for p in dentro],
            z_antes=float(z[antes - 1]) if 1 <= antes <= n else None,
            z_despues=float(z[despues - 1]) if 1 <= despues <= n else None,
            umbral_vecino=umbral_vecino, umbral_absorcion=umbral_absorcion,
        ))
    return fuera
