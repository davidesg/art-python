"""
Formal hypothesis tests (Phase 3 of Box-Jenkins-Treadway cycle).

Prerequisites (thesis 2.4.4): a model must be:
  (1) efficiently estimated — MVENC converged,
  (2) statistically adequate — white-noise residuals, and
  (3) parsimoniously parametrized
before any formal test is applied.

Current tests
-------------
shin_fuller : Shin-Fuller (1998) Φ̂₁ᵤ test for non-stationarity.
              H₀: ρ=1; ρₘ=1−4/n; critical values from Table II (5%≈1.75).
              The appropriate formal test for d in an estimated ARMAX model.
              Requires a model that is adequate and parsimoniously parametrized.
              Do NOT use for initial d specification — use ADF/KPSS (Bloque L).
dcd         : DCD non-invertibility test for regular MA(1) factors.
              H₀: θ = 1 (unit root in MA polynomial).
              Critical values from thesis Table 2.2: 10 % = 1.00, 5 % = 1.94,
              1 % = 4.41.
dcd_f       : DCD non-invertibility test for fixed-frequency MA_f factors.
              H₀: λ₂ = −1 (seasonal integration at frequency f).
              Critical values: 10 % = 1.07, 5 % = 2.02, 1 % = 4.52.
              Uses the pure-Python estimator for both models to work around
              the nlatools.c tensor() bug that crashes the C backend when
              combining AR + MA_f (see fue/TODO.md).
rv          : RV fixed-frequency test for AR(2) factors with complex roots.
              H₀: resonant frequency = k (a seasonal harmonic).
              Under H₀ the AR(2) can be reparametrised as ar_f(freq=k),
              saving 1 degree of freedom.  LR ~ χ²(1).
meg         : MEG stochastic seasonality evaluation.
              For each frequency f: augments the model with AR_f unit root
              (ifadf[f]=1) + free MA_f testigo, removes deterministic
              harmonics at f, and applies DCD_f on the testigo.
              MA_f invertible → stochastic; non-invertible → deterministic.

Critical values (Treadway tradition)
-------------------------------------
DCD regular MA (thesis Cuadro 2.2):
    10 % = 1.00,  5 % = 1.94,  1 % = 4.41
DCD fixed-frequency MA_f (DCD_f):
    10 % = 1.07,  5 % = 2.02,  1 % = 4.52
Both sets are from Treadway (thesis), obtained by simulation.
Monte Carlo verification of the exact distribution is pending (see TODO T1).

MEG strategy
------------
Frequencies are tested independently, round by round.  If a unit root is
found at frequency f₀ in round 1, the analyst re-runs MEG including
ifadf[f₀]=1 before testing remaining frequencies in round 2.  The analyst
must confirm the round-1 finding before proceeding.  Multiple testing
inflates type I error by 1−(1−α)^k; for monthly data (s=12, k≤5 non-biannual
harmonics) the inflation is acceptable at α=5 %.

TODO / Pending work
--------------------
T1. DCD and DCD_f critical values — Monte Carlo verification of the Treadway
    tabulated values.  Current values are taken from the thesis; bootstrapped
    or simulated counterparts have not yet been produced.

T2. MEG_AR (NOT IMPLEMENTED) — complementary test using AR_f non-stationarity,
    analogous to Shin-Fuller (1998) for seasonal frequencies.
    Motivation: Shin-Fuller tests regular unit roots via unconditional MLE LR.
    An AR_f variant would approach seasonal integration from the AR side and
    complement MEG (which works from the MA side via DCD_f).
    Status: degenerate in standard fue models (d≥2).
    Reason: in ∇ᵈy_t with d≥2, a seasonal unit root at frequency f manifests
    as MA_f non-invertibility (MA_f→−1), not as AR_f near-unit-root.  Adding
    AR_f with coef≈−1 to the AR polynomial creates a double seasonal filter
    at f, causing catastrophic likelihood loss (Δℓ≈−130 for Chile IPC n=192).
    The free AR_f invariably converges to ≈0 regardless of the true seasonality
    type, and the LR is always large (≈258) — no discriminating power.
    Valid context: models with d=0 or d=1 where the seasonal unit root has not
    yet been extracted into the differencing (OCSB/Canova-Hansen territory,
    outside the standard Treadway workflow).
    Harmonic cancellation: harmonics at f cancel with AR_f at the unit root
    (correct to remove them at the boundary); however, neither removing nor
    keeping harmonics resolves the degeneracy above.
    Conclusion: for the standard fue d≥2 workflow, MEG (MA_f testigo + DCD_f)
    is both theoretically correct and empirically effective.  MEG_AR is not
    implemented and is not part of the Treadway tradition.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

import numpy as np
import scipy.stats as sp_stats


# ---------------------------------------------------------------------------
# Critical values for DCD test (thesis Table 2.2)
# Non-standard distribution; values valid for n ≥ 50.
# ---------------------------------------------------------------------------

_DCD_CRIT_MA   = {'10%': 1.00, '5%': 1.94, '1%': 4.41}
_DCD_CRIT_MA_F = {'10%': 1.07, '5%': 2.02, '1%': 4.52}


# ---------------------------------------------------------------------------
# Critical values for Shin-Fuller (1998) Φ̂₁ᵤ test — Table II
# Φ̂₁ᵤ = L_free − L_constrained  (NOT 2·ΔL).
# Larger values reject H₀ (unit root) → evidence of stationarity.
# ---------------------------------------------------------------------------

_SF_CRIT = [
    #  n,   10%,   5%,   1%
    ( 25, 1.02, 1.68, 3.33),
    ( 50, 1.06, 1.75, 3.41),
    (100, 1.07, 1.75, 3.41),
    (250, 1.07, 1.76, 3.44),
    (500, 1.08, 1.77, 3.46),
]


def _sf_crit(n: int) -> tuple[float, float, float]:
    """Linear interpolation of Shin-Fuller (1998) Table II critical values."""
    if n <= _SF_CRIT[0][0]:
        return _SF_CRIT[0][1], _SF_CRIT[0][2], _SF_CRIT[0][3]
    if n >= _SF_CRIT[-1][0]:
        return _SF_CRIT[-1][1], _SF_CRIT[-1][2], _SF_CRIT[-1][3]
    for i in range(len(_SF_CRIT) - 1):
        n0, c10_0, c5_0, c1_0 = _SF_CRIT[i]
        n1, c10_1, c5_1, c1_1 = _SF_CRIT[i + 1]
        if n0 <= n <= n1:
            t = (n - n0) / (n1 - n0)
            return (
                c10_0 + t * (c10_1 - c10_0),
                c5_0  + t * (c5_1  - c5_0),
                c1_0  + t * (c1_1  - c1_0),
            )
    return _SF_CRIT[-1][1], _SF_CRIT[-1][2], _SF_CRIT[-1][3]  # unreachable


# ---------------------------------------------------------------------------
# Shin-Fuller (1998) non-stationarity test
# ---------------------------------------------------------------------------

@dataclass
class ShinFullerResult:
    """Result of the Shin-Fuller (1998) Φ̂₁ᵤ test."""
    phi_null: float          # ρₘ = 1 − 4/n  (Table II null point)
    phi_free: list[float]    # estimated AR coefficients (free model)
    loglik_free: float
    loglik_constrained: float
    phi_1u: float            # Φ̂₁ᵤ = L_free − L_constrained  (eq. 3.5)
    crit_10pct: float        # Table II critical value at 10 %
    crit_5pct: float         # Table II critical value at 5 %
    crit_1pct: float         # Table II critical value at 1 %
    df: int                  # number of constrained AR params
    pvalue: float            # chi²(df) p-value of 2·Φ̂₁ᵤ (conservative approx.)
    n: int
    s: int

    @property
    def lr(self) -> float:
        """2·Φ̂₁ᵤ — conventional LR scale (for display/chi² reference only)."""
        return 2.0 * self.phi_1u

    @property
    def stationary(self) -> bool:
        """True if Φ̂₁ᵤ > 5% critical value (H₀ unit-root rejected)."""
        return self.phi_1u > self.crit_5pct

    def summary(self) -> str:
        phi_str = ", ".join(f"{v:.4f}" for v in self.phi_free)
        stars = ("***" if self.phi_1u > self.crit_1pct
                 else "** " if self.phi_1u > self.crit_5pct
                 else "*  " if self.phi_1u > self.crit_10pct
                 else "   ")
        lines = [
            "Shin-Fuller (1998) non-stationarity test",
            f"  n={self.n}, s={self.s}",
            f"  ρₘ = 1 − 4/n = {self.phi_null:.6f}",
            f"  φ_free = [{phi_str}]",
            f"  logL(free) = {self.loglik_free:.4f}",
            f"  logL(constrained) = {self.loglik_constrained:.4f}",
            f"  Φ̂₁ᵤ = {self.phi_1u:.4f}  {stars}",
            f"  Crit. vals (Table II): 10%={self.crit_10pct:.2f}  5%={self.crit_5pct:.2f}  1%={self.crit_1pct:.2f}",
            f"  → {'ESTACIONARIO ✓' if self.stationary else 'RAÍZ UNITARIA — considerar d+1 ✗'}",
        ]
        return "\n".join(lines)


def _count_free_ar(model) -> int:
    """Count free regular AR parameters."""
    n = 0
    for i, factor in enumerate(model.ar or []):
        free = (model.ar_free[i]
                if model.ar_free and i < len(model.ar_free)
                else [True] * len(factor))
        n += sum(free)
    return n


def _extract_ar_params(model) -> list[float]:
    """
    Extract estimated values of free regular AR coefficients from model.params.

    Parameter ordering (from cast_us._build_initial_x):
      1. omega_free per intervention
      2. delta_free per intervention
      3. AR regular
      4. AR seasonal
      5. MA regular  ...
    """
    # Count intervention free params that come before AR
    n_omega = sum(
        sum(itv.omega_free)
        for itv in (model.interventions or [])
    )
    n_delta = sum(
        sum(itv.delta_free)
        for itv in (model.interventions or [])
    )
    start = n_omega + n_delta

    params = np.asarray(model.params, dtype=float)
    values = []
    idx = start
    for i, factor in enumerate(model.ar or []):
        free = (model.ar_free[i]
                if model.ar_free and i < len(model.ar_free)
                else [True] * len(factor))
        for j in range(len(factor)):
            if free[j]:
                values.append(float(params[idx]))
                idx += 1
    return values


def shin_fuller(model) -> ShinFullerResult:
    """
    Shin-Fuller (1998) likelihood-ratio test for non-stationarity.

    H₀: ρ = 1 (AR near-unit-root; d is under-specified)
    H₁: ρ < 1 (AR is stationary; d is correct)

    Test statistic: Φ̂₁ᵤ = L_free − L_constrained  (eq. 3.5, NOT 2·ΔL).
    The constrained model fixes ρ = ρₘ = 1 − 4/n (the median of the null
    distribution of ρ̂μ; see Shin-Fuller 1998, p. 595) and sets all higher-
    order AR coefficients to zero; all other parameters re-estimated freely.
    H₀ is rejected if Φ̂₁ᵤ exceeds the 5 % critical value from Table II
    (≈ 1.75 for n ≥ 50).

    Prerequisites
    -------------
    * The model must be adequate (white-noise residuals) and parsimoniously
      parametrized before applying this test — formal hypothesis testing
      requires a correctly specified model (thesis 2.4.4).
    * model.fit() has already been called (model._result is not None).
    * model.ar is non-empty and has at least one free coefficient.
    * Applies to REGULAR AR only; seasonal AR (model.ar_s) is untouched.

    Note: for initial d specification (before estimation), use ADF + KPSS
    via unit_root_tests() in identification.py (Bloque L).

    Reference
    ---------
    Shin, D.-W. & Fuller, W. A. (1998). Unit root tests based on unconditional
    maximum likelihood estimation for the autoregressive moving average model.
    Journal of Time Series Analysis, 19(5), 591–599.
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")
    if _count_free_ar(model) == 0:
        raise ValueError("No free regular AR parameters — SF test not applicable.")


    n = model.series.nobs
    s = model.series.freq
    phi_null = 1.0 - 4.0 / n   # ρₘ = 1 − 4/n  (Shin-Fuller 1998, p. 595)

    L_free = float(model._result.loglik)
    phi_free = _extract_ar_params(model)
    df = len(phi_free)

    # --- constrained model: fix AR at phi_null for first coef, 0 elsewhere ---
    mc = copy.deepcopy(model)
    mc._result = None

    for i in range(len(mc.ar)):
        order = len(mc.ar[i])
        null_coefs = [phi_null if j == 0 else 0.0 for j in range(order)]
        mc.ar[i] = null_coefs
        if mc.ar_free is None:
            mc.ar_free = [[False] * order for _ in mc.ar]
        else:
            mc.ar_free[i] = [False] * order

    mc.fit()
    L_constrained = float(mc._result.loglik)

    phi_1u = L_free - L_constrained           # Φ̂₁ᵤ — eq. (3.5)
    pvalue = float(sp_stats.chi2.sf(2.0 * phi_1u, df))  # conservative chi² approx.
    c10, c5, c1 = _sf_crit(n)

    return ShinFullerResult(
        phi_null=phi_null,
        phi_free=phi_free,
        loglik_free=L_free,
        loglik_constrained=L_constrained,
        phi_1u=phi_1u,
        crit_10pct=c10,
        crit_5pct=c5,
        crit_1pct=c1,
        df=df,
        pvalue=pvalue,
        n=n,
        s=s,
    )


