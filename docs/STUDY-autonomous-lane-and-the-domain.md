# The autonomous lane and the domain — a study

**Status: a study to be argued with, not a plan.** Written 2026-10-02, from an
evaluation of the autonomous lane on the two series of the pass-through ladder
test (WTI and IPC_ES, `levels_2002_2019.csv`, objective MULTIVARIANTE). The
analyst played by the LLM followed the protocol node by node; the analyst
proper then evaluated the result. This document records what failed, why, and
what art could change. Nothing here is implemented.

It builds on `DISENO-dominio-en-los-ordenes.md`, with its decisions of
2026-09-30 (§10.bis), and on the protocol's own rule for the AR(1)/MA(1) tie
(`_INSTRUCTIONS`, «EL EMPATE AR(1) vs MA(1), Y CÓMO SE ROMPE»).

---

## 1. What happened

| | the lane's final model | what the tie looked like |
|---|---|---|
| WTI | ARIMA(0,1,1), θ = −0.155 (shown as `(1 + 0.155B)`), μ = 1.18 %/month, two multi-ω steps (10/2008, 12/2014) | AR(1) and MA(1) at ΔAIC 0.33, one parameter each, both adequate; the identifier's list put an AR(3) first, built on outlier-driven lags |
| IPC_ES | ARIMA(0,1,1), θ = −0.425, five harmonic pairs + Nyquist, μ, a VAT step (9/2012) | the identifier flagged a GENUINE tie MA(1)/AR(1), with the card (materiality 0.08 σ); fitted, ΔAIC 0.85 for MA(1) |

In both series, in a genuine AR/MA tie on a price series, the lane chose the
**MA(1) with θ < 0**. For IPC_ES the reason it recorded was
`criterio="estadístico"`. For WTI it cited Working (1960) without examining
the forecast function, and without weighing the alternative mechanism (§2).

Then, in IPC_ES, the formal tests ran on the MA(1) model:
- with no free AR, Shin-Fuller was not applicable;
- the DCD over-differencing side alone gave LR 21 against a printed critical
  value of 1.94;
- art warned twice that a one-sided reading is not conclusive;
- the lane estimated d = 2 anyway. Its MA then had a root at 0.964, which the
  lane read correctly as over-differencing, but then argued over against the
  DCD.

The analyst's evaluation:

> «El problema radica en la elección de un MA(1) con parámetro negativo que
> no tiene sentido» — and d was never the question: with an AR the
> Shin-Fuller side is available and does not reject d = 1, the AR is small,
> and the d = 2 alternative has an MA root at the invertibility boundary.

## 2. What the MA(1) with θ < 0 implies, and why it fails the domain

Box-Jenkins convention, (1 − θB). For ARIMA(0,1,1) with θ < 0:
- **ρ₁ = −θ/(1+θ²) > 0** in the differences;
- **the forecast function** is ŷ_T(h) = y_T − θ·a_T = y_T + |θ|·a_T at every
  horizon;
- **the weights on past levels**, πⱼ = (1−θ)θ^{j−1}, alternate in sign
  (1.425, −0.606, +0.258, … for θ = −0.425), and the "smoothing constant"
  1 − θ exceeds 1. It is not an exponential smoothing: it extrapolates the last
  surprise and represents itself by overshooting and correcting.

The protocol already says this, for price indices:
- the MA(1) with θ < 0 «no es un proceso generador defendible»;
- in a tie with ΔAIC < 2 it is broken for **AR(1)**, whose impulse response is
  positive and geometrically decreasing: inflationary inertia, with theory
  behind it.

**IPC_ES.** The `dominio` node declared persistence (indexation, inertia) and a
stochastic mean of inflation. The MA(1) with θ = −0.425 implies:
- one month of memory: 42 % of a surprise passes to the next month and
  vanishes;
- then a FIXED mean of inflation (1.8 % a year) forever.

That is the opposite of both declared expectations. The AR(1) (φ = 0.40) at
least carries geometric persistence, it is what the protocol's rule picks, and
it keeps the Shin-Fuller side of the boundary tests.

**WTI.** The lane justified the MA(1) by Working (1960): the monthly average
of a daily random walk has ρ₁ ≈ +0.25 and nothing after, an MA(1) with
θ ≈ −0.27. That is one mechanism, not THE mechanism, and it is the weaker one:

| | MA(1), θ < 0 | AR(1), φ > 0 |
|---|---|---|
| continuation | exactly one month, then nothing | decays geometrically (φ, φ², …) |
| ρ₂ | 0 | φ² ≈ 0.02 |
| forecast weights | infinite, alternating, on an unobserved innovation | finite (two), on the last observed change |
| mechanism | aggregation (Working): mechanical, and only if daily prices are a pure random walk | gradual adjustment: inventories, a supply that answers with a lag, OPEC policy, the momentum documented in commodities |
| formal tests | no Shin-Fuller | the pair complete |

