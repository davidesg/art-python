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

Why this layer exists at all
----------------------------
Everything decided here is an INITIAL SPECIFICATION, and that is a different
kind of act from a hypothesis test. Once an adequate model is in hand, the
corresponding hypothesis CAN be tested formally — Shin-Fuller on the order of
integration, DCD on invertibility, the MEG on stochastic seasonality — and this
suite runs all of them, at the end, where they belong.

The reason they cannot be run earlier is the one that governs the whole design:
**a formal hypothesis test on an inadequate model is not a weak test, it is not
a test at all.** Its distribution under the null assumes the model is right, so
on a misspecified model the statistic is answering a question about something
other than the series. Seasonality left in the residuals inflates a standard
error and biases the ADF towards "difference again"; a missing mean puts a drift
where the ARMA orders have to explain it away. The instrument reports, and what
it reports is not about the world.

So the sequence is forced: judgement first, formal tests afterwards. That is
why criterion matters so much in Box-Jenkins, and why the rules in this module
are *criteria* — the plot, the shape of the correlogram, what kind of series
this is, what is obvious — rather than p-values. They are not a cheaper
substitute for the tests that come later. They are what makes those tests mean
something.
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
    # El drift se estima si su t supera esto. 2.0 y no 3.0: no estimar una media
    # que existe deja la deriva en los residuos y ahí contamina TODO lo que viene
    # después --órdenes ARMA, intervenciones, diagnosis--, mientras que estimar
    # una que no existe cuesta un parámetro y sale con t bajo, que se ve.
    "mu_drift": 2.0,
    # Fracción de la varianza del nivel que explica una recta. Por encima de
    # esto, la tendencia ES lo que se ve en el gráfico, y un `recommended_d = 0`
    # sobre una serie así es un contraste fallando por baja potencia, no una
    # serie estacionaria. Calibrado contra los dos lados: las series anuales de
    # precipitación de Cycles —I(0), con pendiente HAC significativa (3.37 y
    # 2.20) pero deriva suave— dan R² de 0.076 y 0.035 y NO se tocan; IPC_ES da
    # 0.910. Es "observar el gráfico" y no "contrastar la pendiente": una
    # pendiente puede ser significativa sin dominar nada.
    "trend_dominates": 0.5,
}


# ---------------------------------------------------------------------------
# Stage decisions
# ---------------------------------------------------------------------------

# Prefijos de nombre que marcan una serie ÍNDICE. Vivían dentro de
# `guided_identification` en mcp_server.py: una regla del analista escrita en la
# capa guiada, invisible para el camino autónomo (BUG-0015). Ahora hay una copia.
_INDEX_PREFIXES = ("ipc", "ipi", "ipp", "cpi", "ppi", "cci",
                   "indice", "índice", "index", "idx", "price")


def decide_domain(ts) -> str:
    """What KIND of series this is: ``"price_index"`` or ``"generic"``.

    The policy protocol took evidence and never DOMAIN, and that gap has now
    produced three defects in a row: μ (BUG-0013), the λ index rule (BUG-0015)
    and the AR(1)/MA(1) tie-break for price series (still in TODO). A rule that
    needs to know what the series IS could not be written, because no argument
    carried the answer.

    This is a SUGGESTION and it is inferred from the name, which is weak
    evidence: a model must not come out different because the file was called
    `IPC_ES` rather than `serie3`. Two things keep that honest —

    * the answer is RECORDED (`PipelineResult.domain`) and announced, never
      applied in silence; and
    * the analyst overrides it (`ClaudePolicy(domain=…)`, `build_model(domain=…)`),
      and a declared domain always wins.

    Declared beats inferred. The inference exists so the autonomous path is not
    left with nothing, not because the name is good evidence.
    """
    name = (getattr(ts, "name", "") or "").lower()
    return "price_index" if name.startswith(_INDEX_PREFIXES) else "generic"