# ---------------------------------------------------------------------------
# DCD (Durbin-Cantrell-Davidson) non-invertibility test
# ---------------------------------------------------------------------------

@dataclass
class DCDResult:
    """Result of the DCD non-invertibility test for one MA factor."""
    factor_index: int         # 0-based index into model.ma
    freq: float | None        # None for regular MA; cycle frequency for MA_f
    coef_free: float          # estimated MA coefficient in the free model
    coef_null: float          # null value: 1.0 for regular MA
    loglik_free: float
    loglik_constrained: float
    lr: float                 # 2·(L_free − L_constrained)

    @property
    def _crit(self) -> dict:
        return _DCD_CRIT_MA if self.freq is None else _DCD_CRIT_MA_F

    @property
    def rejects_10pct(self) -> bool:
        return self.lr > self._crit['10%']

    @property
    def rejects_5pct(self) -> bool:
        return self.lr > self._crit['5%']

    @property
    def rejects_1pct(self) -> bool:
        return self.lr > self._crit['1%']

    @property
    def invertible(self) -> bool:
        """True if H₀ (unit root) rejected at 5 %."""
        return self.rejects_5pct

    def summary(self) -> str:
        if self.freq is None:
            param_str = f"θ (regular MA factor {self.factor_index})"
        else:
            param_str = f"λ_f (MA_f at freq={self.freq})"
        crit = self._crit
        pct = ("***" if self.rejects_1pct
               else "** " if self.rejects_5pct
               else "*  " if self.rejects_10pct
               else "   ")
        lines = [
            f"DCD non-invertibility test — {param_str}",
            f"  H₀: {param_str} = {self.coef_null:.1f}",
            f"  coef (free model) = {self.coef_free:.6f}",
            f"  logL(free) = {self.loglik_free:.4f}",
            f"  logL(constrained) = {self.loglik_constrained:.4f}",
            f"  LR = {self.lr:.4f}  {pct}",
            f"  Critical values: 10%={crit['10%']}, 5%={crit['5%']}, 1%={crit['1%']}",
            f"  → {'INVERTIBLE ✓' if self.invertible else 'NO INVERTIBLE — revisar d ✗'}",
        ]
        return "\n".join(lines)