What the comparison shows:
- **Both imply momentum** (ρ₁ > 0), and both forecast a little above the last
  level. The AR(1) also puts a negative weight on a past level
  (y_t = 1.148·y_{t−1} − 0.148·y_{t−2}), so "overshooting" does not separate
  them.
- **The data cannot decide.** ρ₂ = 0.02 against 0 is undetectable with
  n = 214 (the s.e. of r₂ is about 0.07), and the materiality is negligible.
  The choice is the domain's.
- **The economic mechanism asks for a decay.** For crude oil, supply-demand
  imbalances that persist for months are a more substantive mechanism than
  aggregation, and they imply an AR.
- **A weak hint from the data:** the estimated ρ₁ (0.15) is below Working's
  0.25, where aggregation of a random walk alone would put it. It is weak,
  because the interventions absorb part of it.
- **The practical reasons point the same way:** finite and observable weights,
  the boundary-test pair complete, and for mtram a finite prewhitening filter
  (1 − φB)∇.

So the protocol's rule (a price → AR(1) in a tie) holds for WTI too. Working's
MA(1) would need two things: a pure aggregation mechanism, and evidence that
the underlying daily price is a random walk. A check that would settle it
without theory, left for later: if end-of-month (or daily) prices, not
averaged, still show ρ₁ ≈ 0.15, the persistence is economic and the model is
an AR.

What clearly fails WTI's domain besides the order is the drift: +1.18 %/month,
about +14 % a year inherited by every forecast. The lane accepted it to clear
the residual-mean criterion, after two permanent steps took the falls and left
the recoveries in the noise.

## 3. Why it happened: three failures

### F1 — A decision failure: the tie was broken by statistics, not by the domain

The `dominio` node is a preregistration, and the tie is exactly where it is
meant to decide. Yet:
- `guion_node(criterio="estadístico")` is accepted in a genuine tie with
  ΔAIC < 2, the very case the protocol's rule covers. art only checks
  `criterio="dominio"` (that a declared expectation exists); it checks nothing
  for the other two values;
- the protocol's AR(1)/MA(1) rule lives in `_INSTRUCTIONS` as prose. Nothing in
  the tools applies it, warns when it is not applied, or says when it is out of
  scope (an averaged commodity price).

### F2 — An instrument failure: the card exists where the decision is not

- `describe.py` generates the card of implied dynamics ONLY inside the
  identification listing, ONLY when the similarity band (0.04) holds more than
  one candidate, and ONLY with the identifier's light coefficients.
- In WTI it did not appear (gap 0.071). In IPC_ES it did, and its MA(1) column
  said «infinitos, alternan sin fin», but on light coefficients and three calls
  before the decision.
- Decision 2 of §10.bis already says the card is generated «in the comparison
  of estimated models (ΔAIC < 2)». **That half is not implemented.**
- Nothing confronts the declared expectations with the chosen model: they are
  stored as free text and never read again by the engine.

### F3 — A reading failure: a one-sided boundary test was read as decisive

- `formal_tests` says it in its own output: «Sin par confirmatorio … el
  veredicto de arriba es UN SOLO lado … Antes de mover `d`, estima el candidato
  d+1».
- What it does not say is that the missing side is a consequence of the ORDER
  choice: an MA-only model has no Shin-Fuller. Its candidate is the AR model
  already estimated in the tie.
- The lane estimated d + 1 instead, which is the more expensive branch and the
  one whose reading is ambiguous: an MA root near 1 is over-differencing if it
  is at 1, and a stochastic mean if it is below.

## 4. Proposals

### P1 — The AR/MA tie in price series is decided by a rule the tools apply

In `guion_node(nodo="ordenes")`, and in the autonomous lane's flow:
- When the `dominio` node is `price_index` or `multiplicative`, and the decision
  is between an AR(p) and an MA(q) with θ < 0 at ΔAIC < 2 (or inside the
  similarity band):
  - `criterio="estadístico"` is REFUSED. The message cites the protocol's rule
    and the alternating forecast weights.
  - The admissible criteria are:
    - `dominio`, with the expectation cited;
    - `uso`;
    - a new `excepcion`, which requires a written mechanism AND evidence for
      it. Working's aggregation is the example: it needs both pure aggregation
      and an underlying random walk (§2), not just an averaged series.
- Choosing the MA with θ < 0 then needs an explicit, recorded exception, not a
  default.
- The rule moves out of `_INSTRUCTIONS` into one function (say
  `policy.tie_ar_ma(domain, candidates)`) that the listing, `guion_node` and the
  card all call. It is the same lesson as BUG-0015: a rule that lives in only
  some layers splits the family.

Scope (from the WTI discussion, §2): the rule covers every price —
`price_index` and `multiplicative` — not consumer prices only. In a commodity
price the AR(1) carries the economic mechanism (gradual adjustment) and the
practical advantages. `excepcion` is the escape, and it is not a default.

### P2 — The card on the estimated models, with the forecast function