def decide_lambda(boxcox_data: dict, domain: str | None = None) -> float:
    """Box-Cox λ from describe_boxcox(...).data.

    gap = corr(raw) − corr(log); gap ≥ 0 means the log scale reduces the
    mean–std correlation at least as much → log (λ=0).  Otherwise identity.

    **The index rule (BUG-0015).** For `domain="price_index"` the answer is λ=0
    whatever the statistic says, because an index has no natural zero: its base
    year is a convention (2016=100) and only relative changes carry meaning. A
    LEVEL model of an index has no interpretable scale, and against a log input
    in a transfer function it gives a semi-elasticity where the others give an
    elasticity — so the countries cannot go in the same table.

    That rule lived only in the guided MCP layer, so the autonomous path split
    one family of eight CPI indices four in logs and four in levels, on the sign
    of a statistic whose |gap| never exceeded 0.304 and which sat at +0.023 for
    IPC_JP — one hair from flipping. Nothing in the data says those eight differ
    in kind.
    """
    if domain == "price_index":
        return 0.0
    gap = boxcox_data.get("gap", 0.0)
    return 0.0 if gap >= 0 else 1.0


def decide_d(unit_root_data: dict, seasonal: bool | None = None,
             current_d: int = 0, max_step: int | None = 1) -> int:
    """Regular differencing order d from describe_unit_root(...).data.

    Uses the ADF+KPSS recommendation, capped by two rules of the school
    (BUG-0016). Falls back to 1 if the recommendation is absent.

    **A level that trends is evidence against `recommended_d = 0`.** The same low
    power, read the other way round: if the test calls the level stationary while
    the plot climbs, it is the test that is failing, not the series that is
    stationary. So a recommendation of 0 is raised to 1 when a straight line
    explains more than `THRESHOLDS["trend_dominates"]` of the level.

    The criterion is how much of the series the trend IS, not whether a slope
    coefficient is significant, and the difference is not pedantic. Both annual
    precipitation series in `Cycles` — I(0), and the control for exactly this —
    have significant HAC slopes (t = 3.37 and 2.20) and a real drift of some 5 %
    of the mean per century, yet a line explains 0.076 and 0.035 of them. You
    would not call those plots trending; you would call them noisy. IPC_ES gives
    0.910, which is what "the plot climbs" looks like. Testing the slope would
    have differenced the controls; reading the plot does not.

    **Seasonality is settled before d, so it caps d.** The ADF regression carries
    no seasonal terms, so a strong seasonal pattern lands in its residual
    variance, inflates the standard error of the coefficient and biases the test
    towards NOT rejecting the unit root — which reads as "difference again".
    Measured on eight monthly CPI indices, the only two that over-differenced
    were exactly the top two of the seasonality ranking, with a clean break at
    F-HAC ≈ 50. That is the contamination, not a coincidence.

    The signature of a test without power, on the same series: IPC_ES returns
    d=2 starting in January (n=216) and d=1 starting in February (n=215). One
    observation should not change an order of integration.

    So when `seasonal` is True — the caller has already detected seasonality and
    not yet differenced it away — d is capped at 1. `seasonal=None` means "no
    seasonal information available" and caps nothing.

    **One step at a time.** `max_step` defaults to 1, so d never advances by more
    than one in a single decision. The reason is twofold and neither half is a
    matter of caution.

    *First, the question asked from the level is not "how many differences?"* It
    is "is at least one regular difference needed?". Seasonality is normally read
    on a series that has already been differenced once, so from d=0 the question
    of whether a SECOND difference is warranted has never been put. A series may
    well be I(2), but that was not what the test at d=0 examined — least of all
    on a series that may carry seasonality. Jumping 0 → 2 is not answering
    quickly; it is answering a question nobody asked.

    *Second, take the obvious step first.* If d=1 is the obvious reading, d=2 is
    not reachable from d=0 in one move. This cuts both ways: low power can also
    leave the test failing to call for a difference at all, but if the series
    trends and may be seasonal, that is itself a reason to doubt the test rather
    than to believe it, and the obvious step remains d=1. Nominal series in
    economics and finance are almost always d=1, and occasionally d=2.

    **And nothing is lost by starting low, which is the part that settles it.**
    ADF, KPSS and the plot of the series are tools of INITIAL SPECIFICATION, and
    they are sound as such — but they are not the last word on d, and they are
    not asked to be. The real contrast on the order of integration comes at the
    END of the process, on a model that is adequate and correctly specified:
    `dcd_overdiff_regular` and Shin-Fuller, which is exactly where the flow
    already puts them. So capping here does not silently under-difference
    anything. It defers the question to the point where it can be answered
    properly, instead of settling it with an instrument that cannot yet see.

    Over-differencing a price index is not venial: it injects an MA unit root at
    −1, and in a transfer function that destroys the reading of the gain.

    The evidence layer is left alone on purpose — `recommended_d` keeps
    reporting what the tests found. This is a POLICY cap, so the table still
    shows that d=2 was suggested and the cap is visible rather than hidden
    inside the statistic.
    """
    rec = int(unit_root_data.get("recommended_d", 1))

    # Y la duda en la otra dirección: si el contraste dice d=0 sobre una serie
    # cuyo gráfico sube, el que falla es el contraste. Es la misma baja potencia
    # leída al revés, y es Box-Jenkins: se mira la serie, no sólo el estadístico.
    if rec == 0 and float(unit_root_data.get("trend_r2", 0.0)) > THRESHOLDS["trend_dominates"]:
        rec = 1

    d = rec if max_step is None else min(rec, int(current_d) + int(max_step))
    if seasonal:
        d = min(d, 1)
    return max(d, 0)


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
    interpretable measure of that inertia.

    The competing MA(1) carries θ < 0 (that is the sign that puts ρ₁ > 0 in the
    differenced series, which is what makes it compete at all), and an IMA(1,1)
    with θ < 0 is an EWMA whose smoothing constant (1 − θ) exceeds 1 — outside
    the valid range. Its forecast weights on past LEVELS alternate in sign:
    with θ = −0.7 they are 1.700, −1.190, +0.833, −0.583, +0.408, … So it
    forecasts by overshooting the last observation and correcting backwards.
    That is not a defensible generating process for a price index, even though
    the ACF of the differenced series is perfectly compatible with it. (A
    "normal" IMA(1,1) with θ > 0 has all-positive decaying weights — 0.700,
    0.210, 0.063 for θ = 0.3 — the textbook local level.) Confirmed on the IPC_ES case (2002:01–2019:12): AR(1) φ≈0.40 chosen
    over MA(1) θ≈0.43 despite ΔAIC=1.12 nominally favouring MA(1).

    Scope: applies only to price/index series and only under a genuine tie; when
    the statistics *do* discriminate, fit wins. And it must always be STATED —
    "the data prefer X by ΔAIC=…, theory prefers Y because…, you decide". A
    theoretical criterion that is not announced stops being a criterion and
    becomes a bias.

    Since 2026-08-08 the rule is also in the MCP instructions (LLAMADA 4), which
    is what Claude actually reads: before that it lived only here, so it was
    applied when Claude happened to open this file and not otherwise — which is
    exactly the inconsistency the analyst reported. Still not auto-applied in
    the function below, because `decide_orders` does not receive the
    series-domain flag or the candidate fit stats needed to detect the tie
    safely. See TODO §El empate AR(1)/MA(1).
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