def _extract_ma_param(model, factor_index: int) -> float:
    """
    Extract estimated value of the first free coefficient of MA factor factor_index
    from model.params.

    Parameter ordering (cast_us._build_initial_x):
      1. omega_free per intervention
      2. delta_free per intervention
      3. AR regular (free)
      4. AR seasonal (free)
      5. MA regular (free)  ← we want this
      ...
    """
    n_omega = sum(
        sum(itv.omega_free)
        for itv in (model.interventions or [])
    )
    n_delta = sum(
        sum(itv.delta_free)
        for itv in (model.interventions or [])
    )

    def _count_free(factors, free_lists):
        total = 0
        for i, fac in enumerate(factors or []):
            free = (free_lists[i]
                    if free_lists and i < len(free_lists)
                    else None)
            total += sum(1 for j in range(len(fac))
                         if free is None or free[j])
        return total

    n_ar   = _count_free(model.ar,   model.ar_free)
    n_ar_s = _count_free(model.ar_s, model.ar_s_free)

    params = np.asarray(model.params, dtype=float)
    idx = n_omega + n_delta + n_ar + n_ar_s

    for i, fac in enumerate(model.ma or []):
        free = (model.ma_free[i]
                if model.ma_free and i < len(model.ma_free)
                else None)
        if i == factor_index:
            for j in range(len(fac)):
                if free is None or free[j]:
                    return float(params[idx])
            raise ValueError(
                f"MA factor {factor_index} has no free coefficients"
            )
        idx += sum(1 for j in range(len(fac))
                   if free is None or free[j])

    raise IndexError(f"MA factor index {factor_index} out of range")


