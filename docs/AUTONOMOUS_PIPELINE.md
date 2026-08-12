# The autonomous pipeline — state, gaps, and what must be settled before closing the loop

*Working document for `run_full` / `build_model` / `batch_build`. Opened
2026-08-12. The guided path is being made solid first; this is the register of
what the autonomous path does today, what it cannot do, and which questions have
to be answered before any of it is built.*

---

## 1. Why this has its own document

The autonomous pipeline is the crown jewel and also the hardest part of the
suite, and those two facts are the same fact. It is the claim that
Box-Jenkins-Treadway judgement can be automated — that ART is a tool and not
only a surface for an assistant. Everything else in the suite has a human or a
model in the loop; this is the part that does not.

It also cannot be debugged the way the rest is, because its failures are not
wrong numbers. They are **wrong decisions that each look locally reasonable**,
and they interact: four of the defects closed in August 2026 (BUG-0013, 0015,
0016 and the annual-series one) were invisible on any single model and only
showed up when the same rule was run across a family of series with a known
answer.

So the order is deliberate: **make the guided path solid, then come back here.**
The guided path is where the criteria are written, argued and corrected; the
autonomous path can only be as good as the criteria it applies, and debugging it
against half-formed criteria measures the wrong thing.

---

## 2. What it does today, measured

Three benches with known answers, all in `tests/`. This is the asset the work
starts from — none of it existed in July.

| bench | series | what the answer is | autonomous result |
|---|---|---|---|
| `test_bug_0015_0016_…` | 8 monthly CPI, 2002–2019 | I(1), logs, drift in 7 of 8 | **correct** — 8/8 logs, 8/8 d=1, μ in 7, IPC_JP without |
| `test_annual_i0_precipitation_controls` | Geneva, Zurich, annual | I(0), non-seasonal, one in levels and one in logs | **correct** — d=0 both, λ=1 and λ=0 |
| `test_thesis_i2_chile_colombia` | IPC Chile / Colombia 1986–2001 | **I(2)**, deterministic *and* stochastic seasonality | **incomplete** — see below |

The third is where it stops. Measured 2026-08-12:

```
             delivered by build_model              thesis models
Chile        d=1  D=0  ifadf all zero  13 det      d=2, ifadf [0,1,1,0,1,0,1] (PC6)
             diagnosis: REVISAR ✗ (Q fails 6,12,24,36)
Colombia     d=1  D=0  ifadf all zero  15 det      d=2
```

All seventeen thesis models are d=2, in both countries, without exception. The
autonomous path delivers the **initial specification** and stops.

That is not by itself a defect — the initial specification *should* be d=1, and
§4 explains why. The defect is what happens next, or rather what does not.

---

## 3. The two gaps, and they are different kinds

### 3.1 A verdict that is computed and never shown — a plain defect

`describe_formal_tests` runs `dcd_overdiff_regular` and prints its verdict.
`build_model` does not: it computes `dcd()` and `meg()` and formats those two
(`_format_dcd_meg`), and `dcd_overdiff_regular` appears nowhere in
`mcp_server.py` except in the bug warnings inside `_INSTRUCTIONS`.

So on Chile the strongest signal in the whole analysis — **LR = 18.235 against a
critical value of 1.94, "consider d+1"** — is never produced on the autonomous
path. The MEG *is* shown (Colombia reports `freq=4: Estocástica ⚠ LR=2.445`), so
of the two tests that contradict the delivered specification, one is visible and
the other is not.

This is the same shape as BUG-0010: a result that exists and is silently
dropped. It is small — a handful of lines — and it is the first thing to do
here, because until it is done the autonomous path cannot even *report* that its
own specification is contradicted.

### 3.2 Nothing re-specifies — a design question, not a defect

`run_full` has an outlier loop. It has no specification loop. Even with §3.1
fixed, the pipeline would report "consider d+1" and deliver d=1.

The guided path closes this with a human: the analyst reads the verdict and
calls `confirm_and_estimate` again with d=2. The autonomous path has nobody, and
**giving it somebody is the hard part of this document.**

---

## 4. The principle that constrains any solution

From the methodology, and it is not negotiable:

> **A formal hypothesis test on an inadequate model is not a weak test. It is
> not a test at all.**

Its distribution under the null assumes the model is right, so on a misspecified
model the statistic answers a question about something other than the series.
This suite has measured it twice: untreated seasonality inflates the ADF
standard error and biases it towards "difference again" (BUG-0016); a missing
mean leaves a drift the ARMA orders end up explaining (BUG-0013).

Hence the sequence: **criterion first, formal tests afterwards.** The initial
choice of λ, d, D, harmonics and orders is a *specification*, a different act
from a test. The real contrast on the order of integration comes at the end,
on an adequate model — `dcd_overdiff_regular`, Shin-Fuller — which is exactly
where the flow puts them.

And here is the bite for this document: **Chile's delivered model is not
adequate.** Its diagnosis is `REVISAR ✗` with Q failing at lags 6, 12, 24 and 36
— the seasonal lags, which is what stochastic seasonality looks like. Acting on
a formal test computed on that model would be doing precisely what the principle
forbids. So a re-specification loop cannot simply be "read the verdict and
apply it": it needs a gate on adequacy first, and the gate is not obvious,
because the model may be inadequate *because* of the thing the test is pointing
at.

That circularity is the real problem, and it is why this is a design task and
not a patch.

---

