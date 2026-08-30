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
# Prefijos de nombre que delatan un ÍNDICE. Es la única inferencia que sigue
# apoyada en el nombre, y no por pereza: un índice no tiene firma en el dato que
# lo distinga de cualquier otra magnitud positiva —lo que lo define es que su
# nivel es una convención, y eso no se ve en la serie—. Para todo lo demás la
# inferencia mira el dato (ver `decide_domain`).
_INDEX_PREFIXES = ("ipc", "ipi", "ipp", "cpi", "ppi", "cci",
                   "indice", "índice", "index", "idx", "price",
                   # tipos de cambio efectivos: son índices de base convencional
                   "itcer", "tcer", "reer", "neer", "iter")

# Factor de recorrido a partir del cual una magnitud positiva es, a efectos de
# modelización, multiplicativa. Ver `decide_domain` para el argumento.
RANGO_MULTIPLICATIVO = 3.0


# La banda dentro de la cual el estadístico Box-Cox NO discrimina. Es la misma
# que art imprime al analista ("Δcorr=0.024 < 0.10 → decisión ambigua"), y aquí
# es el interruptor: dentro de ella manda el dominio, fuera manda el dato.
BANDA_AMBIGUA_BOXCOX = 0.10

DOMINIOS = ("price_index", "multiplicative", "ratio", "generic")


def decide_domain(ts) -> str:
    """What KIND of series this is — one of ``DOMINIOS``.

    **BUG-0040: esta taxonomía era BINARIA** (`"price_index"` | `"generic"`) y
    eso resultó ser el arreglo de BUG-0015 quedándose corto: se añadió el
    dominio a la política, pero con las dos únicas categorías que el caso de
    entonces necesitaba. Todo lo que no fuera un índice caía en `"generic"`, y
    ahí λ la decide el signo de `gap` — un estadístico que sobre series cortas es
    ruido.

    Medido sobre PGAS (precio de exportación del gas, 95→500 USD/t): `gap` vale
    −0.024, y con la taxonomía binaria eso daba λ=1. Dos carriles independientes
    —la heurística por lotes y un analista LLM sin contexto previo— cometieron el
    MISMO error, y el segundo lo escribió con todas las letras: *«es un precio
    con cero natural, NO un índice, así que la transformación la decide el
    estadístico»*. No fue un descuido: es la taxonomía leída correctamente. El
    texto que art imprime dice «índice de precios **o magnitud multiplicativa**»,
    pero el código no tenía la segunda categoría.

    Consecuencia medida: con λ=1 ninguno de los seis modelos estimados sobre PGAS
    alcanzó la adecuación — el JB fue de 46.7 a 8.9 y nunca pasó, porque la
    heterocedasticidad que el log elimina reaparece como no-normalidad.

    Las cuatro categorías
    ---------------------
    ``price_index``   Un índice: base convencional, sin cero natural. λ=0 SIEMPRE
                      — un modelo en niveles no tiene escala interpretable.
    ``multiplicative``Magnitud positiva con cero natural que se mueve en
                      proporción: un precio, una cantidad, un agregado
                      monetario. λ=0 POR DEFECTO, y el dato puede desmentirlo.
    ``ratio``         Una participación acotada. λ=0 por defecto con la misma
                      salvedad, y con una limitación que conviene saber: la
                      transformación natural de un cociente acotado es la logit,
                      que la suite no ofrece — λ=0 es la mejor disponible, no la
                      correcta.
    ``generic``       Lo demás: decide el estadístico.

    La inferencia mira el DATO, no el nombre
    ----------------------------------------
    La versión anterior infería del nombre del fichero, y su propio docstring se
    quejaba de ello: *«un modelo no debe salir distinto porque el fichero se
    llamara IPC_ES en vez de serie3»*. El nombre se conserva para los índices
    —ahí el prefijo es informativo y no hay firma en el dato que los distinga—
    pero lo demás se decide midiendo:

    * valores no positivos ⇒ ``generic``: el log no está definido, no hay nada
      que discutir;
    * todo dentro de (0, 1) ⇒ ``ratio``;
    * recorrido máx/mín ≥ ``RANGO_MULTIPLICATIVO`` ⇒ ``multiplicative``. El
      umbral es una convención, y ésta es su razón: sobre un recorrido de factor
      R, un modelo de varianza aditiva afirma que la innovación tiene la misma
      magnitud absoluta en los dos extremos. Con R ≥ 3 eso es implausible para
      una magnitud económica positiva — en PGAS serían los mismos USD/t de
      sorpresa a 95 que a 500.

    Sigue siendo una SUGERENCIA: se registra en `PipelineResult.domain`, se
    anuncia, y **lo declarado gana siempre** (`ClaudePolicy(domain=…)`,
    `build_model(domain=…)`).
    """
    import numpy as _np
    name = (getattr(ts, "name", "") or "").lower()
    if name.startswith(_INDEX_PREFIXES):
        return "price_index"
    try:
        y = _np.asarray(getattr(ts, "data", []), dtype=float)
        y = y[_np.isfinite(y)]
        if y.size == 0 or _np.min(y) <= 0.0:
            return "generic"
        if _np.max(y) < 1.0:
            return "ratio"
        if _np.max(y) / _np.min(y) >= RANGO_MULTIPLICATIVO:
            return "multiplicative"
    except Exception:
        return "generic"
    return "generic"


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
    # BUG-0040. Para una magnitud multiplicativa o un cociente, el log es el
    # punto de partida — pero a diferencia del índice, el dato PUEDE desmentirlo.
    # El interruptor es la banda dentro de la cual el estadístico no discrimina,
    # la misma que art ya imprime al analista: dentro, decide el dominio; fuera,
    # decide el dato. Sobre PGAS gap=−0.024 cae de lleno dentro y el signo de ese
    # número era lo único que empujaba a λ=1.
    if domain in ("multiplicative", "ratio") and abs(gap) < BANDA_AMBIGUA_BOXCOX:
        return 0.0
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