def dcd(model) -> list[DCDResult]:
    """
    DCD (Durbin-Cantrell-Davidson) non-invertibility test for regular MA factors.

    Tests H₀: θ = 1 (unit root in the MA polynomial) for each free regular MA(1)
    factor.  Under H₀ the MA factor is at its non-invertibility boundary and the
    model should be reformulated (typically by reducing d by one).

    LR = 2·[logL(free) − logL(θ=1)]

    The distribution is non-standard.  Critical values from thesis Table 2.2:
      10 % = 1.00,  5 % = 1.94,  1 % = 4.41.

    Parameters
    ----------
    model : fue.Model, already fitted (.fit() called)

    Returns
    -------
    list[DCDResult] — one entry per free regular MA(1) factor found.

    Raises
    ------
    RuntimeError  if model not fitted
    ValueError    if no free regular MA(1) factors are present
    NotImplementedError  if any MA factor has order > 1 (MA(q), q > 1)

    Notes
    -----
    For MA_f (fixed-frequency MA) factors use dcd_f() — not yet implemented
    because the fue C backend crashes when combining AR/AR_f with MA_f.
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    ma = model.ma or []

    # Validate: only MA(1) supported
    for i, fac in enumerate(ma):
        if len(fac) != 1:
            raise NotImplementedError(
                f"DCD for MA({len(fac)}) not implemented — only MA(1) supported."
            )

    # Identify free factors
    testable = []
    for i, fac in enumerate(ma):
        free = (model.ma_free[i]
                if model.ma_free and i < len(model.ma_free)
                else None)
        if free is None or free[0]:
            testable.append(i)

    if not testable:
        raise ValueError(
            "No free regular MA(1) factors found — DCD not applicable."
        )

    L_free = float(model._result.loglik)
    results = []

    for i in testable:
        coef_free = _extract_ma_param(model, i)

        mc = copy.deepcopy(model)
        mc._result = None
        mc.ma[i] = [1.0]
        if mc.ma_free is None:
            mc.ma_free = [[True] for _ in mc.ma]
        mc.ma_free[i] = [False]
        mc.fit()

        L_const = float(mc._result.loglik)
        lr = 2.0 * (L_free - L_const)

        results.append(DCDResult(
            factor_index=i,
            freq=None,
            coef_free=coef_free,
            coef_null=1.0,
            loglik_free=L_free,
            loglik_constrained=L_const,
            lr=lr,
        ))

    return results


# ---------------------------------------------------------------------------
# DCD for fixed-frequency MA_f factors
# ---------------------------------------------------------------------------

def _extract_ma_f_param(model, factor_index: int) -> float:
    """
    Extract estimated coef of MA_f factor at factor_index from model.params.

    Parameter ordering (cast_us._build_initial_x):
      1. omega_free per intervention
      2. delta_free per intervention
      3. AR regular (free)
      4. AR seasonal (free)
      5. MA regular (free)
      6. MA seasonal (free)
      7. AR_f free coefs  ← one scalar per free AR_f
      8. MA_f free coefs  ← we want this
    """
    n_omega = sum(
        sum(itv.omega_free)
        for itv in (model.interventions or [])
    )
    n_delta = sum(
        sum(itv.delta_free)
        for itv in (model.interventions or [])
    )

    def _count_free(factors, free_lists):
        total = 0
        for i, fac in enumerate(factors or []):
            free = (free_lists[i]
                    if free_lists and i < len(free_lists)
                    else None)
            total += sum(1 for j in range(len(fac))
                         if free is None or free[j])
        return total

    n_ar   = _count_free(model.ar,   model.ar_free)
    n_ar_s = _count_free(model.ar_s, model.ar_s_free)
    n_ma   = _count_free(model.ma,   model.ma_free)
    n_ma_s = _count_free(model.ma_s, model.ma_s_free)
    n_ar_f = sum(1 for ff in (model.ar_f or []) if ff.free)

    params = np.asarray(model.params, dtype=float)
    idx = n_omega + n_delta + n_ar + n_ar_s + n_ma + n_ma_s + n_ar_f

    for i, ff in enumerate(model.ma_f or []):
        if i == factor_index:
            if not ff.free:
                raise ValueError(f"MA_f factor {factor_index} is not free")
            return float(params[idx])
        if ff.free:
            idx += 1

    raise IndexError(f"MA_f factor index {factor_index} out of range")


def _fit_py(mc) -> None:
    """
    Fit a model in-place using the pure-Python estimator only.

    Retained as a fallback for environments where the C extension is not
    compiled.  The tensor() bug that required this workaround for AR+MA_f
    models has been fixed in fue/csrc/internal/nlatools.c (nrh-nrl+1
    allocation + shifted pointer).
    """
    from fue.cast_us import estimate_py
    from fue.model import FitResult
    raw = estimate_py(mc)
    mc._result = FitResult(raw)
    if not mc._result.converged:
        raise RuntimeError(
            f"Pure-Python estimation failed: ifault={mc._result.ifault}"
        )


def dcd_f(model) -> list[DCDResult]:
    """
    DCD non-invertibility test for fixed-frequency MA_f factors.

    Tests H₀: λ₂ = −1 (seasonal integration boundary) for each free MA_f
    factor.  Under H₀ the factor 1 − 2cos(2πf/s)·B + B² represents a unit
    root at frequency f, and the model should be reformulated (typically by
    adding a seasonal integration operator at that frequency).

    LR = 2·[logL(free) − logL(λ₂=−1)]

    The distribution is non-standard.  Critical values from thesis Table 2.2:
      10 % = 1.07,  5 % = 2.02,  1 % = 4.52.

    Implementation note
    -------------------
    Both the free and constrained models are estimated with model.fit() which
    uses the C backend when available.  The tensor() bug in nlatools.c that
    previously caused a crash for AR + MA_f combinations has been fixed
    (calloc size corrected to nrh−nrl+1, shifted pointer for negative nrl).

    Parameters
    ----------
    model : fue.Model, already fitted (.fit() called)

    Returns
    -------
    list[DCDResult] — one entry per free MA_f factor found.

    Raises
    ------
    RuntimeError  if model not fitted
    ValueError    if no free MA_f factors are present
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    ma_f = model.ma_f or []
    testable = [i for i, ff in enumerate(ma_f) if ff.free]

    if not testable:
        raise ValueError(
            "No free MA_f factors found — DCD_f not applicable."
        )

    # Re-fit the free model to get a consistent loglik baseline.
    m_free = copy.deepcopy(model)
    m_free._result = None
    m_free.fit()
    L_free = float(m_free._result.loglik)

    results = []

    for i in testable:
        coef_free = _extract_ma_f_param(m_free, i)

        # Constrained: fix MA_f[i] at λ₂ = −1, all other factors free.
        mc = copy.deepcopy(model)
        mc._result = None
        from fue.model import FixedFreqFactor
        orig = mc.ma_f[i]
        mc.ma_f[i] = FixedFreqFactor(freq=orig.freq, coef=-1.0, free=False)
        mc.fit()

        L_const = float(mc._result.loglik)
        lr = 2.0 * (L_free - L_const)

        results.append(DCDResult(
            factor_index=i,
            freq=model.ma_f[i].freq,
            coef_free=coef_free,
            coef_null=-1.0,
            loglik_free=L_free,
            loglik_constrained=L_const,
            lr=lr,
        ))

    return results


