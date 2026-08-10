# Architecture of the ART / FUE / FUG / FUF suite

> Architectural vision document. It records the separation of layers, the
> **evidence vs judgement** philosophy, the two modes of operation, and the
> refactor plan that **unified the orchestration**.
> Written Jun-2026 after the critical review of the suite; translated into
> English Aug-2026, when the tool count was also corrected from 32 to 35.

---

## 1. What the suite is for

Building univariate models by the **Box-Jenkins-Treadway (BJT)** methodology: an
**iterative** process that uses graphical tools and tests to take decisions,
building the model step by step through partial identification until a final
model is reached, ready to use (estimation + forecasting).

The intrinsic limitation of the BJT process is that **it requires judgement**:
the decisions, empirical or theoretical, are not arbitrary. What supplies that
judgement is **Claude**, fed by the evidence the suite produces.

This is the core of a **false simplicity**: ARMA models are simple, but the
iterative building process worked wonderfully mainly if you were Box, Jenkins or
one of their disciples. The real difficulty is training the analyst in decisions
that are often heuristic; AI plays here, with its limitations, the part of that
trained analyst. Note also that the analysis is **not the canonical Box and
Jenkins one** but the version extended by **Arthur B. Treadway** (a disciple of
Gwilym Jenkins), with elements and heuristics coming out of his work at the
Forecasting and Monitoring Services (SPS) of the Spanish economy.

**Design principle (the measuring stick):** forecasting is one of the objectives
of an ARMAX model — perhaps unbeatable at it — but the univariate model is also
the foundation of a more sophisticated analysis of relationships. That is why
these univariate models must be the **measuring stick** for more complex ones:
if a sophisticated model does not improve on their forecasts, something is wrong
with it and it should be rethought.

---

## 2. Components and boundaries

| Component | Role | Nature |
|------------|-----|-----------|
| **FUE** (`atws/fue`) | Exact ML estimation + **forecasting (FUF)** + low-level diagnostics | Python over `_fue_engine.so` (C) |
| **FUG / pyfug** (`atws/fug/pyfug`) | High-definition graphics for time series analysis | Python + matplotlib |
| **ART** (`art-python/src/art`) | Orchestration + semantic adaptation + audit trail | Python |
| **ART MCP** (`mcp_server.py`) | A surface of 35 tools facing Claude | FastMCP |
| **Claude** | **Judgement**: identification, interpretation, decisions | LLM |

**FUF is not a peer component.** In the Python suite forecasting lives *inside*
FUE (`load_fuf`, `forecast_fuf`, `write_fuf`, `fuf_cli.py`,
`report_forecast.py`). It is a **capability of FUE** downstream of the finished
model. The `atws/fuf/fuf-*` trees are the C/GTK legacy.

---

## 3. Layers (no cycles)

```
CLAUDE — judgement (empirical / theoretical)
  guided:     suggests → the analyst decides
  autonomous: decides everything → presents the final model
   │  MCP protocol + the server's instructions
ART MCP  (mcp_server.py · 35 tools)
   │
ART describe.py  ── SEMANTIC ADAPTER
   │  Description{summary, figure_b64, recommendation, data}
   │  turns numbers and graphs into evidence an LLM can read
   ├──────────────────────────────┐
ART analysis                     (describe.py and mcp_server.py are
  identification                   the only ones that import pyfug)
  seasonal_detection
  model_detection · interventions
  formal_tests · diagnosis · guion
   │                                │
FUE (estimation + FUF)            FUG / pyfug (graphics)
   │
_fue_engine.so (C)
```

Verified invariants: the graph has no cycles; only `describe.py` and
`mcp_server.py` know about pyfug; FUE is the numerical base underneath
everything.

**`describe.py` is the central success**: the adapter that makes the numerical
engines "speak Claude". It is the right abstraction and must be preserved.

---

## 4. Philosophy: evidence ≠ judgement

The boundary the design has to respect:

- **Evidence** (deterministic, reproducible): the engines and the analysis
  modules.
- **Presentation of the evidence**: `describe.py` (`summary` + `figure_b64` +
  `data`).
- **Judgement**: Claude, through the MCP protocol.
- **Record of decisions** (the BJT audit trail): `guion.py` → `guion.json`.

**Tension found:** judgement leaks down into the evidence layer. The
`Description.recommendation` field is computed by ART with hard-wired heuristics
(e.g. "Decision B1 by default"), so there are **two judges at once** — ART's
heuristics and Claude — which can contradict each other and which **anchor**
Claude and the analyst before either has reasoned.