def decide_seasonal_orders(specs) -> tuple[int, int]:
    """Seasonal (P, Q) from suggest_orders(...) — the top-ranked ACF/PACF match.

    The sibling of `decide_orders`, and the reason it exists is BUG-0031.

    `suggest_orders` searches over (p, q, P, Q) with P_max = Q_max = 1, so every
    spec it ranks CARRIES a seasonal pair. `decide_orders` returned only the
    regular `(p, q)`, and `run_full` built its `ModelSpec` without touching `P`
    or `Q` — which left them at 0. The consequence was not a worse model but an
    UNREACHABLE one: on a series whose identification puts a P=1 spec in first
    place, the autonomous lane estimated that same spec **without** the seasonal
    operator, and the residuals were not white noise. The engine was never at
    fault — `_make_model` has built the D=0 "harmonics + stationary seasonal
    AR/MA" combination all along (pipeline.py, `ar_s_val` under `if D == 0`).
    What was missing was the wire from the policy to the spec.

    Why a separate function rather than widening `decide_orders` to a 4-tuple:
    the regular and the seasonal pair are decided on different evidence (the low
    lags of the ACF/PACF vs. the lags at multiples of s), the guided lane
    confirms them as separate acts, and `decide_orders` carries a documented
    domain tie-break of its own that has nothing to say about P and Q.

    THE P≥1 AND Q≥1 GUARD. The fue C backend aborts when a seasonal AR and a
    seasonal MA are both free in the same model (see `_make_model`'s docstring
    and fue/TODO.md, "AR_s+MA_s"). `suggest_orders` does rank (P=1, Q=1) specs —
    it ranks on correlogram similarity and knows nothing about the backend — so
    this function must never return that pair. When the top spec asks for both,
    the seasonal AR is kept and the seasonal MA dropped: at the annual lags an
    AR nests the persistent decay that a seasonal MA can only cut off at lag s,
    so it is the safer of the two to keep, and an over-rich AR shows up as a
    quasi-cancellation the DCD can then test — a dropped MA leaves nothing to
    look at. The choice is a CONSTRAINT, not a criterion, so it is announced.
    """
    if not specs:
        return 0, 0
    top = specs[0]
    P = int(getattr(top, "P", 0) or 0)
    Q = int(getattr(top, "Q", 0) or 0)
    if P >= 1 and Q >= 1:
        # Backend constraint, not a modelling judgement — see docstring.
        Q = 0
    return P, Q


