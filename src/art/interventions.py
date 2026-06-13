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

    For an FLT with delta (multi-parameter transfer function):
        Individual t-tests per free omega, plus a joint Wald test
        H₀: g = 0  where  g = α·ω,  V(g) = α·COV(ω)·αᵀ,
        α = (1, −δ₁, −δ₂, …) of dimension len(omega).
    """
    itv_index: int              # 0-based index into model.interventions
    itv_type: str               # 'pulse', 'step', 'cos', 'sin', 'alter', …
    itv_at: int                 # 0-based obs index (0 for cos/sin/alter)
    harmonic: float | None      # for cos/sin only
    omega: list[float]          # estimated free omega coefs (in order)
    omega_se: list[float]       # standard errors
    omega_t: list[float]        # individual t-statistics
    omega_p: list[float]        # individual 2-sided p-values
    wald_stat: float | None     # Wald χ²(k) for multi-param joint test; None if k==1
    wald_p: float | None        # p-value of Wald test; None if k==1
    df: int                     # degrees of freedom (n_obs - npar) for t-tests
    significant: bool           # True if ANY free omega param is significant at 5%

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
            lines.append(f"       Wald χ²({len(self.omega)})={self.wald_stat:.3f}  p={self.wald_p:.4f} {wstar}")
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

    For FLTs with delta, an additional joint Wald test is performed:
        H₀: g = α·ω = 0,  α = (1, −δ₁, −δ₂, …),  V(g) = α·COV(ω)·αᵀ.

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

    # Collect free omega indices and values
    free_om_idx = []   # global param indices for free omega coefs
    free_om_val = []
    local = start
    for v, f in zip(om, omf):
        if f:
            free_om_idx.append(local)
            free_om_val.append(float(params[local]))
            local += 1

    omega_est  = [float(params[i]) for i in free_om_idx]
    omega_se   = [float(np.sqrt(max(cov[i, i], 0.0))) for i in free_om_idx]
    omega_t    = [v / s if s > 0 else float("nan")
                  for v, s in zip(omega_est, omega_se)]
    omega_p    = [float(2 * sp_stats.t.sf(abs(t), df=df))
                  for t in omega_t]

    # Joint Wald test for FLT (delta ≠ 0)
    wald_stat = None
    wald_p    = None
    k = len(free_om_idx)
    if k > 1 and any(f for f in dlf):
        # α = (1, −δ₁, …) where δᵢ are the free delta coefs
        # For k free omegas, α has the same length k
        free_dl = [float(v) for v, f in zip(dl, dlf) if f]
        alpha_vec = np.array([1.0] + [-d for d in free_dl[:k - 1]])
        alpha_vec = alpha_vec[:k]   # trim/pad to k
        if len(alpha_vec) < k:
            alpha_vec = np.pad(alpha_vec, (0, k - len(alpha_vec)))
        sub_cov = cov[np.ix_(free_om_idx, free_om_idx)]
        g       = float(alpha_vec @ np.array(omega_est))
        Vg      = float(alpha_vec @ sub_cov @ alpha_vec)
        if Vg > 0:
            wald_stat = g ** 2 / Vg          # χ²(1) under H₀: g=0
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