# ---------------------------------------------------------------------------
# RV fixed-frequency test for AR(2) factors with complex roots
# ---------------------------------------------------------------------------

def _extract_ar_factor_coefs(model, ar_factor_index: int) -> tuple[float, ...]:
    """
    Extract estimated values of free coefficients for AR factor ar_factor_index.

    Parameter ordering (cast_us._build_initial_x):
      1. omega_free per intervention
      2. delta_free per intervention
      3. AR regular (free)  ← target
      ...
    """
    n_omega = sum(sum(itv.omega_free) for itv in (model.interventions or []))
    n_delta = sum(sum(itv.delta_free) for itv in (model.interventions or []))
    params = np.asarray(model.params, dtype=float)
    idx = n_omega + n_delta

    for i, factor in enumerate(model.ar or []):
        free = (model.ar_free[i]
                if model.ar_free and i < len(model.ar_free)
                else [True] * len(factor))
        if i == ar_factor_index:
            coefs = []
            for j in range(len(factor)):
                if free[j]:
                    coefs.append(float(params[idx]))
                    idx += 1
            return tuple(coefs)
        for j in range(len(factor)):
            if free[j]:
                idx += 1

    raise IndexError(f"AR factor index {ar_factor_index} out of range")


@dataclass
class RVResult:
    """Result of the RV fixed-frequency test for one AR(2) factor."""
    ar_factor_index: int
    freq_estimated: float   # estimated resonant frequency f̂ (harmonic units)
    freq_null: int          # harmonic k tested under H₀: f = k
    phi1: float             # fitted φ₁ (free model)
    phi2: float             # fitted φ₂ (free model); φ₂ < 0 for complex roots
    rho: float              # modulus = √(−φ₂) of the inverse roots
    loglik_free: float
    loglik_constrained: float
    lr: float               # 2·(L_free − L_constrained)
    pvalue: float           # chi²(1) p-value

    @property
    def rejects_5pct(self) -> bool:
        return self.pvalue < 0.05

    @property
    def rejects_1pct(self) -> bool:
        return self.pvalue < 0.01

    @property
    def fixed_frequency(self) -> bool:
        """True if H₀ (frequency = freq_null) is NOT rejected at 5%."""
        return not self.rejects_5pct

    def summary(self) -> str:
        lines = [
            f"RV fixed-frequency test — AR(2) factor {self.ar_factor_index}",
            f"  H₀: f = {self.freq_null}  (f̂ = {self.freq_estimated:.4f})",
            f"  φ̂₁ = {self.phi1:.6f},  φ̂₂ = {self.phi2:.6f},  ρ̂ = {self.rho:.6f}",
            f"  logL(free) = {self.loglik_free:.4f}",
            f"  logL(constrained) = {self.loglik_constrained:.4f}",
            f"  LR = {self.lr:.4f}",
            f"  p-value = {self.pvalue:.4f}  [χ²(1)]",
            f"  → {'FRECUENCIA FIJA ✓' if self.fixed_frequency else 'FRECUENCIA LIBRE ✗'}",
        ]
        return "\n".join(lines)