## 5. Explosion risks — what runs away if the loop is closed naively

These are the failure modes to design against, not hypotheticals: each has a
mechanism that is already visible somewhere in the suite.

**Escalation of `d`.** Take the verdict, set d=2, re-run, ask again. The DCD on
the d=2 model may again say "consider d+1". Over-differencing injects an MA unit
root at −1, which is exactly what the witness is built to detect, so the loop can
manufacture its own evidence. Any loop needs a hard ceiling and a rule that a
second escalation is a *stop*, not a step.

**Activation of `ifadf` on frequencies the sample cannot sustain.** The MEG at
5 % will call roughly one frequency in twenty stochastic by chance, and there are
six frequencies per model. Applying every stochastic verdict makes a model that
fits the sample and forecasts worse. Chile's thesis model PC6 has four active
frequencies — a defensible result reached by an analyst over many iterations, not
something to arrive at in one automatic pass.

**Interaction between decisions.** Fixing the index rule (BUG-0015) made the
over-differencing defect fire on *more* series, and it would have looked like a
regression of the fix. Decisions are not independent: λ changes what the unit
root tests see, d changes what the seasonality test sees, seasonality changes
what the ARMA orders look like. **A loop that re-specifies one thing must
re-examine the ones upstream of it**, and that is a dependency graph nobody has
written down yet.

**The outlier loop chasing structure.** Already met once: folding the residual
mean check into `clean` made the autonomous run add two interventions on IPC_ES,
chasing a drift with dummies. A dummy cannot absorb a missing mean. The loop was
deliberately left consulting `residuals_ok` (shape) rather than `clean`
(adequacy) for that reason — and any new loop inherits the same trap in a new
place.

**Non-termination and oscillation.** Two rules that each improve one diagnostic
and worsen the other will cycle. There is no convergence proof for BJT
identification and there will not be one; the loop needs a budget and a rule for
what to return when the budget runs out. "Return the last model" is not a good
answer; "return the model plus what remained contradicted" is.

**Silent divergence from the guided path.** Every rule that exists in only one
of the two paths is a defect waiting to be found — that is the family BUG-0013,
0015 and 0016 belong to. Any new autonomous behaviour must be a *shared* rule
consulted by both, or it will drift.

---

## 6. Questions to answer before writing code

Roughly in the order they block each other.

1. **Is the autonomous path a loop, a single pass with a verdict, or a
   two-phase process?** Three candidate shapes: (i) stay as it is and report
   contradictions loudly; (ii) one bounded second pass, no iteration; (iii) a
   real loop with a dependency graph and a budget. They are very different
   amounts of work and only (i) is safe today.

2. **Who is allowed to act on a formal test, and when is a model "adequate
   enough"?** §4's circularity lives here. One possible answer: a test may be
   *acted on* only when the residual defect it points at is the same one the
   diagnosis is complaining about — Chile's Q failing at seasonal lags and the
   MEG calling a frequency stochastic are the same finding, and that agreement
   is evidence. Disagreement between the two would be a stop.

3. **What is the dependency graph of the decisions?** Which decisions must be
   re-examined when d changes, when λ changes, when a frequency is reformulated.
   This should be written down whatever shape (1) takes, because the guided path
   needs it too — it is the ordering the instructions try to convey in prose.

4. **How does an autonomous re-specification get recorded?** `guion.py` exists
   and records specification, diagnosis, equation, decision and rationale, and
   the autonomous path does not write to it at all today. A loop that
   re-specifies without leaving a trace is not auditable, and auditability is
   the point of the guion.

5. **Is `domain` the general channel for judgement inputs?** It was added for
   the index rule (BUG-0015). The AR(1)/MA(1) tie-break for price series wants
   the same thing, and TODO already asks for it. If the answer is yes, it should
   be designed once rather than grown.

---

## 7. Task list

Ordered. Everything above the line is doable now and does not depend on the
design questions.

- [ ] **Report `dcd_overdiff_regular` in `build_model`.** §3.1. A handful of
      lines; without it the autonomous path cannot say that its own tests
      contradict it. Do this first.
- [ ] **`run_full` writes to the guion.** Already in TODO from the external
      review; it is a precondition for anything auditable here.
- [ ] **State the decision dependency graph** (question 3) as a document. Needed
      by the guided path too.
- [ ] **Golden benches for more domains** — the three in §2 cover I(0), I(1) and
      I(2). Missing: a non-seasonal monthly series, a series with a genuine level
      break, one with non-constant variance.
- [ ] **Make every autonomous decision a shared rule.** Audit for the remaining
      members of the BUG-0013 family: rules that live in `_INSTRUCTIONS` or in
      `guided_identification` and not in `policy.py`. The AR(1)/MA(1) tie-break
      is the known one.

---

- [ ] **Answer questions 1, 2 and 5** (§6), then decide the shape.
- [ ] Only then: the second pass or the loop, whichever shape survives.

---

## 8. What "the guided path is solid" means

The gate for coming back to this document. Not a vague standard:

* every criterion the guided path applies is in `policy.py` and consulted by
  both paths, so there is nothing left that only a human sees;
* the instructions have tests on their **content**, not only on the code —
  `base_pre_path` had zero mentions while being the only way to honour the
  `.pre` contract, and no test could notice;
* the four open bugs are closed or explained;
* and the guion records a guided session completely enough that an autonomous
  session could be compared against it, which is how the two paths get held to
  the same standard.