# ---------------------------------------------------------------------------
# El OBJETIVO del modelo, y la ruta estacional
# ---------------------------------------------------------------------------

OBJETIVOS = ("univariante", "multivariante", "estructural")

OBJETIVO_POR_DEFECTO = "univariante"


def decide_seasonal_route(meg_verdicts, b2_seasonal_invertible,
                          objetivo: str = OBJETIVO_POR_DEFECTO,
                          b1_ok: bool = True, b2_ok: bool = True):
    """Elige entre B1 (D=0 + armónicos) y B2 (D=1) **por contraste, no por decreto**.

    El problema, y por qué no basta con un default
    ----------------------------------------------
    Box-Jenkins canónico: detectada la estacionalidad, `D=1`, y de ahí (p,q,P,Q).
    La extensión de Treadway: partir de `D=0` + armónicos como HIPÓTESIS DE
    TRABAJO y contrastarla con el MEG (Abraham-Box 1978; Treadway y Gallego
    después). En econometría, y sobre todo cuando la serie va a entrar en un
    sistema multivariante, la práctica es `D=0` con armónicos o dummies.

    Tres tradiciones, y la elección no está en los datos: está en para qué es el
    modelo. Pero tampoco es ARBITRARIA, y ahí está la salida.

    Los dos caminos son contrastables, y forman PAR
    ----------------------------------------------
    * B1 se contrasta con el **MEG**: ¿alguna frecuencia es estocástica?
    * B2 se contrasta desde el otro lado, con el **DCD_f** sobre su MA
      estacional: si se apila en la frontera de no invertibilidad, la ∇ₛ sobraba
      y la estacionalidad era determinista.

    Nulas opuestas sobre la misma pregunta — la misma estructura que
    Shin-Fuller/DCD en f=0. Habiendo par, elegir por convención es justo lo que
    el método evita en todos los demás nodos.

    La asimetría que decide, y no es de tradición sino de EXPRESIVIDAD
    -----------------------------------------------------------------
    `D=1` impone raíces unitarias en TODAS las frecuencias estacionales a la vez.
    El instrumento fino no es `D`, es `ifadf` por frecuencia — y a `ifadf` sólo
    se llega desde B1, vía MEG. Por tanto:

    * **B1 puede llegar a B2.** Medido sobre RATIO (Gasto/PIB Bolivia): el MEG
      dictó f=1 y después f=2, y el operador total quedó en
      `(1−B)(1+B²)(1+B) = ∇₄` — el modelo de Box-Jenkins, pero CON la evidencia
      de por qué, y sabiendo que cada frecuencia lo era por separado.
    * **B2 no puede llegar a un B1 mixto.** Si la verdad es «f=1 estocástica,
      f=2 determinista», `D=1` no lo representa y ningún contraste posterior lo
      recupera.

    Y el coste del error es asimétrico: empezar en B1 cuando la verdad es B2
    cuesta iteraciones y el MEG lo encuentra; empezar en B2 cuando la verdad es
    B1 mete una raíz unitaria estacional espuria ANTES de identificar el ARMA, y
    para cuando el DCD_f lo delata la identificación ya se hizo sobre una serie
    sobrediferenciada.

    Parameters
    ----------
    meg_verdicts  dict {freq: "stochastic"|"deterministic"} del MEG sobre B1, o
                  None/{} si no se pudo correr.
    b2_seasonal_invertible
                  True si el MA estacional de B2 es invertible (la ∇ₛ es
                  genuina), False si se apila en la frontera (sobraba), None si
                  no se pudo contrastar.
    objetivo      para qué es el modelo — rompe el empate cuando los contrastes
                  no deciden, y VETA B2 en el caso multivariante.
    b1_ok, b2_ok  si la diagnosis de cada rama es adecuada.

    Returns
    -------
    (ruta, razón) con ruta ∈ {"B1", "B2"}.
    """
    obj = (objetivo or OBJETIVO_POR_DEFECTO).strip().lower()
    if obj not in OBJETIVOS:
        obj = OBJETIVO_POR_DEFECTO

    # 0. La adecuación manda sobre todo lo demás.
    if b1_ok and not b2_ok:
        return "B1", ("B2 no pasa la diagnosis y B1 sí. La adecuación decide "
                      "antes que cualquier preferencia de ruta.")
    if b2_ok and not b1_ok:
        return "B2", ("B1 no pasa la diagnosis y B2 sí. La adecuación decide "
                      "antes que cualquier preferencia de ruta.")

    # 1. El objetivo multivariante VETA B2, y no por gusto: una raíz unitaria
    #    estacional dentro de una cointegración es otro problema —y mucho más
    #    duro—, y además las series de un sistema tienen que llevar el MISMO
    #    tratamiento estacional o sus órdenes de integración no son comparables.
    if obj == "multivariante":
        return "B1", ("objetivo=multivariante: las raíces unitarias estacionales "
                      "complican la cointegración y exigen tratamiento idéntico "
                      "en todas las series del sistema. B1 con armónicos es la "
                      "especificación que mantiene comparables los órdenes de "
                      "integración. No es preferencia: es requisito del uso.")

    # 2. Los contrastes, cuando hablan.
    v = dict(meg_verdicts or {})
    if v:
        estocasticas = [f for f, r in v.items() if r == "stochastic"]
        if not estocasticas:
            return "B1", ("el MEG no encuentra ninguna frecuencia estocástica: "
                          "la estacionalidad es determinista y la ∇ₛ de B2 "
                          "sobrediferenciaría.")
        if len(estocasticas) == len(v):
            if b2_seasonal_invertible is False:
                return "B1", ("el MEG marca todas las frecuencias estocásticas "
                              "pero el MA estacional de B2 se apila en la "
                              "frontera: su ∇ₛ sobra. Los dos contrastes no "
                              "coinciden y B1, que es reformulable frecuencia a "
                              "frecuencia, es donde se puede seguir mirando.")
            return "B2", ("todas las frecuencias salen estocásticas y el MA "
                          "estacional de B2 es invertible: los dos lados "
                          "coinciden, y B2 es la forma parsimoniosa de lo mismo. "
                          "B1 llegaría al mismo operador con más parámetros.")
        return "B1", (f"el MEG separa las frecuencias: estocástica(s) "
                      f"{sorted(estocasticas)} y determinista(s) "
                      f"{sorted(f for f in v if f not in estocasticas)}. "
                      "Un caso MIXTO sólo lo representa B1 con `ifadf` por "
                      "frecuencia; D=1 impone la raíz unitaria en todas a la vez.")

    # 3. Sin contrastes utilizables, decide el objetivo — y se dice.
    if obj == "univariante":
        return "B2", ("los contrastes no deciden y objetivo=univariante: para "
                      "previsión el patrón que se adapta suele predecir mejor, y "
                      "B2 es la forma canónica de Box-Jenkins.")
    return "B1", ("los contrastes no deciden y objetivo=estructural: B1 deja los "
                  "componentes estacionales explícitos y legibles, que es para lo "
                  "que se pidió el modelo.")


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