Implement the missing half of §10.bis decision 2.
- **When.** Whenever two or more ADEQUATE estimated models of the same lineage
  sit within ΔAIC < 2, the card is generated from their MLE coefficients:
  - in the output of the second `confirm_and_estimate`, or in a tool
    `compare_estimated(guion_path, versions)`.
- **What the card adds**, beside ψ, roots, π weights and materiality, which it
  has today:
  - **the forecast function in words and numbers**: ŷ_T(h) for h = 1, 2, s, 2s
    on the transformed level; whether the forecast extrapolates the last
    surprise, reverts to a fixed mean, or follows a moving mean;
  - **the sign reading** of each MA: "θ < 0: ρ₁ > 0, extrapolates the last
    surprise; weights alternate"; "0 < θ < 1: a level plus noise, exponential
    smoothing";
  - **a line against each declared expectation**, read from the `dominio` node
    (persistence, finite memory, stochastic mean, cycle), as a table
    (expected / implied by A / implied by B). The engine fills the "implied"
    columns mechanically; the expectation column is the text the analyst wrote,
    tagged by keyword where possible (persistencia, memoria finita, media
    estocástica, ciclo).
- The card does not decide (§4.1 of the domain study stands). It puts the
  disagreement where the decision is taken.

### P3 — Boundary tests know which candidate completes the pair

When `formal_tests` cannot run one side of a pair:
- **Shin-Fuller missing (no free AR):**
  - name the AR candidate already in the guion (same lineage, adequate) and
    offer `formal_tests` on it: «el par lo completa la versión vN (AR(1)), ya
    estimada»;
  - if there is none, propose the cheapest AR completion, not d + 1.
- **DCD missing (no free MA):** the symmetric message.
- **Wording:** «apuntaría a d+1» is replaced, when the pair is incomplete, by
  "one side only: complete the pair before reading it". d + 1 stays as the
  alternative AFTER the pair is read, not as the next step.

### P4 — An MA root near 1 after d + 1: the reading is said, not inferred

Decision 4 of §10.bis sends the question back to the d node, but the d node
does not say how to decide it. When a d + 1 candidate has an MA root
r ≥ CANCEL (0.90), the output states the two readings and their test:
- r = 1: over-differencing — stay at d;
- r < 1: a stochastic mean (a fraction 1 − r of each shock moves the mean for
  good) — d + 1 with that MA;
- the boundary test decides between them: DCD on that root, Shin-Fuller on the
  AR side. Without the pair, the default is d (parsimony).

## 5. Defects found on the same run (to register as bugs)

1. **`confirm_and_estimate` with `base_pre_path` ignores `d`, but the header
   announces it.** IPC_ES m06: «ARIMA(0,2,2)» in the header, d = 1 estimated
   (the `.pre`'s), and the equation shows ∇. Either refuse a `d` different from
   the base's or say "d comes from the .pre". This is the most serious of the
   five: it misleads the analyst.
2. **The seasonality chart does not reproduce the calendar-month means.**
   IPC_ES:

   | | January | July | December |
   |---|---|---|---|
   | chart | −0.87 | −0.22 | −0.76 |
   | mean of ∇100ln by month, about the overall mean | −1.15 | −0.81 | −0.11 |

3. **The Ockham ladder reports rung values that are not the final fit's.**
   IPC_ES 9/2012:
   - rung 1a: AIC 77.44, ω −0.43;
   - estimated model: AIC 69.90, ω +0.88;
   - and the domain warning speaks of «una caída permanente» for a rise.
4. **«TODOS los errores típicos … NO son válidos»** on a model with no
   parameters (WTI m00, random walk without μ).
5. **The identification listing's mean line contradicts itself:** «t=+0.83 →
   Sí, estimate_mu=True» (WTI m05). The "yes" comes from the base model
   already carrying μ, not from t.

## 6. Order and decisions

Proposed order:
1. **P1:** a policy function and a refusal in `guion_node`; small, and it closes
   F1.
2. **P3:** wording plus a lookup in the guion; small, and it closes F3.
3. **P2:** the card on estimated models; the real work, and it closes F2.
4. **P4:** text in the d node, with P2's machinery.

The five defects of §5 are registered first, as bugs, since two of them
(1 and 2) can mislead any lane.

Open decisions:
1. **P1's scope — settled (2026-10-02):** every price (`price_index` and
   `multiplicative`). The WTI discussion is in §2; `excepcion` requires a
   mechanism and evidence for it.
2. **Does `criterio="estadístico"` stay legal** in a genuine tie outside price
   series, or is a tie by definition not decided by statistics?
3. **P2's trigger:** ΔAIC < 2 only, or also the similarity band of the listing
   (as today)?
4. **Where this lands:** 0.2.3 (behavioural changes in the autonomous lane,
   during the running-in) or 0.3, with the other changes to how the LLM is
   asked (BUG-0116, BUG-0186)?