The design rule to aim for: the evidence layer emits **evidence plus the menu of
possible decisions with the arguments for and against**, not verdicts. Closing
the judgement is Claude's part (guided: it proposes; autonomous: it decides).

---

## 5. The two modes

| | Guided (analyst + Claude) | Autonomous (Claude alone) |
|---|---|---|
| Who decides | The analyst, with Claude's suggestions | Claude |
| Output | Iterative, confirmed at every stage | One final model |
| Path as it was | `guided_identification` → `confirm_and_estimate` → `suggest_intervention_form` → `confirm_and_estimate(base_pre_path)` → `formal_tests` | `build_model` / `batch_build` (a monolith) |

### The structural problem: DOUBLE ORCHESTRATION

The autonomous mode **did not drive the same tools Claude would drive**: it
*reimplemented* them in a monolith. `build_model` (`mcp_server.py:2735-2932`)
took six decisions inline that in guided mode Claude takes by reading the
`describe_*`:

| Decision | In `build_model` (autonomous) | In guided mode |
|----------|------------------------------|-----------|
| λ | `0.0 if bc.data["gap"] >= 0 else 1.0` | Claude reads `describe_boxcox` |
| d | `urt.data["recommended_d"]` | Claude reads `describe_unit_root` |
| D, decision | `seas.data` | Claude reads `describe_seasonality` |
| no. of harmonics | `freq//2-1 if decision!="A" else 0` | Claude / `confirm_and_estimate` |
| p, q | `suggest_orders(...)[0]` | Claude reads `describe_identification` |
| Intervention | `z>3.0` loop + step-if-consecutive-else-pulse | `suggest_intervention_form` (threshold 2.5) |

**Proven consequence of the drift:** `batch_build` had `d=1` hard-wired while
`build_model` correctly called `describe_unit_root` — the classic bug of keeping
two implementations of the same method. It also contradicts the philosophy: in
autonomous mode "Claude decides", when in fact a fixed heuristic in the code
decided.

---

## 6. The refactor: unifying the orchestration

**Objective:** one single source of truth per decision and per execution step.
Autonomous mode becomes "Claude / the default policy running the SAME guided
sequence without the confirmation pauses".

### Target architecture: three separated layers

```
art/policy.py    ← DECISION RULES (a single home). Pure functions:
                   decide_lambda(bc_data)                  -> float
                   decide_differencing(seas_data, urt_data)-> (d, D, decision, n_harm)
                   decide_orders(specs)                    -> (p, q, P, Q)
                   decide_interventions(diag, existing)    -> list[(at, form)]
                   should_stop(diag)                       -> bool
                   THRESHOLDS = {...}   # 2.0/2.5/3.0/3.5 in one place

art/pipeline.py  ← EXECUTION STEPS (a single home). Pure mechanism:
                   build_and_fit(ts, spec)        -> (model, diag)
                       # wraps _make_model + _write_inp + _load_fitted + diagnose
                   outlier_round(ts, spec, diag)  -> spec'
                   run_full(ts, policy)           -> PipelineResult

mcp_server.py    ← THIN TOOLS over pipeline + policy:
                   build_model          = pipeline.run_full(ts, DefaultPolicy())
                   batch_build          = a loop of run_full
                   confirm_and_estimate = pipeline.build_and_fit(ts, claude_spec)
                   guided_*             = describe_* + policy.decide_* AS A SUGGESTION
```

**The key principle:** the `policy` functions are the only home of each decision
rule. In guided mode they are exposed as a *suggestion* (Claude may override);
in autonomous mode they are applied. Same rule, two ways of consuming it,
**zero drift**.

### Phases (each one deliverable and verifiable on its own)

**Phase 0 — Safety net.**
Characterisation tests: capture the current output of `build_model` and
`confirm_and_estimate` over fixture series (golden output). The refactor must
preserve the behaviour of the autonomous mode.

**Phase 1 — Extract `policy.py`.**
Move `build_model`'s six inline decisions into pure functions. `build_model`
calls them (no behavioural change). The guided tools begin to expose
`policy.decide_*` in their `recommendation` field, replacing the hard-wired and
scattered recommendations (e.g. "Decision B1 by default").
→ Resolves §4 (leaked judgement): it is centralised AND made overridable.

**Phase 2 — Extract `pipeline.py`.**
Move `_make_model` + `_write_inp` + `_load_fitted` + `diagnose` into
`build_and_fit`, and the outlier loop into `run_full`. `build_model` comes down
to ~15 lines: `result = run_full(ts, DefaultPolicy()); return render(result)`.
`confirm_and_estimate` reuses `build_and_fit`. `batch_build` iterates `run_full`.
→ Removes the duplication between the `_make_model` loop and the guided tools.