def rv(model, ar_factor_index: int = 0,
       freq_null: int | list[int] | None = None) -> list[RVResult]:
    """
    RV fixed-frequency test for AR(2) factors with complex roots.

    Tests H₀: resonant frequency = k (a seasonal harmonic) against
    H₁: frequency is free.  Under H₀ the AR(2) can be reparametrised as
    ar_f(freq=k), saving one degree of freedom (parsimony gain).

    LR = 2·[logL(AR₂ free) − logL(ar_f fixed at k)] ~ χ²(1)

    Parameters
    ----------
    model : fue.Model, already fitted (.fit() called)
    ar_factor_index : int
        Index into model.ar of the AR(2) factor to test.  Default 0.
    freq_null : int, list[int], or None
        Harmonic(s) to test as H₀.  None → test all k = 1 … s//2.

    Returns
    -------
    list[RVResult] — one entry per tested harmonic.

    Raises
    ------
    RuntimeError   if model not fitted
    ValueError     if factor is not AR(2) with 2 free coefs, or roots are real
    IndexError     if ar_factor_index is out of range
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    ar = model.ar or []
    if not ar:
        raise ValueError("Model has no regular AR factors — RV test not applicable.")
    if ar_factor_index >= len(ar):
        raise IndexError(
            f"ar_factor_index={ar_factor_index} out of range "
            f"(model has {len(ar)} AR factor(s))"
        )

    factor = ar[ar_factor_index]
    free_flags = (model.ar_free[ar_factor_index]
                  if model.ar_free and ar_factor_index < len(model.ar_free)
                  else [True] * len(factor))

    if len(factor) != 2:
        raise ValueError(
            f"AR factor {ar_factor_index} has order {len(factor)}, not 2. "
            "RV test requires AR(2)."
        )
    if sum(free_flags) != 2:
        raise ValueError(
            f"AR factor {ar_factor_index} has {sum(free_flags)} free parameter(s), "
            "need exactly 2 free coefficients for RV test."
        )

    phi1, phi2 = _extract_ar_factor_coefs(model, ar_factor_index)

    disc = phi1**2 + 4.0 * phi2
    if disc >= 0.0:
        raise ValueError(
            f"AR(2) factor {ar_factor_index} has real roots "
            f"(discriminant = {disc:.4f} ≥ 0). RV test requires complex roots."
        )

    rho = math.sqrt(-phi2)
    cos_w = max(-1.0, min(1.0, phi1 / (2.0 * rho)))
    omega_hat = math.acos(cos_w)
    s = model.series.freq
    freq_hat = omega_hat * s / (2.0 * math.pi)

    if freq_null is None:
        harmonics = list(range(1, s // 2 + 1))
    elif isinstance(freq_null, int):
        harmonics = [freq_null]
    else:
        harmonics = list(freq_null)

    for k in harmonics:
        if not (1 <= k <= s // 2):
            raise ValueError(
                f"freq_null={k} out of range [1, {s // 2}] for s={s}."
            )

    L_free = float(model._result.loglik)
    results = []

    for k in harmonics:
        mc = copy.deepcopy(model)
        mc._result = None

        # Remove the tested AR(2): replace by ar_f(freq=k, coef=phi2 as init)
        mc.ar = [f for j, f in enumerate(mc.ar) if j != ar_factor_index]
        if mc.ar_free is not None:
            mc.ar_free = [f for j, f in enumerate(mc.ar_free) if j != ar_factor_index]
        if not mc.ar:
            mc.ar_free = None

        from fue.model import FixedFreqFactor
        mc.ar_f = list(mc.ar_f or []) + [FixedFreqFactor(freq=float(k), coef=phi2, free=True)]

        _fit_py(mc)
        L_const = float(mc._result.loglik)
        lr = 2.0 * (L_free - L_const)
        pvalue = float(sp_stats.chi2.sf(lr, df=1))

        results.append(RVResult(
            ar_factor_index=ar_factor_index,
            freq_estimated=freq_hat,
            freq_null=k,
            phi1=phi1,
            phi2=phi2,
            rho=rho,
            loglik_free=L_free,
            loglik_constrained=L_const,
            lr=lr,
            pvalue=pvalue,
        ))

    return results


# ---------------------------------------------------------------------------
# MEG stochastic seasonality evaluation
# ---------------------------------------------------------------------------

@dataclass
class MEGResult:
    """Result of the MEG stochastic seasonality test for one seasonal frequency."""
    freq: int                      # seasonal harmonic tested (1..s//2−1)
    coef_ma_f: float | None        # estimated MA_f testigo coef (None if ambiguous)
    dcd_result: DCDResult | None   # DCD_f output (None if ambiguous)
    status: str                    # 'stochastic', 'deterministic', 'ambiguous'

    @property
    def stochastic(self) -> bool:
        """True if stochastic seasonality detected at this frequency."""
        return self.status == 'stochastic'

    @property
    def deterministic(self) -> bool:
        """True if deterministic seasonality at this frequency."""
        return self.status == 'deterministic'

    def summary(self) -> str:
        lines = [f"MEG stochastic seasonality — freq={self.freq}"]
        if self.dcd_result is not None:
            lr = self.dcd_result.lr
            crit = self.dcd_result._crit
            pct = ("***" if self.dcd_result.rejects_1pct
                   else "** " if self.dcd_result.rejects_5pct
                   else "*  " if self.dcd_result.rejects_10pct
                   else "   ")
            lines += [
                f"  MA_f testigo coef = {self.coef_ma_f:.6f}  (null = -1.0)",
                f"  LR = {lr:.4f}  {pct}",
                f"  Critical values: 10%={crit['10%']}, 5%={crit['5%']}, 1%={crit['1%']}",
            ]
        suffix = ('ESTOCÁSTICA' if self.stochastic
                  else 'DETERMINISTA' if self.deterministic
                  else 'AMBIGUA')
        lines.append(f"  → {suffix}")
        return "\n".join(lines)


def meg(model, frequencies=None) -> list[MEGResult]:
    """
    MEG stochastic seasonality evaluation.

    For each seasonal harmonic frequency f, augments the model with:
    - Individual annual difference factor (ifadf[f] = 1)
    - Free MA_f testigo at f (initial coef = −0.9)
    - Deterministic harmonics (cos/sin) at f are removed from interventions
      because they are absorbed by the unit-root filter.

    Then applies DCD_f on the MA_f testigo:
    - MA_f invertible  (DCD_f rejects H₀: λ₂=−1) → genuine unit root
      → **stochastic** seasonality at f.
    - MA_f non-invertible (DCD_f does not reject) → unit root and testigo
      cancel → **deterministic** seasonality at f.
    - Estimation failure → **ambiguous**.

    Parameters
    ----------
    model : fue.Model, already fitted (.fit() called)
    frequencies : list[int] or None
        Harmonics to test (1-indexed).  None → all f = 1 … s//2 − 1.
        The biannual frequency f = s//2 corresponds to the ``alter``
        intervention and is excluded by default (requires first-order MA
        handling not yet implemented).

    Returns
    -------
    list[MEGResult] — one entry per tested frequency, in order.

    Raises
    ------
    RuntimeError  if model not fitted
    ValueError    if any requested frequency is already stochastic
                  (ifadf[f]=1 in the base model) or out of valid range
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    s = model.series.freq
    if frequencies is None:
        frequencies = list(range(1, s // 2))

    for f in frequencies:
        if not (1 <= f <= s // 2):
            raise ValueError(
                f"freq={f} out of range [1, {s // 2}] for s={s}."
            )
        if len(model.ifadf) > f and model.ifadf[f] == 1:
            raise ValueError(
                f"freq={f} is already stochastic (ifadf[{f}]=1) in the "
                "base model — remove it from the frequencies list."
            )

    from fue.model import FixedFreqFactor

    results = []
    for f in frequencies:
        mc = copy.deepcopy(model)
        mc._result = None

        # Remove deterministic harmonics at f (they cancel with the unit root)
        mc.interventions = [
            itv for itv in mc.interventions
            if not (itv.type in ('cos', 'sin') and itv.harmonic == float(f))
        ]

        # Activate individual annual difference at f
        n_slots = s // 2 + 1
        if len(mc.ifadf) < n_slots:
            mc.ifadf = mc.ifadf + [0] * (n_slots - len(mc.ifadf))
        mc.ifadf[f] = 1

        # Append MA_f testigo (always last in the list)
        testigo_idx = len(mc.ma_f)
        mc.ma_f = list(mc.ma_f) + [FixedFreqFactor(freq=float(f), coef=-0.9, free=True)]

        # Estimate augmented model (C backend, now supports AR+MA_f)
        try:
            mc.fit()
        except Exception:
            results.append(MEGResult(freq=f, coef_ma_f=None, dcd_result=None,
                                     status='ambiguous'))
            continue

        # Apply DCD_f; pick only the result for the testigo we added
        try:
            dcd_results = dcd_f(mc)
            r = next((r for r in dcd_results if r.factor_index == testigo_idx), None)
            if r is None:
                results.append(MEGResult(freq=f, coef_ma_f=None, dcd_result=None,
                                         status='ambiguous'))
                continue
            status_val = 'stochastic' if r.invertible else 'deterministic'
            results.append(MEGResult(freq=f, coef_ma_f=r.coef_free,
                                     dcd_result=r, status=status_val))
        except Exception:
            results.append(MEGResult(freq=f, coef_ma_f=None, dcd_result=None,
                                     status='ambiguous'))

    return results


# ---------------------------------------------------------------------------
# Bloque H — Joint LR test for seasonal harmonic simplification
# ---------------------------------------------------------------------------

@dataclass
class SeasonalSimplificationResult:
    """Result of the joint H₀: cos_k = sin_k = 0 for k in harmonics_tested."""
    harmonics_tested: list[int]    # k values restricted to zero
    components: dict               # k → {'cos', 'sin'} sets — which components exist
    df: int                        # degrees of freedom = Σ |components_k|
    loglik_free: float
    loglik_constrained: float
    lr: float                      # 2·(L_free − L_constrained)
    pvalue: float                  # chi²(df) p-value
    alpha: float = 0.05

    @property
    def rejects(self) -> bool:
        """True when H₀ is rejected — harmonics are jointly significant."""
        return self.pvalue < self.alpha

    def summary(self) -> str:
        crit_90 = sp_stats.chi2.ppf(0.90, df=self.df)
        crit_95 = sp_stats.chi2.ppf(0.95, df=self.df)
        crit_99 = sp_stats.chi2.ppf(0.99, df=self.df)
        ks = ", ".join(f"k={k}" for k in self.harmonics_tested)
        verdict = ("RECHAZA H₀ — armónicos significativos ✗"
                   if self.rejects
                   else "No rechaza H₀ — armónicos pueden eliminarse ✓")
        return "\n".join([
            f"Test RV de simplificación estacional",
            f"  H₀: cos_k = sin_k = 0  para {ks}",
            f"  df = {self.df}",
            f"  logL(libre)       = {self.loglik_free:.4f}",
            f"  logL(restringido) = {self.loglik_constrained:.4f}",
            f"  LR = {self.lr:.4f}",
            f"  Valores críticos χ²({self.df}): 10%={crit_90:.2f}  5%={crit_95:.2f}  1%={crit_99:.2f}",
            f"  p-value = {self.pvalue:.4f}  (α={self.alpha})",
            f"  → {verdict}",
        ])


def seasonal_simplification_test(model, freq_list=None,
                                  alpha: float = 0.05) -> SeasonalSimplificationResult:
    """
    Joint LR test H₀: cos_k = sin_k = 0 for all k in freq_list.

    Fits a restricted model with the specified harmonic parameters fixed to zero
    and computes LR = 2·(L_free − L_restricted) ~ χ²(df), where df = number
    of constrained free parameters (2 per regular harmonic, 1 for Nyquist/alter).

    Parameters
    ----------
    model      : fue.Model, already fitted
    freq_list  : list[int] | None
        Harmonic indices k to restrict. None = all free harmonics in model.
    alpha      : significance level for the ``rejects`` property (default 0.05)

    Returns
    -------
    SeasonalSimplificationResult

    Raises
    ------
    RuntimeError  if model is not fitted
    ValueError    if no free harmonics found, or if freq_list names absent harmonics
    """
    if model._result is None:
        raise RuntimeError("Model has not been fitted — call model.fit() first.")

    freq = model.series.freq

    # Inventory all free harmonics in model
    all_harmonics: dict[int, set] = {}
    for itv in (model.interventions or []):
        t    = itv.type
        om_f = (list(itv.omega_free)
                if (hasattr(itv, "omega_free") and itv.omega_free)
                else [True])
        if t in ("cos", "sin", "alter") and om_f[0]:
            k         = (freq // 2) if t == "alter" else int(round(getattr(itv, "harmonic", 1)))
            component = "cos" if t in ("cos", "alter") else "sin"
            all_harmonics.setdefault(k, set()).add(component)

    if not all_harmonics:
        raise ValueError("No free harmonic (cos/sin/alter) parameters found in model.")

    if freq_list is None:
        freq_list = sorted(all_harmonics.keys())
    else:
        unknown = [k for k in freq_list if k not in all_harmonics]
        if unknown:
            raise ValueError(
                f"Harmonic(s) {unknown} not found in model. "
                f"Available: {sorted(all_harmonics)}"
            )

    # Degrees of freedom = number of free params being restricted
    df = sum(len(all_harmonics[k]) for k in freq_list)

    L_free = float(model._result.loglik)

    # Build restricted model: fix listed harmonics to 0
    mc = copy.deepcopy(model)
    mc._result = None
    test_set = set(freq_list)
    for itv in mc.interventions:
        t = itv.type
        if t not in ("cos", "sin", "alter"):
            continue
        k = (freq // 2) if t == "alter" else int(round(getattr(itv, "harmonic", 1)))
        if k in test_set:
            itv.omega      = [0.0]
            itv.omega_free = [False]
    mc.fit()

    L_const = float(mc._result.loglik)
    lr      = 2.0 * (L_free - L_const)
    pvalue  = float(1.0 - sp_stats.chi2.cdf(max(lr, 0.0), df=df))

    return SeasonalSimplificationResult(
        harmonics_tested=sorted(freq_list),
        components={k: all_harmonics[k] for k in freq_list},
        df=df,
        loglik_free=L_free,
        loglik_constrained=L_const,
        lr=lr,
        pvalue=pvalue,
        alpha=alpha,
    )