def decide_mu(ts, lam: float, d: int, D: int) -> bool:
    """Should the model carry a free mean?

    The question BUG-0013 showed nobody was asking. It has a test, and the test
    is the obvious one: after the Box-Cox and the differencing, is the mean of
    what remains distinguishable from zero?

        t = mean(w) / (sd(w) / sqrt(n))          w = the differenced series

    For `d = 0` that is the level's mean, which a stationary series has and
    which is not optional. For `d >= 1` it is a DRIFT, and for a price index it
    is the monthly inflation rate — the single most interpretable number in the
    model, and the one whose omission leaves a trend in the residuals for the
    ARMA orders and the interventions to explain away.

    Returns True when |t| exceeds `THRESHOLDS["mu_drift"]`.

    Degenerate input (too few observations after differencing, a constant
    series, a Box-Cox that produced non-finite values) returns False, because
    there is then no drift to speak of. Anything else raises: swallowing an
    error into "no mean" is precisely the silent failure this bug was.
    """
    import numpy as np

    yv = np.asarray(getattr(ts, "data", ts), float)
    w = np.log(yv) if abs(float(lam)) < 1e-8 else np.sign(yv) * np.abs(yv) ** float(lam)
    freq = int(getattr(ts, "freq", 1) or 1)
    for _ in range(int(d or 0)):
        w = np.diff(w)
    for _ in range(int(D or 0)):
        w = w[freq:] - w[:-freq]

    if w.size < 3 or not np.all(np.isfinite(w)):
        return False
    sd = float(np.std(w, ddof=1))
    if not sd > 0:
        return False
    t = abs(float(np.mean(w))) / (sd / np.sqrt(w.size))
    return bool(t > THRESHOLDS["mu_drift"])