def decide_interventions(extreme, existing_ats,
                        offset: int = 0) -> list[tuple[int, str]]:
    """Which interventions to add this round, given the residual diagnosis.

    Parameters
    ----------
    extreme       list of (obs_1based, z) extreme residuals (diag.extreme).
                  **Los índices son de la serie de RESIDUOS**, no de la original.
    existing_ats  iterable of 0-based positions already covered by interventions
    offset        `d + D*s` — cuántas observaciones se pierden al diferenciar,
                  que es exactamente lo que separa el origen de la serie de
                  residuos del de la serie original.

    Returns a list of (at_0based, form) — form chosen by decide_form — ordered
    by descending |z|; positions already covered are skipped.

    **BUG-0030.** Esto hacía `at_0 = obs - 1`, que sólo sería correcto si las dos
    series arrancaran a la vez. La serie de residuos empieza `d + D*s`
    observaciones después, así que TODA intervención del carril autónomo caía ese
    desfase ANTES del anómalo que la disparó — un trimestre con d=1, trece
    períodos en un mensual con D=1.

    Y el defecto era estructural, no aritmético: esta función no recibía `d` ni
    `D`, así que no podía hacer la conversión aunque quisiera. De ahí el
    parámetro nuevo.

    Lo que lo hacía silencioso: un pulso de NIVEL colocado un período antes
    ajusta la imagen especular del correcto. Medido — ω = +4.347 (t=+4.57) mal
    colocado frente a ω = −4.353 (t=−4.58) bien colocado, con Δ logL = 0.03.
    Signo invertido, magnitud igual, verosimilitud indistinguible. Nada en la
    diagnosis lo delata.
    """
    ext_obs = {obs for obs, _ in extreme}
    already = set(existing_ats)
    new: list[tuple[int, str]] = []
    for obs, z in sorted(extreme, key=lambda x: -abs(x[1])):
        at_0 = obs - 1 + int(offset)
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

    def decide_seasonal_orders(self, specs) -> tuple[int, int]:
        raise NotImplementedError

    def decide_seasonal_route(self, meg_verdicts, b2_seasonal_invertible,
                              objetivo="univariante", b1_ok=True, b2_ok=True):
        raise NotImplementedError

    def decide_mu(self, ts, lam: float, d: int, D: int) -> bool:
        """Free mean or not. Added for BUG-0013: `run_full` did not forget to
        set it -- there was no door through which to ask."""
        raise NotImplementedError

    def decide_form(self, target_obs: int, extreme_obs) -> str:
        raise NotImplementedError

    def decide_interventions(self, extreme, existing_ats, offset: int = 0) -> list:
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

    def decide_seasonal_orders(self, specs):
        return decide_seasonal_orders(specs)

    def decide_seasonal_route(self, meg_verdicts, b2_seasonal_invertible,
                              objetivo="univariante", b1_ok=True, b2_ok=True):
        return decide_seasonal_route(meg_verdicts, b2_seasonal_invertible,
                                     objetivo, b1_ok, b2_ok)

    def decide_mu(self, ts, lam, d, D):
        return decide_mu(ts, lam, d, D)

    def decide_form(self, target_obs, extreme_obs):
        return decide_form(target_obs, extreme_obs)

    def decide_interventions(self, extreme, existing_ats, offset: int = 0):
        return decide_interventions(extreme, existing_ats, offset)

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
                 domain=None, P=None, Q=None):
        self.estimate_mu = estimate_mu
        self.domain = domain
        self.lam = lam
        self.d = d
        self.D = D
        self.decision = decision
        self.n_harmonics = n_harmonics
        self.p = p
        self.q = q
        # BUG-0031: el par estacional se confirma igual que el regular.
        self.P = P
        self.Q = Q

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

    def decide_seasonal_orders(self, specs):
        P, Q = super().decide_seasonal_orders(specs)
        return (P if self.P is None else int(self.P),
                Q if self.Q is None else int(self.Q))

    def decide_seasonal_route(self, meg_verdicts, b2_seasonal_invertible,
                              objetivo="univariante", b1_ok=True, b2_ok=True):
        """La ruta declarada gana, como todo lo demás en esta política.

        `decision` es el campo que la lleva: "B1"/"B2" la fijan; "A" no aplica
        (no hay estacionalidad que enrutar) y cualquier otra cosa deja decidir
        al contraste."""
        if self.decision in ("B1", "B2"):
            return self.decision, "ruta fijada por el analista"
        return super().decide_seasonal_route(meg_verdicts, b2_seasonal_invertible,
                                             objetivo, b1_ok, b2_ok)

    def decide_mu(self, ts, lam, d, D):
        """What the analyst fixed, or the heuristic. Same shape as the other
        spec-level decisions: the guided path can override, and silence means
        "use the rule" rather than "no mean" -- which is what BUG-0013 was."""
        if self.estimate_mu is not None:
            return bool(self.estimate_mu)
        return super().decide_mu(ts, lam, d, D)