**Phase 3 — Unify the intervention logic.**
The step/pulse heuristic existed in `build_model` (inline) and in
`suggest_intervention_form` (threshold 2.5). Move it to
`policy.decide_interventions`. Guided and autonomous then use the identical rule.

**Phase 4 — Policy as an interchangeable object.**
`DefaultPolicy` (heuristics) vs `ClaudePolicy` (delegates to Claude). Autonomous
= `DefaultPolicy`. This makes the philosophy explicit in code: autonomous mode
is "the default heuristic policy", and it leaves the door open for Claude's own
choices to feed back as a policy.

**Phase 5 — Cleanup.**
Delete dead duplication, align thresholds to `policy.THRESHOLDS`, retire the
divergent paths.

### Implementation status (Jun-2026)

| Phase | State | Result |
|------|--------|-----------|
| 0 | ✅ | `tests/test_golden_pipeline.py` + a frozen fixture; the safety net |
| 1 | ✅ | `art/policy.py` — pure decision functions + `THRESHOLDS` |
| 2 | ✅ | `art/pipeline.py` — execution primitives + `build_and_fit` + `run_full`; `build_model`/`batch_build` share the loop |
| 3 | ✅ | a single `policy.decide_form`; intervention thresholds from `THRESHOLDS` |
| 4 | ✅ | `Policy`/`DefaultPolicy`/`ClaudePolicy`; `run_full(decision_policy=…)` |
| 5 | ✅ | user-facing thresholds → `THRESHOLDS["outlier_user"]`; dead `_param_table`/`_param_names` removed |

Behaviour preserved through every phase (golden green). Zero net regressions
against the `af2ba9b` baseline (the suite's remaining failures are
pre-existing: nlags on short series, Chile tolerances, quarterly npar).

**Closing the unification (done):** `build_model` is now the only engine in both
modes. With no spec → `DefaultPolicy` (autonomous). With a confirmed spec
(`lam/d/D/p/q/n_harmonics/decision`) → `ClaudePolicy`, which honours what the
analyst fixed and leaves the rest to the heuristic, driving the same `run_full`.
"Autonomous" and "guided" are literally the same path with a different "who
confirms". For outlier-by-outlier confirmation the `confirm_and_estimate` +
`suggest_intervention_form` flow is still available.

### Risk and verification

- **Main risk:** `build_model`'s output can change if an inline decision was not
  exactly equivalent to the new `policy` function. Mitigated by the Phase 0
  golden tests.
- **Verification per phase:** the golden tests must pass after each phase
  (behaviour preserved) except for deliberate, documented changes.
- **Sequence:** every phase is independent and deployable; there is no big bang.

### State of the `data` contract (related)

`Description.data` is an untyped `dict` with magic defaults
(`data.get("recommended_d", 1)`). That is where the hard-wired `d=1` bug hid.
A recommendation complementary to the refactor: type `data` per stage
(`SeasonalityData`, `UnitRootData`, …) or remove the magic defaults so that a
missing key is an explicit error.

---

## 7. Residual architectural debt (outside the orchestration refactor)

| Item | Severity | Note |
|------|-----------|------|
| The FUF boundary uses private attributes (`_fuf_*`) | Low-medium | An explicit `ForecastSpec` is missing |
| Split state: `.inp`/`.pre` vs `guion.json` | Medium | `guion.json` ought to be the source of truth |
| `_write_inp` duplicates FUE's knowledge of the format | Medium | No version stamp in the `.inp` header |
| Split graphics: pyfug vs `fue.plots` | Low | pyfug should own all the plotting |

---

## 8. What to preserve

- `describe.py` as the **semantic adapter** (engines → conversable evidence).
- The **acyclic dependency graph** and the FUE(numbers) / pyfug(graphics)
  separation.
- `guion` as the **audit trail** of the iterative BJT process.
- The guided/autonomous distinction — but implemented as **a single
  orchestration path** with a different "who confirms".

## Releasing: push a tag, do not run `twine`

This package publishes from CI: pushing a `v*` tag (or `art-v*` / `atsw-v*`)
triggers the workflow that builds and uploads. Running `twine upload` by hand
gets there first, and then the workflow finds the files already present and
fails — which is what happened to several releases before this note existed.

    git tag -a v<version> -m "<package> <version>"
    git push origin v<version>

That is the whole release. Watch the run; do not upload anything yourself.