class Policy:
    """Interface for the per-stage Box-Jenkins-Treadway decisions."""

    def decide_domain(self, ts) -> str:
        """What KIND of series this is. Added for BUG-0015: the protocol took
        evidence and never domain, so a rule that needs to know what the series
        IS had no argument to hold the answer."""
        raise NotImplementedError

    def decide_lambda(self, boxcox_data: dict, domain: str | None = None) -> float:
        raise NotImplementedError

    def decide_d(self, unit_root_data: dict, seasonal: bool | None = None,
                 current_d: int = 0) -> int:
        raise NotImplementedError

    def decide_seasonal_structure(self, seasonality_data: dict, freq: int) -> tuple[int, str, int]:
        raise NotImplementedError

    def decide_orders(self, specs) -> tuple[int, int]:
        raise NotImplementedError

    def decide_mu(self, ts, lam: float, d: int, D: int) -> bool:
        """Free mean or not. Added for BUG-0013: `run_full` did not forget to
        set it -- there was no door through which to ask."""
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

    def decide_domain(self, ts):
        return decide_domain(ts)

    def decide_lambda(self, boxcox_data, domain=None):
        return decide_lambda(boxcox_data, domain)

    def decide_d(self, unit_root_data, seasonal=None, current_d=0):
        return decide_d(unit_root_data, seasonal, current_d)

    def decide_seasonal_structure(self, seasonality_data, freq):
        return decide_seasonal_structure(seasonality_data, freq)

    def decide_orders(self, specs):
        return decide_orders(specs)

    def decide_mu(self, ts, lam, d, D):
        return decide_mu(ts, lam, d, D)

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
                 n_harmonics=None, p=None, q=None, estimate_mu=None,
                 domain=None):
        self.estimate_mu = estimate_mu
        self.domain = domain
        self.lam = lam
        self.d = d
        self.D = D
        self.decision = decision
        self.n_harmonics = n_harmonics
        self.p = p
        self.q = q

    def decide_domain(self, ts):
        """Declarado gana a inferido, siempre. El nombre del fichero es evidencia
        débil: existe para que el camino autónomo no se quede sin nada."""
        return self.domain if self.domain is not None else super().decide_domain(ts)

    def decide_lambda(self, boxcox_data, domain=None):
        return (super().decide_lambda(boxcox_data, domain)
                if self.lam is None else float(self.lam))

    def decide_d(self, unit_root_data, seasonal=None, current_d=0):
        return (super().decide_d(unit_root_data, seasonal, current_d)
                if self.d is None else int(self.d))

    def decide_seasonal_structure(self, seasonality_data, freq):
        D, decision, n_harm = super().decide_seasonal_structure(seasonality_data, freq)
        return (D if self.D is None else int(self.D),
                decision if self.decision is None else self.decision,
                n_harm if self.n_harmonics is None else int(self.n_harmonics))

    def decide_orders(self, specs):
        p, q = super().decide_orders(specs)
        return (p if self.p is None else int(self.p),
                q if self.q is None else int(self.q))

    def decide_mu(self, ts, lam, d, D):
        """What the analyst fixed, or the heuristic. Same shape as the other
        spec-level decisions: the guided path can override, and silence means
        "use the rule" rather than "no mean" -- which is what BUG-0013 was."""
        if self.estimate_mu is not None:
            return bool(self.estimate_mu)
        return super().decide_mu(ts, lam, d, D)
