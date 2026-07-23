"""
art.policy — single home for the Box-Jenkins-Treadway *decision rules*.

Architectural role (see docs/ARCHITECTURE.md §6): the suite cleanly separates
three concerns —

    evidence   (describe.py: turns engines into Description{summary,figure,data})
    policy     (THIS module: turns evidence into decisions)
    execution  (pipeline.py: builds, fits, diagnoses a spec)

These functions are the *default heuristic policy*. They are consumed two ways:

  * Autonomous mode — applied directly (Claude/the pipeline takes the decision).
  * Guided mode — surfaced as a *suggestion* in Description.recommendation; the
    analyst (with Claude) may confirm or override.

Same rule, two consumption modes → no drift between the guided and autonomous
paths.  Every function is PURE: it takes evidence (plain dicts / values) and
returns a decision, with no I/O and no dependency on describe.py or fue.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Centralised thresholds — the one place |z| cut-offs are defined.
# ---------------------------------------------------------------------------
# Rationale for the spread (was scattered, undocumented, across mcp_server.py):
#   user      3.5  conservative, user-facing scans (intervention_analysis)
#   autonomous3.0  tighter, so the automated cycle does not leave marginal
#                  outliers unmodelled
#   autoscan  2.5  sensitive, flags marginal outliers DURING the modeling cycle
#   form      2.5  consecutivity test to choose step vs pulse
#   autoselect2.0  wide net when auto-picking the most extreme residual
THRESHOLDS = {
    "outlier_user": 3.5,
    "outlier_autonomous": 3.0,
    "outlier_autoscan": 2.5,
    "intervention_form": 2.5,
    "intervention_autoselect": 2.0,
}


# ---------------------------------------------------------------------------
# Stage decisions
# ---------------------------------------------------------------------------

def decide_lambda(boxcox_data: dict) -> float:
    """Box-Cox λ from describe_boxcox(...).data.

    gap = corr(raw) − corr(log); gap ≥ 0 means the log scale reduces the
    mean–std correlation at least as much → log (λ=0).  Otherwise identity.
    """
    gap = boxcox_data.get("gap", 0.0)
    return 0.0 if gap >= 0 else 1.0


def decide_d(unit_root_data: dict) -> int:
    """Regular differencing order d from describe_unit_root(...).data.

    Uses the ADF+KPSS recommendation; falls back to 1 if absent.
    """
    return int(unit_root_data.get("recommended_d", 1))


def decide_seasonal_structure(seasonality_data: dict, freq: int) -> tuple[int, str, int]:
    """Seasonal structure from describe_seasonality(...).data.

    Returns (D, decision, n_harmonics):
      D           seasonal differencing (0 for B1 deterministic, 1 for B2)
      decision    "A" (no seasonality) | "B1" (deterministic) | "B2" (stochastic)
      n_harmonics full deterministic spec = freq//2 − 1 cos/sin pairs (the Nyquist
                  harmonic is covered separately by 'alter'); 0 when decision="A".
    """
    D = int(seasonality_data.get("recommended_D", 0))
    decision = seasonality_data.get("decision", "B1")
    n_harmonics = max(freq // 2 - 1, 0) if decision != "A" else 0
    return D, decision, n_harmonics


def decide_orders(specs) -> tuple[int, int]:
    """Regular (p, q) from suggest_orders(...) — the top-ranked ACF/PACF match.

    *specs* is the ordered list returned by art.model_detection.suggest_orders;
    each element has .p and .q.  Falls back to (0, 1) — a plain MA(1) — when no
    suggestion is available.

    Heuristic — PRICE/INDEX series, AR(1) vs MA(1) tie-break
    -------------------------------------------------------
    On a price/index series (CPI/IPC, modelled in logs with d=1, i.e. the
    differenced series is monthly inflation), identification often ties between
    AR(1) and MA(1): a single dominant spike at lag 1 in both ACF and PACF, and
    the two candidates only separated by a sliver of ACF/PACF similarity. When
    the *fit* also fails to discriminate — ΔAIC < 2, equal parsimony, both pass
    Q-test and Jarque-Bera, near-identical residual ACF/PACF — break the tie in
    favour of **AR(1)** (p=1, q=0).

    Rationale: in a statistical tie, economic theory should decide. AR(1) on
    inflation (π̃ₜ = φ·π̃ₜ₋₁ + aₜ) has a positive, geometrically decaying impulse
    response — i.e. *inflation persistence / inertia*, a robust, theoretically
    grounded regularity (staggered Calvo/Taylor pricing, indexation, adaptive
    expectations; Fuhrer, Stock-Watson, Pivetta-Reis). φ is a directly
    interpretable measure of that inertia. MA(1) implies only ~1 month of memory
    and, in AR(∞) form, sign-alternating coefficients with no clean structural
    story. Confirmed on the IPC_ES case (2002:01–2019:12): AR(1) φ≈0.40 chosen
    over MA(1) θ≈0.43 despite ΔAIC=1.12 nominally favouring MA(1).

    Scope: applies only to price/index series and only under a genuine tie; when
    the statistics *do* discriminate, fit wins. Currently a documented guided-mode
    rule (the analyst, with Claude, applies it); not yet auto-applied here because
    decide_orders does not receive the series-domain flag or the candidate fit
    stats needed to detect the tie safely.
    """
    if specs:
        top = specs[0]
        return int(top.p), int(top.q)
    return 0, 1


def decide_form(target_obs: int, extreme_obs) -> str:
    """Choose the intervention form for an outlier at *target_obs* (1-based).

    "step" if an adjacent observation is also extreme — a consecutive run of
    extremes signals a permanent level shift — otherwise an isolated "pulse".
    *extreme_obs* is the set/iterable of 1-based observations flagged extreme.

    Single source of truth shared by the autonomous loop (decide_interventions)
    and the guided tool (suggest_intervention_form).
    """
    ext = set(extreme_obs)
    has_consec = (target_obs - 1 in ext) or (target_obs + 1 in ext)
    return "step" if has_consec else "pulse"


def decide_interventions(extreme, existing_ats) -> list[tuple[int, str]]:
    """Which interventions to add this round, given the residual diagnosis.

    Parameters
    ----------
    extreme       list of (obs_1based, z) extreme residuals (diag.extreme)
    existing_ats  iterable of 0-based positions already covered by interventions

    Returns a list of (at_0based, form) — form chosen by decide_form — ordered
    by descending |z|; positions already covered are skipped.
    """
    ext_obs = {obs for obs, _ in extreme}
    already = set(existing_ats)
    new: list[tuple[int, str]] = []
    for obs, z in sorted(extreme, key=lambda x: -abs(x[1])):
        at_0 = obs - 1
        if at_0 in already:
            continue
        new.append((at_0, decide_form(obs, ext_obs)))
    return new


def should_stop(clean: bool, n_extreme: int) -> bool:
    """Stop the outlier-addition cycle when the diagnosis is clean or there are
    no extreme residuals left to model."""
    return bool(clean or n_extreme == 0)


# ---------------------------------------------------------------------------
# Swappable policy objects
# ---------------------------------------------------------------------------
# The module-level functions above are the canonical heuristic implementation.
# The classes below wrap them so the execution engine (pipeline.run_full) can
# take a *policy object* and the philosophy becomes explicit in code:
#
#   autonomous mode → DefaultPolicy   (the heuristic decides)
#   guided mode     → ClaudePolicy    (the analyst / Claude decides; heuristic
#                                       fills any choice not explicitly given)
#
# Only *who supplies each decision* differs — both run through the same engine.

class Policy:
    """Interface for the per-stage Box-Jenkins-Treadway decisions."""

    def decide_lambda(self, boxcox_data: dict) -> float:
        raise NotImplementedError

    def decide_d(self, unit_root_data: dict) -> int:
        raise NotImplementedError

    def decide_seasonal_structure(self, seasonality_data: dict, freq: int) -> tuple[int, str, int]:
        raise NotImplementedError

    def decide_orders(self, specs) -> tuple[int, int]:
        raise NotImplementedError

    def decide_form(self, target_obs: int, extreme_obs) -> str:
        raise NotImplementedError

    def decide_interventions(self, extreme, existing_ats) -> list:
        raise NotImplementedError

    def should_stop(self, clean: bool, n_extreme: int) -> bool:
        raise NotImplementedError


class DefaultPolicy(Policy):
    """The default heuristic policy — delegates to the module-level rules.

    This is the policy the autonomous pipeline (build_model / batch_build) runs:
    every decision is taken by the BJT heuristics defined in this module.
    """

    def decide_lambda(self, boxcox_data):
        return decide_lambda(boxcox_data)

    def decide_d(self, unit_root_data):
        return decide_d(unit_root_data)

    def decide_seasonal_structure(self, seasonality_data, freq):
        return decide_seasonal_structure(seasonality_data, freq)

    def decide_orders(self, specs):
        return decide_orders(specs)

    def decide_form(self, target_obs, extreme_obs):
        return decide_form(target_obs, extreme_obs)

    def decide_interventions(self, extreme, existing_ats):
        return decide_interventions(extreme, existing_ats)

    def should_stop(self, clean, n_extreme):
        return should_stop(clean, n_extreme)


class ClaudePolicy(DefaultPolicy):
    """Policy seeded with analyst/Claude-confirmed choices.

    Any spec-level decision passed at construction (λ, d, D, decision,
    n_harmonics, p, q) is returned as given; everything else — and the
    per-round loop decisions (form, interventions, stopping) — falls back to
    the DefaultPolicy heuristic. This lets the guided path reuse the same
    execution engine as the autonomous one, differing only in who decided.
    """

    def __init__(self, lam=None, d=None, D=None, decision=None,
                 n_harmonics=None, p=None, q=None):
        self.lam = lam
        self.d = d
        self.D = D
        self.decision = decision
        self.n_harmonics = n_harmonics
        self.p = p
        self.q = q

    def decide_lambda(self, boxcox_data):
        return super().decide_lambda(boxcox_data) if self.lam is None else float(self.lam)

    def decide_d(self, unit_root_data):
        return super().decide_d(unit_root_data) if self.d is None else int(self.d)

    def decide_seasonal_structure(self, seasonality_data, freq):
        D, decision, n_harm = super().decide_seasonal_structure(seasonality_data, freq)
        return (D if self.D is None else int(self.D),
                decision if self.decision is None else self.decision,
                n_harm if self.n_harmonics is None else int(self.n_harmonics))

    def decide_orders(self, specs):
        p, q = super().decide_orders(specs)
        return (p if self.p is None else int(self.p),
                q if self.q is None else int(self.q))
