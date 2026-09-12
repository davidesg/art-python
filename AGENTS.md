# AGENTS.md — operating the ATSW suite as an AI agent

This file tells an LLM agent how to drive the **Box-Jenkins-Treadway** time
series suite (fue + pyfug + ART) through the ART MCP server. It complements the
server's own `_INSTRUCTIONS` (loaded at runtime) and `docs/TOOLS.md`.

## The suite

| Component | Package | What it gives the agent |
|-----------|---------|--------------------------|
| FUE (+FUF) | `fue` | exact ML estimation, residuals, forecasting (`.inp`/`.pre`/`.out`/`.fuf`) |
| FUG | `pyfug` | high-definition graphics for time series analysis |
| ART | `art-tseries` | the 48 MCP tools + the guided/autonomous protocol |

Connect: `claude mcp add art -- art-mcp`. Tools are documented in `docs/TOOLS.md`.

## Core philosophy: evidence vs criterion

ART produces **evidence** (graphs, tests, numbers); the **criterion** (the
decisions the BJT method requires) is yours and/or the analyst's. Never invent a
decision the evidence does not support; never present a decision as forced.

## Two modes

- **Guided** — analyst + agent: present evidence, propose with arguments, the
  analyst confirms each decision node. Use `guided_identification` (4-call tree)
  then `confirm_and_estimate` / `suggest_intervention_form`.
- **Autonomous** — **the agent IS the analyst.** It walks the SAME decision
  nodes as the guided mode, in the same order and one at a time, and decides
  each one itself: `guided_identification` → `confirm_and_estimate` →
  interventions → `formal_tests` → reformulation. Every node is recorded with
  `guion_node(..., decidido_por="LLM")` and its reason; every estimation call
  passes `modo="autonomo"`, or the output stops at ⏸ waiting for a human who
  is not there (BUG-0180, BUG-0181).
- **`build_model` is NOT the autonomous mode.** It is the one-call heuristic
  shortcut — an auto-ARIMA with the school's rules — for when the user asks
  for an automatic fit without analysis. An "autonomous" run that reduces to
  it is a hybrid of the guided mode and an auto-ARIMA: the worst of both.

## Non-negotiable rules

1. **Always present the estimated model.** Every estimation returns the
   "MODELO ESTIMADO: <model>" equation block (in a code fence, marked
   "[Claude: muestra TAL CUAL]") + the residual graph titled "A.<model>". Show
   the equation block VERBATIM; NEVER rebuild your own parameter table (it can be
   wrong). Order: equation → residual graph → comment (|t|>2, Q-test, JB, verdict).
   Equation title and graph title share the model name so they are associated.
2. **Treating anomalies is the analyst's decision, never required.** The outlier
   scan runs latently after each estimation; it only surfaces a decision node
   when distortion is strong. Calibrate the ACF/PACF distortion
   (`preliminary_outlier_scan`: var_outlier %, ACF_max %, affected lags) and
   SUGGEST; the analyst decides whether to intervene before ARMA.
3. **Sequential construction from the previous optimum.** Each estimation starts
   from the previous model's `.pre` (estimated params as initial values) and
   writes a new `.pre` + `.out`. Do not start from scratch when refining.

## I/O conventions

- `.inp` = model spec + series. `.pre` = a `.inp` with estimated params (the
  starting point for the next step). `.out` = ASCII results report. `.fuf` = a
  `.pre` + forecast horizon/sigma line (header "program FUF").
- **Write all live outputs to `cases/<serie>/work/`** (git-ignored). NEVER write
  to `cases/<serie>/` root — that holds versioned case studies / test fixtures.

## Methodology references (in this repo)

- `docs/ARCHITECTURE.md` — layers, evidence-vs-criterion, the two modes.
- `docs/TOOLS.md` — the 48 MCP tools.
- DCD (non-invertibility, Davis-Chen-Dunsmuir): the constrained model RE-estimates
  all params with the factor fixed at the non-invertible value. MEG (stochastic
  seasonality) tests f=1…s/2 including the Nyquist (1+B). Critical values and the
  flat-likelihood caveat: see thesis chap2.4.
